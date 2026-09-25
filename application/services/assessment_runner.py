"""Runs an assessment in the background and reports how far it has got.

``AssessmentService.assess_page`` is one blocking call per page, which left the
caller holding a request open for as long as a page took — the first of a
session also loads the checkpoints — with nothing to show until it returned,
and with the run tied to whichever browser tab happened to be driving it. This
moves the loop server-side: a run is started once, pages through the chat on a
worker thread, and anyone can ask how it is going, or ask it to stop, while it
works.

A run stops between pages, never inside one: a page is one batch put to the
engine, and answers land in the decision cache page by page, so stopping and
starting again later resumes where it left off without losing anything.
"""

import logging
import threading
import time
from dataclasses import dataclass, replace
from enum import StrEnum

from application.ports.decision_engine import IDecisionEngine
from application.services.assessment_service import AssessmentService
from domain.errors import BusyError, ChatNotFoundError

logger = logging.getLogger(__name__)


class RunState(StrEnum):
    IDLE = "idle"
    #: Waiting on the engine's first load; nothing has been assessed yet.
    LOADING = "loading"
    RUNNING = "running"
    #: Asked to stop; finishing the page in flight.
    STOPPING = "stopping"
    DONE = "done"
    STOPPED = "stopped"
    FAILED = "failed"


_ACTIVE = frozenset({RunState.LOADING, RunState.RUNNING, RunState.STOPPING})


@dataclass(frozen=True)
class RunStatus:
    """A snapshot of one chat's run. Safe to hand out: it is never mutated."""

    chat_id: int
    state: RunState = RunState.IDLE
    page_size: int = 0
    #: Pages the run stops after, or None to run until the chat is done.
    max_pages: int | None = None
    #: Where the run started, and where the next page will start.
    started_offset: int = 0
    next_offset: int = 0
    pages: int = 0
    assessed: int = 0
    skipped: int = 0
    coverage_percent: float = 0.0
    #: Wall time since the run started, and since the last page finished.
    elapsed_seconds: float = 0.0
    #: Time spent inside pages, and inside the most recent one.
    page_seconds: float = 0.0
    last_page_seconds: float | None = None
    error: str | None = None

    @property
    def is_active(self) -> bool:
        return self.state in _ACTIVE

    @property
    def seconds_per_message(self) -> float | None:
        """Page time over messages assessed. The first page of a session also
        loads the checkpoints, so early in a run this reads high."""
        return round(self.page_seconds / self.assessed, 3) if self.assessed else None


class _Run:
    def __init__(self, status: RunStatus) -> None:
        self.status = status
        self.started_at = time.monotonic()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None


class AssessmentRunner:
    """At most one background run per chat, each on its own daemon thread."""

    def __init__(self, service: AssessmentService, engine: IDecisionEngine) -> None:
        self._service = service
        self._engine = engine
        self._runs: dict[int, _Run] = {}
        self._lock = threading.Lock()

    def start(
        self,
        chat_id: int,
        offset: int,
        page_size: int,
        max_pages: int | None = None,
    ) -> RunStatus:
        """Starts a run from ``offset``, or returns the one already going.

        It runs until the chat is done, it is stopped, or — with ``max_pages``
        — it has worked through that many pages.

        Raises:
            ChatNotFoundError: if the chat has not been imported.
            BusyError: if another chat's run is going. Two runs would share
                one engine and each take twice as long, for no gain.
        """
        # Checked here rather than on the worker, so a bad id is a 404 on the
        # request that asked for it and not a failed run found later.
        self._service.get_assessment(chat_id)

        with self._lock:
            current = self._runs.get(chat_id)
            if current is not None and current.status.is_active:
                return self._snapshot(current)
            for other_id, other in self._runs.items():
                if other.status.is_active:
                    raise BusyError(
                        f"Chat {other_id} is being assessed; stop it or wait for it "
                        "to finish first."
                    )
            run = _Run(
                RunStatus(
                    chat_id=chat_id,
                    state=(
                        RunState.RUNNING if self._engine.is_ready else RunState.LOADING
                    ),
                    page_size=page_size,
                    max_pages=max_pages,
                    started_offset=offset,
                    next_offset=offset,
                )
            )
            run.thread = threading.Thread(
                target=self._work,
                args=(run,),
                name=f"assessment-{chat_id}",
                daemon=True,
            )
            self._runs[chat_id] = run
        run.thread.start()
        return self._snapshot(run)

    def stop(self, chat_id: int) -> RunStatus:
        """Asks the run to stop once the page in flight is saved."""
        with self._lock:
            run = self._runs.get(chat_id)
            if run is None or not run.status.is_active:
                return self._snapshot(run) if run else RunStatus(chat_id=chat_id)
            run.stop.set()
            run.status = replace(run.status, state=RunState.STOPPING)
            return self._snapshot(run)

    def status(self, chat_id: int) -> RunStatus:
        with self._lock:
            run = self._runs.get(chat_id)
            return self._snapshot(run) if run else RunStatus(chat_id=chat_id)

    def wait(self, chat_id: int, timeout: float | None = None) -> RunStatus:
        """Blocks until the chat's run ends. For tests and shutdown."""
        with self._lock:
            run = self._runs.get(chat_id)
        if run is not None and run.thread is not None:
            run.thread.join(timeout)
        return self.status(chat_id)

    # --- worker -----------------------------------------------------------
    def _work(self, run: _Run) -> None:
        chat_id = run.status.chat_id
        try:
            while True:
                page_started = time.monotonic()
                progress = self._service.assess_page(
                    chat_id, offset=run.status.next_offset, limit=run.status.page_size
                )
                with self._lock:
                    status = run.status
                    run.status = replace(
                        status,
                        # A stop requested mid-page stays requested.
                        state=(
                            status.state
                            if status.state is RunState.STOPPING
                            else RunState.RUNNING
                        ),
                        next_offset=progress.next_offset,
                        pages=status.pages + 1,
                        assessed=status.assessed + progress.assessed_now,
                        skipped=status.skipped + progress.skipped_already_done,
                        coverage_percent=progress.coverage_percent,
                        page_seconds=round(
                            status.page_seconds + time.monotonic() - page_started, 2
                        ),
                        last_page_seconds=round(time.monotonic() - page_started, 2),
                    )
                if progress.is_complete:
                    self._finish(run, RunState.DONE)
                    return
                if run.stop.is_set():
                    self._finish(run, RunState.STOPPED)
                    return
                if run.status.max_pages and run.status.pages >= run.status.max_pages:
                    self._finish(run, RunState.DONE)
                    return
        except ChatNotFoundError as error:
            # Deleted while the run was going.
            self._finish(run, RunState.FAILED, f"Chat {error} no longer exists.")
        except Exception as error:  # the run must end, whatever failed
            logger.exception("Assessment run for chat %s failed.", chat_id)
            self._finish(run, RunState.FAILED, str(error) or type(error).__name__)

    def _finish(self, run: _Run, state: RunState, error: str | None = None) -> None:
        with self._lock:
            run.status = replace(
                run.status,
                state=state,
                error=error,
                elapsed_seconds=round(time.monotonic() - run.started_at, 2),
            )
        logger.info(
            "Assessment run for chat %s ended %s after %d pages, %d messages.",
            run.status.chat_id, state, run.status.pages, run.status.assessed,
        )

    def _snapshot(self, run: _Run) -> RunStatus:
        status = run.status
        if not status.is_active:
            return status
        if status.state is RunState.LOADING and self._engine.is_ready:
            status = replace(status, state=RunState.RUNNING)
        return replace(
            status, elapsed_seconds=round(time.monotonic() - run.started_at, 2)
        )
