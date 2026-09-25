"""An answer cache that sits in front of any :class:`IDecisionEngine`.

Chat repeats itself. A third of the messages in the export this was tuned
against say something another message already said, word for word — a single
recurring two-emoji reply accounted for 2,943 of 42,465. The engine is
deterministic, so asking it the same question set about the same state twice
buys a forward pass that returns what it returned the first time.

The ``decisions`` table already caches by message, which is what makes a pass
resumable. This catches what that cannot: two *different* messages whose text
is identical. Nothing downstream can tell the difference — the engine is only
ever shown the sender and the text, so two messages that agree on both are one
question as far as it is concerned.
"""

import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Sequence
from typing import Any

from application.ports.decision_engine import (
    DecisionQuestion,
    EngineResult,
    IDecisionEngine,
)

logger = logging.getLogger(__name__)

#: Distinct (state, question set) answers held in memory. An entry is one small
#: dict of answers per question, so the default costs tens of megabytes; the
#: repeats that matter in a chat are a far smaller set than this, because a
#: handful of short replies account for most of them.
DEFAULT_MAX_ENTRIES = 10_000


class CachingDecisionEngine(IDecisionEngine):
    """Memoises another engine's answers, evicting least-recently-used first."""

    def __init__(
        self,
        inner: IDecisionEngine,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._inner = inner
        self._max_entries = max(1, max_entries)
        self._entries: OrderedDict[str, EngineResult] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @property
    def is_ready(self) -> bool:
        return self._inner.is_ready

    def describe(self) -> dict[str, str | None]:
        return {
            **self._inner.describe(),
            "answer_cache": (
                f"{self.hits} hits, {self.misses} misses, "
                f"{len(self._entries)} of {self._max_entries} entries"
            ),
        }

    def predict(
        self,
        state: Any,
        questions: Sequence[DecisionQuestion],
    ) -> EngineResult:
        key = _cache_key(state, questions)
        if key is not None:
            with self._lock:
                cached = self._entries.get(key)
                if cached is not None:
                    self._entries.move_to_end(key)
                    self.hits += 1
                    return _detached(cached)

        # Deliberately outside the lock. A prediction takes long enough that
        # holding the lock across it would serialise every other caller behind
        # it; two threads racing on the same state waste one pass instead.
        result = self._inner.predict(state, questions)

        if key is not None:
            with self._lock:
                self.misses += 1
                self._entries[key] = _detached(result)
                self._entries.move_to_end(key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
        return result

    def predict_batch(
        self,
        states: Sequence[Any],
        questions: Sequence[DecisionQuestion],
    ) -> list[EngineResult]:
        """Answers what it can from the cache and sends the rest as one batch.

        A state that repeats inside the batch goes to the engine once, which is
        where most of a page's repeats are: a short reply sent several times in
        a row.
        """
        results: list[EngineResult | None] = [None] * len(states)
        # Cache key -> positions in ``states`` waiting on that answer.
        waiting: dict[str, list[int]] = {}
        uncacheable: list[int] = []

        with self._lock:
            for position, state in enumerate(states):
                key = _cache_key(state, questions)
                if key is None:
                    uncacheable.append(position)
                    continue
                cached = self._entries.get(key)
                if cached is not None:
                    self._entries.move_to_end(key)
                    self.hits += 1
                    results[position] = _detached(cached)
                elif key in waiting:
                    # Answered by the engine call below, so as good as a hit.
                    self.hits += 1
                    waiting[key].append(position)
                else:
                    waiting[key] = [position]

        # One representative state per distinct key, then the uncacheable ones.
        asked = [positions[0] for positions in waiting.values()] + uncacheable
        if asked:
            # Outside the lock, for the same reason as in ``predict``.
            answered = self._inner.predict_batch(
                [states[position] for position in asked], questions
            )
            by_position = dict(zip(asked, answered, strict=True))
            with self._lock:
                for key, positions in waiting.items():
                    result = by_position[positions[0]]
                    self.misses += 1
                    self._entries[key] = _detached(result)
                    self._entries.move_to_end(key)
                    for position in positions:
                        results[position] = _detached(result)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
            for position in uncacheable:
                results[position] = by_position[position]

        return [result for result in results if result is not None]


def _detached(result: EngineResult) -> EngineResult:
    """A copy, so that what one caller does to its result stays with it.

    Shallow: the answers themselves are frozen, and this only has to stop a
    caller adding to or replacing an entry in a mapping every later caller is
    also holding.
    """
    return EngineResult(answers=dict(result.answers), metadata=dict(result.metadata))


def _cache_key(state: Any, questions: Sequence[DecisionQuestion]) -> str | None:
    """A stable identity for "this state, put these questions".

    The questions are half of it: the same message read against a different set
    of criteria is a different question, and an edited question set must not be
    answered out of the cache.

    Returns ``None`` for a state that will not serialise, which means the call
    goes straight through rather than failing over a cache.
    """
    try:
        return json.dumps(
            [state, [_question_key(question) for question in questions]],
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        logger.debug("State does not serialise; answering it uncached.")
        return None


def _question_key(question: DecisionQuestion) -> list[Any]:
    return [
        question.key,
        str(question.decision_type),
        question.instructions,
        dict(question.criteria),
        list(question.levels),
    ]
