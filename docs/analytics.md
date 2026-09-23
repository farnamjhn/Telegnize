# What Telegnize measures

Telegnize reports two kinds of figure, and they are not equally trustworthy.

**Counted** figures come from arithmetic over timestamps and words. They are
exact: if it says someone replied in a median of 15 seconds, they did.
`GET /api/analytics/{chat_id}` returns these.

**Classified** figures come from a model reading each message. They are a
reading, and a reading can be wrong about any individual message.
`GET /api/assessments/{chat_id}` returns these, and every one of them should be
read against its `coverage_percent`.

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
| `latency_trend` | Median reply time period by period, oldest first |
| `latency_drift_percent` | Change from the first half of that series to the second |

### Latency drift

A single median hides when it changed. `latency_trend` gives one point per week
— per month for a chat spanning more than half a year — each with the
`reply_count` behind it, so a median resting on three replies is visible as
such.

`latency_drift_percent` is positive when someone is answering more slowly than
they were. Expect very large values when a conversation simply stops: a final
period where replies come hours apart instead of seconds will read in the
thousands of percent. The series is the thing to look at; the single number
only tells you which direction to look in.

Uptake uses a one-hour window by default, not the 24-hour reply window.
Measured over a day, any active conversation answers everything eventually and
the figure pins at 100%, which tells you nothing.

## Engagement

Who carries the conversation.

| Field | Meaning |
| --- | --- |
| `opened_count`, `opened_percent` | Conversations started after a silence |
| `closed_count` | Conversations where they had the last word |
| `turn_count`, `avg_messages_per_turn`, `avg_words_per_turn` | Uninterrupted runs of their own messages |
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
| `emoji_per_100_words` | Emoji characters. Per *hundred* words — they are frequent enough that per-thousand reads badly |
| `exclamations_per_1k_words` | `!` and `！` |
| `elongation_per_1k_words` | Stretched words: "soooo", `سلاممم` |
| `absolutism_percent` | Absolutist words as a share of everything they wrote |
| `collective_focus_percent` | Share of first-person words that are "we" not "I" |

`elongation` is counted on the text as sent, before normalization — normalizing
collapses runs of three characters, which is the whole point of normalizing and
would erase exactly what this measures.

`absolutism_percent` uses Al-Mosaiwi & Johnstone's absolutist dictionary,
unabridged, so it includes ordinary words like "all" and "must". That keeps the
rate comparable to published figures but means the absolute number is only
meaningful next to another participant in the same conversation.

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

## Classified figures: the assessment

`POST /api/assessments/{chat_id}` runs a question set over a page of messages;
`GET /api/assessments/{chat_id}` returns the aggregate.

### Cost — measure before you commit to a run

Assessment runs a model over every message, and it is expensive. How expensive
is not something this page can tell you: it depends on the device torch finds
(an Apple or NVIDIA GPU where there is one, otherwise the CPU), a machine under
sustained load throttles, and non-Latin text routes to a larger multilingual
checkpoint than English does.

So time one small page on the hardware you intend to use, then decide:

```bash
time curl -X POST "localhost:8000/api/assessments/1?offset=0&limit=5"
```

Time a page of mixed languages if the chat has them, because that is where the
two settings below bite.

The first call pays a one-off checkpoint load. Set
`TELEGNIZE_PRELOAD_DECISION_ENGINE=1` to take that at startup instead.

**Both routed checkpoints stay resident.** Laya routes by script and, left at
its own default, keeps one checkpoint in memory and rebuilds the other from
several hundred megabytes on disk whenever the script changes. In a chat that
mixes English with anything else that is not an edge case: on the Persian and
English export this was measured against, 42% of messages changed the routing
from the message before them, so 42% of them paid a checkpoint build before
they could be answered. `TELEGNIZE_RESIDENT_CHECKPOINTS` is 2 for that reason.
Turn it down to 1 only on a machine that cannot hold both.

**Repeated text is answered once.** Chat repeats itself — a third of the
messages in that same export said something an earlier message had already said
word for word, and one recurring two-emoji reply accounted for 2,943 of 42,465.
The engine sees only the sender and the text, so identical pairs are one
question; `TELEGNIZE_DECISION_CACHE_ENTRIES` answers from memory instead of
re-running the pass, and `0` turns that off.

The pass is **paged and resumable**: each POST works through `limit` messages
from `offset`, skips anything already answered, and returns `next_offset` and
`is_complete`. Answers are cached, so re-running a range costs nothing.

```bash
curl -X POST "localhost:8000/api/assessments/1?offset=0&limit=25"
```

**There is no requirement to assess a whole chat**, and usually no reason to. A
few hundred messages is enough to read a rate off, and `coverage_percent` keeps
the partial result honest.

| Field | Meaning |
| --- | --- |
| `positive_count`, `neutral_count`, `negative_count` | How each message read |
| `positivity_ratio` | Positive messages per negative one. `null` when nothing read negative |
| `bid_count`, `bids_met_count`, `bids_met_percent` | Reaching out, and whether the reply engaged |
| `criticism_count`, `defensiveness_count`, `contempt_count`, `friction_percent` | Friction, by kind |
| `repair_count`, `repair_percent` | Apologising, making peace, defusing |
| `avg_sarcasm_score` | 0 (straightforward) to 3 (heavily barbed) |
| `statement_count`, `closed_question_count`, `open_question_count` | What each message was doing |
| `curiosity_per_1k_words` | Open questions and self-disclosures per thousand words |

### What these borrow, and what they do not inherit

`positivity_ratio`, bids, the friction categories and repair attempts all name
constructs from **Gottman's** observational research on couples. That research
coded trained observers watching video of people in a room, over years, against
outcomes. A classifier reading chat text shares the vocabulary and none of the
validation.

So: the well-known 5:1 ratio is **not** a threshold to hold this number against.
A chat is a slice of a relationship that also happens in person, on calls, and
in silence; text strips tone; and the classifier is wrong about individual
messages. Use these to find stretches of conversation worth reading yourself,
not to conclude anything.

`bids_met_percent` is computed over bids that got a reply inside the page at
all, and in a two-person chat it describes how the *other* participant
responded. In a group chat the attribution is looser, because the reply may
come from anyone.

## Tuning the windows

What counts as answering, as one sitting, or as a question still being live
depends on the conversation. All four thresholds are settings:

| Variable | Default | Controls |
| --- | --- | --- |
| `TELEGNIZE_REPLY_WINDOW_SECONDS` | 86400 | Gap still counted as answering an explicit reply |
| `TELEGNIZE_TURN_WINDOW_SECONDS` | 21600 | Gap still counted as answering the previous turn |
| `TELEGNIZE_SESSION_GAP_SECONDS` | 21600 | Silence that starts a new session |
| `TELEGNIZE_UPTAKE_WINDOW_SECONDS` | 3600 | How long a question stays live |
| `TELEGNIZE_ASSESSMENT_PAGE_SIZE` | 200 | Messages assessed per call |

## How it is computed

Counted figures come from aggregate queries. Marker counts are derived on the
`Message` entity and written to columns as messages are stored, and turn
boundaries and sessions are window functions over the message table, so a chat
of any size is analysed in constant memory.

Classified figures are cached in the `decisions` table keyed by message and
question, and aggregated with a group-by joining back to the sender — so
reading an assessment costs one set of queries no matter how much has been
assessed. See [architecture.md](architecture.md).
