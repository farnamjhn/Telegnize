# What Telegnize measures

`GET /api/analytics/{chat_id}` returns four groups of figures: volume, and
then per participant **responsiveness**, **engagement**, and **expression**,
plus chat-level **rhythm** and **balance**.

## Read this first

These are **behavioural observations**, not measurements of a relationship.
They describe things anyone could count from the export — how fast someone
replied, who wrote first, which words appear — and stop there.

Three limits worth keeping in mind:

- **A marker count is about wording, not feeling.** "I love that restaurant"
  counts as an affection marker. A long, warm message using none of the listed
  words counts as nothing. The word lists are in
  [`domain/models/lexicons.py`](../domain/models/lexicons.py).
- **Asymmetry is not a verdict.** One person opening most conversations or
  replying more slowly is a fact about the transcript. People have jobs, time
  zones, and different relationships with their phone.
- **A chat is not the relationship.** Everything said in person, on a call, or
  in another app is missing from this data, and it may be where most of it
  happened.

If a number surprises you, read the messages behind it before concluding
anything.

## Volume

| Field | Meaning |
| --- | --- |
| `message_count`, `word_count`, `char_count` | Totals per participant |
| `message_share_percent`, `word_share_percent` | Share of the conversation |
| `avg_words_per_message` | How much they pack into one message |

Message share and word share can diverge sharply: someone who sends many short
fragments and someone who sends few long messages can carry equal weight.

## Responsiveness

How readily someone answers. Latency is measured against the message being
replied to when there is an explicit reply link, and otherwise against whatever
came directly before.

| Field | Meaning |
| --- | --- |
| `median_seconds` | The usual wait. Read this one first |
| `p90_seconds` | The slow tail — what being left waiting looks like |
| `avg_seconds` | Skewed upward by a few long gaps; kept for completeness |
| `reply_count` | Replies the median is computed from |
| `question_count` | Questions this person asked |
| `questions_answered_percent` | Share the other party took up **while still live** |

Uptake uses a one-hour window by default, not the 24-hour reply window.
Measured over a day, any active conversation answers everything eventually and
the figure pins at 100%, which tells you nothing.

## Engagement

Who carries the conversation.

| Field | Meaning |
| --- | --- |
| `opened_count`, `opened_percent` | Conversations started after a silence |
| `closed_count` | Conversations where they had the last word |
| `turn_count`, `avg_messages_per_turn` | Uninterrupted runs of their own messages |
| `double_text_percent` | Share of their messages that continued their own turn |
| `cold_closure_count`, `cold_closure_percent` | Whole messages that are a bare "ok" / "باشه" |
| `voice_message_count`, `media_count` | Non-text messages |

`double_text_percent` is high for anyone who thinks in fragments and presses
enter often. It is a style measure at least as much as a pursuit measure; it
carries more when the two participants differ sharply on it.

## Expression

Marker counts from the word lists, plus rates per thousand words. **Use the
rates, not the counts** — someone who writes twice as much has twice as much of
everything.

| Field | Meaning |
| --- | --- |
| `affection_per_1k_words` | Endearments, "miss", "love", `عزیزم`, `قربونت` |
| `gratitude_per_1k_words` | "thanks", `مرسی`, `ممنون` |
| `apology_per_1k_words` | "sorry", `ببخشید`, `شرمنده` |
| `emoji_per_1k_words` | Emoji characters |
| `exclamations_per_1k_words` | `!` and `！` |
| `collective_focus_percent` | Share of first-person words that are "we" not "I" |

Exclamation marks are a weak affect signal outside English-language chat — in
many conversations emoji carry all of it, and the exclamation rate sits at
zero while the emoji rate is high. Compare participants within one chat rather
than across chats.

`collective_focus_percent` is the "we" against "I" ratio that recurs in
text-psychology research. Read it as a description of how someone frames
things, not as a score.

## Rhythm

A **session** is a run of messages with no silence in it longer than the
session gap — roughly, one sitting.

| Field | Meaning |
| --- | --- |
| `session_count`, `avg_messages_per_session`, `avg_session_minutes` | Sitting sizes |
| `active_days`, `span_days`, `active_day_percent` | How much of the period had any contact |
| `longest_silence_days` | The longest the conversation went quiet |
| `late_night_percent` | Share sent between midnight and 05:00 |

## Balance

| Field | Meaning |
| --- | --- |
| `message_balance_percent`, `word_balance_percent`, `initiation_balance_percent` | 100 = even split, falling toward 0 as one person dominates |
| `response_time_ratio` | Slowest participant's median reply over the fastest's |

Balance figures are a normalised Shannon entropy over the participants' shares,
so they stay meaningful in a group chat where a two-way ratio would not.

## Tuning the windows

What counts as answering, as one sitting, or as a question still being live
depends on the conversation. All four thresholds are settings:

| Variable | Default | Controls |
| --- | --- | --- |
| `TELEGNIZE_REPLY_WINDOW_SECONDS` | 86400 | Gap still counted as answering an explicit reply |
| `TELEGNIZE_TURN_WINDOW_SECONDS` | 21600 | Gap still counted as answering the previous turn |
| `TELEGNIZE_SESSION_GAP_SECONDS` | 21600 | Silence that starts a new session |
| `TELEGNIZE_UPTAKE_WINDOW_SECONDS` | 3600 | How long a question stays live |

## How it is computed

Every figure comes from an aggregate query. Marker counts are derived on the
`Message` entity and written to columns as messages are stored, and turn
boundaries and sessions are window functions over the message table, so a chat
of any size is analysed in constant memory. See
[architecture.md](architecture.md).
