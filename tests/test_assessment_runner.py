"""Tests for running an assessment in the background."""

import threading
import unittest
from collections.abc import Sequence
from typing import Any

from application.ports.decision_engine import DecisionQuestion, EngineResult
from application.services.assessment_runner import AssessmentRunner, RunState
from domain.errors import BusyError, ChatNotFoundError
from domain.models.chat import Chat
from tests.fakes import FakeDecisionEngine
from tests.test_assessment import AssessmentTestCase

WAIT = 5.0


class GatedEngine(FakeDecisionEngine):
    """Holds every batch until the test lets it through, one at a time."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entered = threading.Semaphore(0)
        self.gate = threading.Semaphore(0)

    def predict_batch(
        self, states: Sequence[Any], questions: Sequence[DecisionQuestion]
    ) -> list[EngineResult]:
        self.entered.release()
        self.gate.acquire(timeout=WAIT)
        return super().predict_batch(states, questions)


class RunnerTestCase(AssessmentTestCase):
    def runner(self, engine=None, page_size=2) -> AssessmentRunner:
        service = self.service(engine, page_size=page_size)
        return AssessmentRunner(service, self.engine)


class TestAssessmentRunner(RunnerTestCase):
    def test_a_run_pages_through_to_the_end(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(5)])
        runner = self.runner()
        runner.start(self.chat.id, offset=0, page_size=2)
        status = runner.wait(self.chat.id, WAIT)

        self.assertIs(status.state, RunState.DONE)
        self.assertEqual(status.pages, 3)
        self.assertEqual(status.assessed, 5)
        self.assertEqual(status.next_offset, 5)
        self.assertEqual(status.coverage_percent, 100.0)
        self.assertFalse(status.is_active)
        self.assertIsNotNone(status.seconds_per_message)

    def test_a_page_cap_stops_the_run_early(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(5)])
        runner = self.runner()
        runner.start(self.chat.id, offset=0, page_size=2, max_pages=1)
        status = runner.wait(self.chat.id, WAIT)

        self.assertIs(status.state, RunState.DONE)
        self.assertEqual((status.pages, status.assessed, status.next_offset), (1, 2, 2))

    def test_stopping_finishes_the_page_in_flight_then_stops(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(6)])
        engine = GatedEngine()
        runner = self.runner(engine)
        runner.start(self.chat.id, offset=0, page_size=2)
        self.assertTrue(engine.entered.acquire(timeout=WAIT))

        self.assertIs(runner.stop(self.chat.id).state, RunState.STOPPING)
        engine.gate.release()
        status = runner.wait(self.chat.id, WAIT)

        self.assertIs(status.state, RunState.STOPPED)
        self.assertEqual((status.pages, status.assessed, status.next_offset), (1, 2, 2))

    def test_starting_a_chat_already_running_returns_that_run(self):
        self.given_messages(*[("u1", f"note {i}") for i in range(4)])
        engine = GatedEngine()
        runner = self.runner(engine)
        first = runner.start(self.chat.id, offset=0, page_size=2)
        self.assertTrue(engine.entered.acquire(timeout=WAIT))

        again = runner.start(self.chat.id, offset=3, page_size=50)
        self.assertEqual((again.started_offset, again.page_size), (0, 2))
        self.assertTrue(first.is_active)

        engine.gate.release()
        engine.gate.release()
        runner.wait(self.chat.id, WAIT)

    def test_only_one_chat_runs_at_a_time(self):
        self.given_messages(("u1", "hello"))
        other = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=100, name="Other")
        )
        engine = GatedEngine()
        runner = self.runner(engine)
        runner.start(self.chat.id, offset=0, page_size=2)
        self.assertTrue(engine.entered.acquire(timeout=WAIT))

        with self.assertRaises(BusyError):
            runner.start(other.id, offset=0, page_size=2)

        engine.gate.release()
        runner.wait(self.chat.id, WAIT)
        # Free again once the first run ends.
        self.assertIs(
            runner.wait(other.id).state, RunState.IDLE
        )

    def test_an_engine_failure_ends_the_run_as_failed(self):
        self.given_messages(("u1", "hello"))
        runner = self.runner(FakeDecisionEngine(fail_with="checkpoint unavailable"))
        runner.start(self.chat.id, offset=0, page_size=2)
        status = runner.wait(self.chat.id, WAIT)

        self.assertIs(status.state, RunState.FAILED)
        self.assertIn("checkpoint unavailable", status.error)

    def test_an_unknown_chat_is_refused_before_a_run_starts(self):
        with self.assertRaises(ChatNotFoundError):
            self.runner().start(9999, offset=0, page_size=2)

    def test_a_chat_that_never_ran_is_idle(self):
        status = self.runner().status(self.chat.id)
        self.assertIs(status.state, RunState.IDLE)
        self.assertFalse(status.is_active)


if __name__ == "__main__":
    unittest.main()
