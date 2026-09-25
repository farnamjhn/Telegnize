import os
import unittest
from datetime import datetime, timedelta

from domain.models.analysis import Decision, DecisionTarget, DecisionType
from domain.models.chat import Chat
from domain.models.language import Language
from domain.models.message import ContentType, Message
from infrastructure.persistence.database import MEMORY_PATH, Database
from infrastructure.persistence.sqlite_chat_repository import SQLiteChatRepository
from infrastructure.persistence.sqlite_decision_repository import (
    SQLiteDecisionRepository,
)
from infrastructure.persistence.sqlite_message_repository import (
    SQLiteMessageRepository,
)

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)


def message(**overrides) -> Message:
    defaults = dict(
        id=0,
        telegram_msg_id=1,
        sender_id="u1",
        sender_name="Alice",
        timestamp=BASE_TIME,
        text="Hello World!",
    )
    return Message(**{**defaults, **overrides})


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.db = Database(MEMORY_PATH)
        self.messages = SQLiteMessageRepository(self.db)
        self.chats = SQLiteChatRepository(self.db)
        self.decisions = SQLiteDecisionRepository(self.db)

    def tearDown(self):
        self.db.close()


class TestMessagePersistence(RepositoryTestCase):
    def test_save_and_read_back(self):
        self.messages.save(
            message(telegram_msg_id=1001, content_type=ContentType.TEXT)
        )
        fetched = self.messages.get_by_id(1)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.telegram_msg_id, 1001)
        self.assertEqual(fetched.sender_name, "Alice")
        self.assertEqual(fetched.text, "Hello World!")
        self.assertIs(fetched.content_type, ContentType.TEXT)
        self.assertIsNone(fetched.reply_to_msg_id)

    def test_language_round_trips_as_enum(self):
        self.messages.save(message(text="سلام", language=Language.PERSIAN))
        self.assertIs(self.messages.get_by_id(1).language, Language.PERSIAN)

    def test_get_by_telegram_id_keeps_reply_link(self):
        self.messages.save(message(telegram_msg_id=2002, reply_to_msg_id=1001))
        fetched = self.messages.get_by_telegram_id(2002)
        self.assertEqual(fetched.reply_to_msg_id, 1001)

    def test_save_batch_reports_count_and_orders_by_time(self):
        written = self.messages.save_batch(
            [
                message(telegram_msg_id=1, timestamp=BASE_TIME + timedelta(hours=1)),
                message(telegram_msg_id=2, timestamp=BASE_TIME),
            ]
        )
        self.assertEqual(written, 2)
        listed = self.messages.list_messages()
        self.assertEqual([m.telegram_msg_id for m in listed], [2, 1])

    def test_save_batch_of_nothing_is_a_no_op(self):
        self.assertEqual(self.messages.save_batch([]), 0)

    def test_resaving_updates_rather_than_duplicates(self):
        self.messages.save(message(telegram_msg_id=500, sender_name="Original"))
        first = self.messages.get_by_telegram_id(500)

        self.messages.save(
            message(telegram_msg_id=500, sender_name="Updated", text="Updated text")
        )
        second = self.messages.get_by_telegram_id(500)

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.sender_name, "Updated")
        self.assertEqual(second.text, "Updated text")
        self.assertEqual(self.messages.count_by_chat(1), 1)

    def test_same_telegram_id_in_two_chats_stays_separate(self):
        other = self.chats.save(Chat(id=0, telegram_chat_id=7, name="Other"))
        self.messages.save(message(telegram_msg_id=42, chat_id=1, text="in one"))
        self.messages.save(message(telegram_msg_id=42, chat_id=other.id, text="in two"))

        self.assertEqual(self.messages.get_by_telegram_id(42, chat_id=1).text, "in one")
        self.assertEqual(
            self.messages.get_by_telegram_id(42, chat_id=other.id).text, "in two"
        )

    def test_pagination_and_sender_filter(self):
        self.messages.save_batch(
            [
                message(
                    telegram_msg_id=i,
                    sender_id="u1" if i % 2 else "u2",
                    timestamp=BASE_TIME + timedelta(minutes=i),
                )
                for i in range(1, 7)
            ]
        )
        page = self.messages.list_messages(limit=2, offset=2)
        self.assertEqual([m.telegram_msg_id for m in page], [3, 4])

        from_u1 = self.messages.list_messages(sender_id="u1")
        self.assertEqual([m.telegram_msg_id for m in from_u1], [1, 3, 5])

    def test_timeline_streams_in_order(self):
        self.messages.save_batch(
            [
                message(telegram_msg_id=2, timestamp=BASE_TIME + timedelta(minutes=5)),
                message(telegram_msg_id=1, timestamp=BASE_TIME),
            ]
        )
        timeline = list(self.messages.iter_chat_timeline(1))
        self.assertEqual([m.telegram_msg_id for m in timeline], [1, 2])

    def test_deleting_a_chat_cascades_to_its_messages(self):
        chat = self.chats.save(Chat(id=0, telegram_chat_id=99, name="Doomed"))
        self.messages.save(message(chat_id=chat.id))
        self.assertEqual(self.messages.count_by_chat(chat.id), 1)

        self.assertTrue(self.chats.delete(chat.id))
        self.assertEqual(self.messages.count_by_chat(chat.id), 0)


class TestMessageAggregates(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        # Alice asks at 10:00, Bob replies 60s later, Alice closes coldly at 10:02.
        self.messages.save_batch(
            [
                message(
                    telegram_msg_id=1,
                    sender_id="u1",
                    sender_name="Alice",
                    text="سلام، کجایی؟",
                    language=Language.PERSIAN,
                ),
                message(
                    telegram_msg_id=2,
                    sender_id="u2",
                    sender_name="Bob",
                    reply_to_msg_id=1,
                    timestamp=BASE_TIME + timedelta(seconds=60),
                    text="سلام، تو راهم",
                    language=Language.PERSIAN,
                ),
                message(
                    telegram_msg_id=3,
                    sender_id="u1",
                    sender_name="Alice",
                    reply_to_msg_id=2,
                    timestamp=BASE_TIME + timedelta(seconds=120),
                    text="باشه",
                    language=Language.PERSIAN,
                ),
            ]
        )

    def test_participant_totals_include_derived_counters(self):
        totals = {
            row["sender_id"]: row
            for row in self.messages.get_participant_totals(1)
        }
        self.assertEqual(totals["u1"]["message_count"], 2)
        self.assertEqual(totals["u1"]["question_count"], 1)
        self.assertEqual(totals["u1"]["cold_closure_count"], 1)
        self.assertEqual(totals["u2"]["message_count"], 1)

    def test_temporal_distributions(self):
        self.assertEqual(self.messages.get_hourly_distribution(1), {10: 3})
        self.assertEqual(self.messages.get_daily_distribution(1), {"Wednesday": 3})

    def test_language_distribution(self):
        self.assertEqual(self.messages.get_language_distribution(1), {"fa": 3})

    def test_language_distribution_excludes_textless_media(self):
        self.messages.save(
            message(
                telegram_msg_id=4,
                content_type=ContentType.STICKER,
                text="",
                language=Language.UNKNOWN,
            )
        )
        self.assertEqual(self.messages.get_language_distribution(1), {"fa": 3})

    def test_assessable_count_excludes_textless_media(self):
        self.messages.save(
            message(
                telegram_msg_id=4,
                content_type=ContentType.STICKER,
                text="",
                language=Language.UNKNOWN,
            )
        )
        self.assertEqual(self.messages.count_by_chat(1), 4)
        self.assertEqual(self.messages.count_assessable_by_chat(1), 3)

    def test_date_range(self):
        first, last = self.messages.get_date_range(1)
        self.assertEqual(first, BASE_TIME.isoformat(sep=" "))
        self.assertEqual(last, (BASE_TIME + timedelta(seconds=120)).isoformat(sep=" "))

    def test_reply_latency_is_measured_against_the_parent(self):
        latencies = self.messages.get_response_latencies(1)
        self.assertEqual(latencies["u2"], [60.0])
        self.assertEqual(latencies["u1"], [60.0])

    def test_self_replies_do_not_count_as_responses(self):
        self.messages.save(
            message(
                telegram_msg_id=4,
                sender_id="u1",
                reply_to_msg_id=3,
                timestamp=BASE_TIME + timedelta(seconds=180),
                text="و یه چیز دیگه",
            )
        )
        self.assertEqual(self.messages.get_response_latencies(1)["u1"], [60.0])

    def test_gaps_beyond_the_turn_window_are_ignored(self):
        self.messages.save(
            message(
                telegram_msg_id=5,
                sender_id="u2",
                timestamp=BASE_TIME + timedelta(hours=9),
                text="سلام دوباره",
            )
        )
        self.assertEqual(self.messages.get_response_latencies(1)["u2"], [60.0])

    def test_turn_taking_without_explicit_replies_is_still_timed(self):
        self.db.close()
        self.db = Database(MEMORY_PATH)
        self.messages = SQLiteMessageRepository(self.db)
        self.messages.save_batch(
            [
                message(telegram_msg_id=1, sender_id="u1"),
                message(
                    telegram_msg_id=2,
                    sender_id="u2",
                    timestamp=BASE_TIME + timedelta(seconds=30),
                ),
            ]
        )
        self.assertEqual(self.messages.get_response_latencies(1), {"u2": [30.0]})


class TestChatPersistence(RepositoryTestCase):
    def test_save_assigns_an_id_and_upserts_by_telegram_id(self):
        chat = self.chats.save(Chat(id=0, telegram_chat_id=123, name="Dana"))
        self.assertTrue(chat.is_persisted)

        again = self.chats.save(Chat(id=0, telegram_chat_id=123, name="Dana Renamed"))
        self.assertEqual(again.id, chat.id)
        self.assertEqual(self.chats.get_by_id(chat.id).name, "Dana Renamed")

    def test_lookup_and_listing(self):
        self.chats.save(Chat(id=0, telegram_chat_id=123, name="One"))
        self.assertIsNotNone(self.chats.get_by_telegram_id(123))
        self.assertIsNone(self.chats.get_by_telegram_id(404))
        # Row 1 is the reserved default chat.
        self.assertEqual(len(self.chats.list_all()), 2)

    def test_update_message_count(self):
        chat = self.chats.save(Chat(id=0, telegram_chat_id=5, name="Counted"))
        self.chats.update_message_count(chat.id, 42)
        self.assertEqual(self.chats.get_by_id(chat.id).total_messages, 42)

    def test_deleting_an_absent_chat_reports_false(self):
        self.assertFalse(self.chats.delete(9999))


class TestDecisionPersistence(RepositoryTestCase):
    def decision(self, **overrides) -> Decision:
        defaults = dict(
            target_type=DecisionTarget.MESSAGE,
            target_id=7,
            question_key="tone",
            decision_type=DecisionType.CHOICE,
            result_value="friendly",
            confidence=0.8,
            probabilities={"friendly": 0.8, "neutral": 0.2},
        )
        return Decision(**{**defaults, **overrides})

    def test_save_and_list(self):
        self.decisions.save(self.decision())
        stored = self.decisions.list_for_target(DecisionTarget.MESSAGE, 7)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].result_value, "friendly")
        self.assertEqual(stored[0].probabilities["friendly"], 0.8)

    def test_non_string_values_survive_the_round_trip(self):
        self.decisions.save_batch(
            [
                self.decision(question_key="is_conflict",
                              decision_type=DecisionType.NOUL, result_value=False),
                self.decision(question_key="warmth",
                              decision_type=DecisionType.SCORE, result_value=0.25),
            ]
        )
        stored = {
            d.question_key: d.result_value
            for d in self.decisions.list_for_target(DecisionTarget.MESSAGE, 7)
        }
        self.assertIs(stored["is_conflict"], False)
        self.assertEqual(stored["warmth"], 0.25)

    def test_re_answering_a_question_replaces_the_cached_answer(self):
        self.decisions.save(self.decision(result_value="friendly", confidence=0.5))
        self.decisions.save(self.decision(result_value="frustrated", confidence=0.9))
        stored = self.decisions.list_for_target(DecisionTarget.MESSAGE, 7)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].result_value, "frustrated")

    def test_targets_are_kept_apart(self):
        self.decisions.save(self.decision())
        self.decisions.save(self.decision(target_type=DecisionTarget.CHAT))
        self.assertEqual(len(self.decisions.list_for_target(DecisionTarget.CHAT, 7)), 1)
        self.assertEqual(
            len(self.decisions.list_for_target(DecisionTarget.MESSAGE, 7)), 1
        )


class TestFileBackedDatabase(unittest.TestCase):
    def test_schema_is_created_under_a_missing_directory(self):
        path = "temp_test_db/chat.db"
        db = Database(path)
        try:
            repo = SQLiteMessageRepository(db)
            repo.save(message(telegram_msg_id=999, text="File test"))
            self.assertIsNotNone(repo.get_by_telegram_id(999))
        finally:
            db.close()
            for leftover in (path, f"{path}-wal", f"{path}-shm"):
                if os.path.exists(leftover):
                    os.remove(leftover)
            if os.path.isdir("temp_test_db"):
                os.rmdir("temp_test_db")


if __name__ == "__main__":
    unittest.main()
