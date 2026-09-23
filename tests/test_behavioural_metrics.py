"""Tests for the circadian, control, composition and stance figures.

Each fixture is built so the expected number can be read off the messages by
hand: the point of these is that the arithmetic matches the definition in
``docs/analytics.md``, not that it runs.
"""

import unittest
from datetime import datetime, timedelta

from domain.models.chat import Chat
from domain.models.message import ContentType, Message
from tests.conftest import memory_container

BASE_TIME = datetime(2026, 5, 27, 10, 0, 0)
HOUR = 3600


class BehaviouralTestCase(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.service = self.container.analytics_service
        self.messages = self.container.message_repository
        self.chat = self.container.chat_repository.save(
            Chat(id=0, telegram_chat_id=77, name="Behaviour")
        )

    def tearDown(self):
        self.container.close()

    def given(self, *rows):
        """rows are (sender_id, offset_seconds, text) plus optional overrides."""
        self.messages.save_batch(
            [
                Message(
                    id=0,
                    chat_id=self.chat.id,
                    telegram_msg_id=index,
                    sender_id=row[0],
                    sender_name={"u1": "Alice", "u2": "Bob"}.get(row[0], row[0]),
                    timestamp=BASE_TIME + timedelta(seconds=row[1]),
                    text=row[2],
                    **(row[3] if len(row) > 3 else {}),
                )
                for index, row in enumerate(rows, start=1)
            ]
        )

    def analytics(self):
        return self.service.compute_chat_analytics(self.chat.id)

    def participant(self, sender_id):
        return next(
            p for p in self.analytics().participants if p.sender_id == sender_id
        )

    def run_nothing(self):
        """A no-op case body, so this fixture can be built on its own."""


class TestCircadian(BehaviouralTestCase):
    def test_night_owl_ratio_counts_midnight_to_five(self):
        # BASE_TIME is 10:00, so +14h is midnight and +17h is 03:00.
        self.given(
            ("u1", 0, "morning"),
            ("u1", 14 * HOUR, "still up"),
            ("u1", 17 * HOUR, "really still up"),
            ("u1", 20 * HOUR, "breakfast"),
        )
        alice = self.participant("u1")
        self.assertEqual(alice.circadian.night_owl_percent, 50.0)
        self.assertEqual(alice.circadian.hourly_distribution[0], 1)
        self.assertEqual(alice.circadian.hourly_distribution[3], 1)

    def test_five_am_is_not_night(self):
        # The window is midnight to 05:00; 05:00 itself belongs to the morning.
        self.given(("u1", 19 * HOUR, "five am"))
        self.assertEqual(self.participant("u1").circadian.night_owl_percent, 0.0)

    def test_peak_hour_is_the_busiest_one(self):
        self.given(("u1", 0, "a"), ("u1", 60, "b"), ("u1", 5 * HOUR, "c"))
        self.assertEqual(self.participant("u1").circadian.peak_hour, 10)

    def test_active_latency_ignores_the_gap_the_ordinary_one_counts(self):
        # Bob answers once in 30s and once after four hours. Four hours is
        # inside the six-hour turn window, so the ordinary median counts it and
        # is dragged to over two hours; the active window leaves it out.
        self.given(
            ("u1", 0, "you up?"),
            ("u2", 30, "yes"),
            ("u1", 60, "good"),
            ("u2", 60 + 4 * HOUR, "morning"),
        )
        bob = self.participant("u2")
        self.assertEqual(bob.responsiveness.reply_count, 2)
        self.assertGreater(bob.responsiveness.median_seconds, HOUR)

        self.assertEqual(bob.circadian.active_reply_count, 1)
        self.assertEqual(bob.circadian.active_median_seconds, 30.0)

    def test_whoever_breaks_a_long_silence_is_the_one_reviving_it(self):
        self.given(
            ("u1", 0, "hey"),
            ("u2", 60, "hi"),
            ("u1", 60 + 72 * HOUR, "you there?"),
        )
        self.assertEqual(self.participant("u1").circadian.revived_count, 1)
        self.assertEqual(self.participant("u1").circadian.revived_percent, 100.0)
        self.assertEqual(self.participant("u2").circadian.revived_count, 0)
        self.assertEqual(self.analytics().rhythm.silence_count, 1)

    def test_a_gap_under_the_threshold_is_not_a_silence(self):
        self.given(("u1", 0, "hey"), ("u2", 24 * HOUR, "sorry, busy day"))
        self.assertEqual(self.analytics().rhythm.silence_count, 0)


class TestControl(BehaviouralTestCase):
    def test_a_burst_of_three_counts_as_a_long_one(self):
        self.given(
            ("u1", 0, "one"), ("u1", 10, "two"), ("u1", 20, "three"),
            ("u2", 30, "ok"),
            ("u1", 40, "four"), ("u1", 50, "five"),
        )
        alice = self.participant("u1").control
        self.assertEqual(alice.burst_count, 2)
        self.assertEqual(alice.long_burst_count, 1)
        self.assertEqual(alice.long_burst_percent, 50.0)
        self.assertEqual(alice.longest_burst, 3)
        self.assertEqual(alice.avg_burst_size, 2.5)

        bob = self.participant("u2").control
        self.assertEqual(bob.burst_count, 1)
        self.assertEqual(bob.long_burst_count, 0)

    def test_the_last_word_goes_to_whoever_is_left_unanswered(self):
        # Two conversations three hours apart. Alice ends the first, Bob the
        # second, which is also the end of the chat.
        self.given(
            ("u1", 0, "hi"), ("u2", 60, "hello"), ("u1", 120, "night"),
            ("u1", 5 * HOUR, "morning"), ("u2", 5 * HOUR + 60, "hey"),
        )
        self.assertEqual(self.participant("u1").control.last_word_count, 1)
        self.assertEqual(self.participant("u2").control.last_word_count, 1)
        self.assertEqual(self.participant("u1").control.last_word_percent, 50.0)

    def test_messages_written_on_top_of_each_other_are_collisions(self):
        self.given(
            ("u1", 0, "so i was thinking"),
            ("u2", 5, "hey did you see"),
            ("u1", 40, "sorry go ahead"),
        )
        # Bob wrote 5s after Alice; Alice then took 35s, which is not a
        # collision. One each way is impossible — only Bob's counts.
        self.assertEqual(self.participant("u2").control.collision_count, 1)
        self.assertEqual(self.participant("u1").control.collision_count, 0)

    def test_a_burst_is_not_a_collision(self):
        self.given(("u1", 0, "one"), ("u1", 2, "two"), ("u1", 4, "three"))
        self.assertEqual(self.participant("u1").control.collision_count, 0)


class TestComposition(BehaviouralTestCase):
    def test_vocabulary_counts_unique_words(self):
        self.given(("u1", 0, "the cat sat on the mat"))
        alice = self.participant("u1").composition
        # six tokens, five distinct: "the" twice.
        self.assertEqual(alice.unique_word_count, 5)
        self.assertAlmostEqual(alice.type_token_ratio, 5 / 6, places=2)

    def test_repetition_reads_as_lower_diversity(self):
        self.given(
            ("u1", 0, "alpha beta gamma delta epsilon zeta"),
            ("u2", 60, "same same same same same same"),
        )
        self.assertGreater(
            self.participant("u1").composition.lexical_diversity,
            self.participant("u2").composition.lexical_diversity,
        )

    def test_media_is_counted_against_everything_sent(self):
        self.given(
            ("u1", 0, "look", {"content_type": ContentType.PHOTO}),
            ("u1", 60, "and this", {"content_type": ContentType.VOICE}),
            ("u1", 120, "plain text"),
            ("u1", 180, "more text"),
        )
        alice = self.participant("u1").composition
        self.assertEqual(alice.media_message_count, 2)
        self.assertEqual(alice.text_message_count, 2)
        self.assertEqual(alice.media_percent, 50.0)

    def test_voice_seconds_add_up_and_average_over_timed_notes_only(self):
        self.given(
            ("u1", 0, "", {"content_type": ContentType.VOICE, "duration_seconds": 30}),
            ("u1", 60, "", {"content_type": ContentType.VOICE, "duration_seconds": 90}),
        )
        alice = self.participant("u1").composition
        self.assertEqual(alice.voice_message_count, 2)
        self.assertEqual(alice.voice_seconds, 120)
        self.assertEqual(alice.timed_voice_count, 2)
        self.assertEqual(alice.avg_voice_seconds, 60.0)

    def test_voice_notes_with_no_duration_report_no_average(self):
        # A chat imported before durations were read: the notes are there and
        # their length is not. That is missing data, not zero-length notes.
        self.given(("u1", 0, "", {"content_type": ContentType.VOICE}))
        alice = self.participant("u1").composition
        self.assertEqual(alice.voice_message_count, 1)
        self.assertEqual(alice.timed_voice_count, 0)
        self.assertIsNone(alice.avg_voice_seconds)

    def test_links_are_counted_per_occurrence(self):
        self.given(("u1", 0, "see https://a.example and www.b.example"))
        self.assertEqual(self.participant("u1").composition.link_count, 2)


class TestStance(BehaviouralTestCase):
    def test_persian_questions_without_a_question_mark_still_count(self):
        self.given(
            ("u1", 0, "چرا اینجوری شد"),
            ("u1", 60, "خوبه"),
        )
        alice = self.participant("u1").stance
        self.assertEqual(alice.interrogative_count, 1)
        self.assertEqual(alice.questions_per_100_messages, 50.0)

    def test_a_question_mark_alone_is_enough(self):
        self.given(("u1", 0, "really?"))
        self.assertEqual(self.participant("u1").stance.interrogative_count, 1)

    def test_hedges_are_rated_against_words_written(self):
        self.given(("u1", 0, "maybe we should probably go"))
        alice = self.participant("u1").stance
        self.assertEqual(alice.hedge_count, 2)
        self.assertEqual(alice.hedge_per_1k_words, 400.0)

    def test_a_message_that_is_only_agreement_is_a_backchannel(self):
        self.given(
            ("u1", 0, "دقیقا"),
            ("u1", 60, "yeah"),
            ("u1", 120, "yeah but what about tuesday"),
            ("u1", 180, "a full sentence here"),
        )
        alice = self.participant("u1").stance
        self.assertEqual(alice.backchannel_count, 2)
        self.assertEqual(alice.backchannel_percent, 50.0)


class TestStyleMatching(BehaviouralTestCase):
    def lsm_for(self, *rows) -> float:
        """The chat-level LSM for one exchange, in a database of its own."""
        case = BehaviouralTestCase("run_nothing")
        case.setUp()
        try:
            case.given(*rows)
            return case.analytics().style_matching.lsm_percent
        finally:
            case.tearDown()

    def test_matched_function_words_score_higher_than_mismatched(self):
        matched = self.lsm_for(
            ("u1", 0, "i think we should go to the park with the dog"),
            ("u2", 60, "i think we could go to the park with the cat"),
        )
        mismatched = self.lsm_for(
            ("u1", 0, "i think that we should probably go to the park"),
            ("u2", 60, "tomato bread cheese olive salt"),
        )
        self.assertGreater(matched, mismatched)

    def test_it_reports_how_many_turn_pairs_it_saw(self):
        self.given(
            ("u1", 0, "one two"), ("u2", 60, "three four"), ("u1", 120, "five six"),
        )
        matching = self.analytics().style_matching
        self.assertEqual(matching.turn_pairs, 2)
        self.assertEqual(set(matching.by_category), {
            "personal_pronouns", "impersonal_pronouns", "articles", "prepositions",
            "auxiliary_verbs", "adverbs", "conjunctions", "negations", "quantifiers",
        })

    def test_a_chat_with_one_speaker_has_nothing_to_match(self):
        self.given(("u1", 0, "talking"), ("u1", 60, "to myself"))
        self.assertIsNone(self.analytics().style_matching.lsm_percent)
        self.assertEqual(self.analytics().style_matching.turn_pairs, 0)


if __name__ == "__main__":
    unittest.main()
