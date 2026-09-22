import unittest
from datetime import datetime, timedelta

from domain.errors import ChatNotFoundError
from domain.models.chat import Chat
from domain.models.language import Language
from domain.models.message import ContentType, Message
from tests.conftest import memory_container

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)
DAY = 24 * 3600


class AnalyticsTestCase(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.service = self.container.analytics_service
        self.messages = self.container.message_repository
        self.chat = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=1234, name="Test Analytics Chat")
        )

    def tearDown(self):
        self.container.close()

    def message(self, telegram_msg_id, sender_id, offset_seconds, text, **overrides):
        names = {"u1": "Alice", "u2": "Bob"}
        return Message(
            id=0,
            chat_id=self.chat.id,
            telegram_msg_id=telegram_msg_id,
            sender_id=sender_id,
            sender_name=names.get(sender_id, sender_id),
            timestamp=BASE_TIME + timedelta(seconds=offset_seconds),
            text=text,
            **overrides,
        )

    def analytics(self):
        return self.service.compute_chat_analytics(self.chat.id)

    def participant(self, sender_id):
        return next(
            p for p in self.analytics().participants if p.sender_id == sender_id
        )


class TestVolumeAndTiming(AnalyticsTestCase):
    def setUp(self):
        super().setUp()
        # Alice asks at 10:00, Bob replies after 60s, Alice closes coldly.
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "سلام، کجایی؟", language=Language.PERSIAN),
                self.message(
                    2, "u2", 60, "سلام، تو راهم",
                    reply_to_msg_id=1, language=Language.PERSIAN,
                ),
                self.message(
                    3, "u1", 120, "باشه", reply_to_msg_id=2, language=Language.PERSIAN
                ),
            ]
        )

    def test_volume_shares(self):
        analytics = self.analytics()
        self.assertEqual(analytics.total_messages, 3)
        self.assertEqual(len(analytics.participants), 2)

        alice = self.participant("u1")
        self.assertEqual(alice.message_count, 2)
        self.assertAlmostEqual(alice.message_share_percent, 66.67, places=2)
        self.assertGreater(alice.word_share_percent, 0)

    def test_participants_are_ordered_by_volume(self):
        self.assertEqual(
            [p.sender_id for p in self.analytics().participants], ["u1", "u2"]
        )

    def test_responsiveness(self):
        bob = self.participant("u2").responsiveness
        self.assertEqual(bob.avg_seconds, 60.0)
        self.assertEqual(bob.median_seconds, 60.0)
        self.assertEqual(bob.p90_seconds, 60.0)
        self.assertEqual(bob.reply_count, 1)

    def test_questions_asked_and_taken_up(self):
        alice = self.participant("u1").responsiveness
        self.assertEqual(alice.question_count, 1)
        self.assertEqual(alice.questions_answered_count, 1)
        self.assertEqual(alice.questions_answered_percent, 100.0)

    def test_cold_closures(self):
        alice = self.participant("u1").engagement
        self.assertEqual(alice.cold_closure_count, 1)
        self.assertEqual(alice.cold_closure_percent, 50.0)

    def test_temporal_and_language_breakdowns(self):
        analytics = self.analytics()
        self.assertEqual(analytics.hourly_distribution, {10: 3})
        self.assertEqual(analytics.daily_distribution, {"Wednesday": 3})
        self.assertEqual(analytics.language_breakdown, {"fa": 3})
        self.assertEqual(analytics.date_range_start, BASE_TIME)
        self.assertEqual(analytics.avg_response_time_seconds, 60.0)


class TestUnansweredQuestions(AnalyticsTestCase):
    def test_a_question_nobody_picks_up_lowers_the_uptake_rate(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "are you coming?"),
                self.message(2, "u2", 60, "yes"),
                self.message(3, "u1", 120, "what time?"),  # never answered
            ]
        )
        alice = self.participant("u1").responsiveness
        self.assertEqual(alice.question_count, 2)
        self.assertEqual(alice.questions_answered_count, 1)
        self.assertEqual(alice.questions_answered_percent, 50.0)

    def test_an_answer_that_arrives_days_later_does_not_count(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "are you coming?"),
                self.message(2, "u2", 3 * DAY, "sorry, missed this"),
            ]
        )
        self.assertEqual(
            self.participant("u1").responsiveness.questions_answered_count, 0
        )


class TestTurnTaking(AnalyticsTestCase):
    def setUp(self):
        super().setUp()
        # Alice writes three times in a row before Bob says anything.
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "hey"),
                self.message(2, "u1", 10, "you there"),
                self.message(3, "u1", 20, "hello"),
                self.message(4, "u2", 60, "here"),
            ]
        )

    def test_double_texting_is_counted(self):
        alice = self.participant("u1").engagement
        self.assertEqual(alice.turn_count, 1)
        self.assertEqual(alice.avg_messages_per_turn, 3.0)
        # Two of Alice's three messages continued her own turn.
        self.assertAlmostEqual(alice.double_text_percent, 66.67, places=2)

    def test_answering_promptly_is_not_double_texting(self):
        bob = self.participant("u2").engagement
        self.assertEqual(bob.double_text_percent, 0.0)
        self.assertEqual(bob.avg_messages_per_turn, 1.0)


class TestInitiation(AnalyticsTestCase):
    def setUp(self):
        super().setUp()
        # Three sittings; Alice opens two of them, Bob one.
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "morning"),
                self.message(2, "u2", 120, "morning!"),
                self.message(3, "u1", DAY, "hey again"),
                self.message(4, "u2", DAY + 60, "hi"),
                self.message(5, "u2", 3 * DAY, "you around?"),
                self.message(6, "u1", 3 * DAY + 60, "yep"),
            ]
        )

    def test_who_starts_conversations(self):
        self.assertEqual(self.participant("u1").engagement.opened_count, 2)
        self.assertEqual(self.participant("u2").engagement.opened_count, 1)
        self.assertAlmostEqual(
            self.participant("u1").engagement.opened_percent, 66.67, places=2
        )

    def test_who_has_the_last_word(self):
        self.assertEqual(self.participant("u2").engagement.closed_count, 2)
        self.assertEqual(self.participant("u1").engagement.closed_count, 1)

    def test_rhythm_describes_the_sittings(self):
        rhythm = self.analytics().rhythm
        self.assertEqual(rhythm.session_count, 3)
        self.assertEqual(rhythm.avg_messages_per_session, 2.0)
        self.assertEqual(rhythm.active_days, 3)
        self.assertEqual(rhythm.longest_silence_days, 2.0)

    def test_initiation_balance_reflects_the_split(self):
        balance = self.analytics().balance
        self.assertGreater(balance.initiation_balance_percent, 80)
        self.assertLess(balance.initiation_balance_percent, 100)


class TestExpression(AnalyticsTestCase):
    def setUp(self):
        super().setUp()
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "I love you so much!! ❤️😊"),
                self.message(2, "u2", 60, "thanks, sorry I was late"),
                self.message(3, "u1", 120, "we should go together, our plan"),
            ]
        )

    def test_marker_counts(self):
        alice = self.participant("u1").expression
        self.assertEqual(alice.affection_count, 1)
        self.assertEqual(alice.emoji_count, 2)
        self.assertEqual(alice.exclamation_count, 2)

        bob = self.participant("u2").expression
        self.assertEqual(bob.gratitude_count, 1)
        self.assertEqual(bob.apology_count, 1)

    def test_rates_normalise_for_verbosity(self):
        alice = self.participant("u1")
        expected = round(alice.expression.affection_count / alice.word_count * 1000, 2)
        self.assertEqual(alice.expression.affection_per_1k_words, expected)
        self.assertGreater(expected, 0)

    def test_the_same_marker_count_rates_lower_in_a_wordier_writer(self):
        self.messages.save(
            self.message(4, "u2", 180, "love " + " ".join(["word"] * 200))
        )
        alice = self.participant("u1").expression
        bob = self.participant("u2").expression
        self.assertEqual(alice.affection_count, bob.affection_count)
        self.assertGreater(alice.affection_per_1k_words, bob.affection_per_1k_words)

    def test_collective_focus_weighs_we_against_i(self):
        alice = self.participant("u1").expression
        # "I" once, then "we" and "our".
        self.assertEqual(alice.self_reference_count, 1)
        self.assertEqual(alice.collective_reference_count, 2)
        self.assertAlmostEqual(alice.collective_focus_percent, 66.67, places=2)

    def test_collective_focus_is_absent_without_first_person_words(self):
        self.messages.save(self.message(9, "u3", 300, "sounds good"))
        self.assertIsNone(self.participant("u3").expression.collective_focus_percent)

    def test_persian_markers_are_counted_too(self):
        self.messages.save(self.message(9, "u3", 300, "عزیزم دلم برات تنگ شده"))
        self.assertEqual(self.participant("u3").expression.affection_count, 2)


class TestRhythm(AnalyticsTestCase):
    def test_late_night_share(self):
        offset = int((datetime(2026, 5, 27, 1, 0, 0) - BASE_TIME).total_seconds())
        self.messages.save_batch(
            [
                self.message(1, "u1", offset, "still awake?"),
                self.message(2, "u2", offset + 60, "yeah"),
                self.message(3, "u1", 0, "afternoon message"),
                self.message(4, "u2", 60, "another one"),
            ]
        )
        self.assertEqual(self.analytics().rhythm.late_night_percent, 50.0)

    def test_a_chat_inside_one_day_spans_one_day(self):
        self.messages.save(self.message(1, "u1", 0, "hi"))
        rhythm = self.analytics().rhythm
        self.assertEqual(rhythm.span_days, 1)
        self.assertEqual(rhythm.active_days, 1)
        self.assertEqual(rhythm.active_day_percent, 100.0)

    def test_a_sparse_chat_has_a_low_active_day_ratio(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "hi"),
                self.message(2, "u2", 9 * DAY, "hello again"),
            ]
        )
        rhythm = self.analytics().rhythm
        self.assertEqual(rhythm.active_days, 2)
        self.assertEqual(rhythm.span_days, 9)
        self.assertEqual(rhythm.longest_silence_days, 9.0)
        self.assertLess(rhythm.active_day_percent, 25)


class TestBalance(AnalyticsTestCase):
    def test_an_even_split_scores_100(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "one two three"),
                self.message(2, "u2", 60, "four five six"),
            ]
        )
        balance = self.analytics().balance
        self.assertEqual(balance.message_balance_percent, 100.0)
        self.assertEqual(balance.word_balance_percent, 100.0)

    def test_one_sided_talk_scores_low(self):
        self.messages.save_batch(
            [self.message(i, "u1", i * 60, "talking") for i in range(1, 20)]
            + [self.message(99, "u2", 2000, "ok")]
        )
        self.assertLess(self.analytics().balance.message_balance_percent, 35)

    def test_a_single_participant_is_reported_as_even(self):
        self.messages.save(self.message(1, "u1", 0, "alone here"))
        self.assertEqual(self.analytics().balance.message_balance_percent, 100.0)

    def test_response_time_ratio_compares_the_two_paces(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "hi"),
                self.message(2, "u2", 10, "hey"),       # Bob answers in 10s
                self.message(3, "u1", 110, "how are you"),  # Alice answers in 100s
                self.message(4, "u2", 120, "good"),     # Bob answers in 10s
                self.message(5, "u1", 220, "nice"),     # Alice answers in 100s
            ]
        )
        self.assertEqual(self.analytics().balance.response_time_ratio, 10.0)


class TestMediaAndEdgeCases(AnalyticsTestCase):
    def test_voice_and_media_are_counted_apart_from_text(self):
        self.messages.save_batch(
            [
                self.message(1, "u1", 0, "", content_type=ContentType.VOICE),
                self.message(2, "u1", 60, "", content_type=ContentType.PHOTO),
                self.message(3, "u1", 120, "text one"),
            ]
        )
        engagement = self.participant("u1").engagement
        self.assertEqual(engagement.voice_message_count, 1)
        self.assertEqual(engagement.media_count, 1)

    def test_an_empty_chat_reports_zeroes_rather_than_failing(self):
        analytics = self.analytics()
        self.assertEqual(analytics.total_messages, 0)
        self.assertEqual(analytics.participants, [])
        self.assertIsNone(analytics.avg_response_time_seconds)
        self.assertEqual(analytics.rhythm.session_count, 0)

    def test_an_unknown_chat_raises(self):
        with self.assertRaises(ChatNotFoundError):
            self.service.compute_chat_analytics(9999)


if __name__ == "__main__":
    unittest.main()
