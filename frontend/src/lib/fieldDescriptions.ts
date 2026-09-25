export interface FieldDefinition {
  key: string;
  label: string;
  short: string;
  description: string;
  formula?: string;
  interpretation?: string;
  caveat?: string;
}

export const ANALYTICS_FIELDS: Record<string, FieldDefinition[]> = {
  overview: [
    {
      key: "avg_reply",
      label: "Average Reply",
      short: "Arithmetic mean of reply times across all participants.",
      description:
        "The mathematical average of all response times across every participant in the chat.",
      formula: "Σ(reply latency) / count(replies)",
      interpretation:
        "Gives an overall sense of conversation pacing, but is heavily skewed upward by overnight gaps and long multi-day silences.",
      caveat:
        "Always read the Median reply under Responsiveness first. The average is dragged upward by a few long gaps and does not reflect what typical chat response time feels like.",
    },
    {
      key: "busiest_hour",
      label: "Busiest Hour",
      short: "The hour of the day with the highest total message volume.",
      description:
        "Aggregates all messages across the entire chat history by hour of day (0–23) and identifies the peak activity window.",
      interpretation:
        "Identifies when chat activity naturally clusters, reflecting common free time or routine conversation hours.",
    },
    {
      key: "busiest_day",
      label: "Busiest Day",
      short: "The day of the week with the most messages sent.",
      description:
        "Aggregates messages by day of the week to reveal weekly patterns in conversation volume.",
      interpretation:
        "Shows whether the conversation is primarily weekday-driven or weekend-driven.",
    },
  ],
  rhythm: [
    {
      key: "sessions",
      label: "Sessions",
      short: "Continuous runs of conversation with no long silences.",
      description:
        "A session is an uninterrupted run of messages where no gap between consecutive messages exceeds the session window (default 6 hours). Roughly corresponds to 'one sitting'.",
      formula: "Gap between messages ≤ 6 hours",
      interpretation:
        "Shows how many distinct conversation sittings took place over the chat's lifetime.",
    },
    {
      key: "typical_session",
      label: "Typical Session",
      short: "Average duration of a single conversation sitting.",
      description:
        "The average time elapsed (in minutes) from the first message of a session to its last message.",
      formula: "Σ(session duration) / count(sessions)",
      interpretation:
        "Distinguishes between rapid, frequent check-ins and extended, long-form conversation sittings.",
    },
    {
      key: "active_days",
      label: "Active Days",
      short: "Days with at least one message exchanged.",
      description:
        "The count and percentage of calendar days within the chat span on which at least one message was sent.",
      formula: "Count(calendar days with ≥1 message) / total span days",
      interpretation:
        "Indicates daily consistency and continuity of contact versus intermittent, sporadic bursts.",
    },
    {
      key: "longest_silence",
      label: "Longest Silence",
      short: "The maximum number of consecutive days with zero messages.",
      description:
        "Measures the largest quiet gap between any two messages in the chat history.",
      interpretation:
        "Shows the greatest historical pause or disconnection before conversation resumed.",
    },
    {
      key: "late_night",
      label: "Late Night",
      short: "Share of messages sent between midnight and 05:00.",
      description:
        "Calculates the percentage of all messages across the entire chat sent during nocturnal hours.",
      formula: "Messages (00:00–05:00) / total messages × 100%",
      interpretation:
        "Reflects how much conversation occurs during late hours, often linked to personal or informal intimacy.",
      caveat:
        "This chat-wide figure averages all participants together. Two people with opposing schedules will produce a flat curve. Check Body Clock for individual nocturnal habits.",
    },
    {
      key: "silences",
      label: "Silences (>48h)",
      short: "Total count of gaps longer than 48 hours.",
      description:
        "Counts instances where the conversation went completely silent for more than 48 hours — indicating the chat stopped rather than merely paused.",
      formula: "Gap between messages > 48 hours",
      interpretation:
        "High counts indicate an episodic or sporadic chat pattern. Check 'Revived' under Circadian to see who restarts the chat after these silences.",
    },
  ],
  balance: [
    {
      key: "message_balance",
      label: "Message Balance",
      short: "How evenly total message count is distributed among participants.",
      description:
        "Normalized Shannon entropy calculated over the participants' message counts. 100% indicates an exactly equal split; falls toward 0% as one person dominates.",
      formula: "-Σ(p_i ln p_i) / ln(N) where p_i is message share",
      interpretation:
        "Unlike a simple two-way ratio, normalized Shannon entropy remains statistically meaningful in group chats with any number of participants.",
      caveat:
        "Message balance and word balance can diverge sharply: someone sending many short fragments can balance someone sending a few long paragraphs.",
    },
    {
      key: "word_balance",
      label: "Word Balance",
      short: "How evenly total word count is shared among participants.",
      description:
        "Normalized Shannon entropy calculated over the participants' word counts. 100% means equal word output; 0% means total dominance.",
      formula: "-Σ(w_i ln w_i) / ln(N) where w_i is word share",
      interpretation:
        "Measures the real balance of conversational 'airtime' and intellectual or narrative contribution.",
    },
    {
      key: "initiation_balance",
      label: "Initiation Balance (Who Opens)",
      short: "How evenly conversation starts after silences are shared.",
      description:
        "Normalized Shannon entropy calculated over who sends the first message after a silence (>6 hours).",
      formula: "-Σ(o_i ln o_i) / ln(N) where o_i is opened sessions share",
      interpretation:
        "100% means both parties initiate conversations equally. Low scores mean one person carries the initiative of reaching out.",
      caveat:
        "Asymmetry here is not necessarily emotional distance: one person may wake earlier, have fixed breaks, or work a schedule that naturally prompts outreach.",
    },
    {
      key: "response_time_ratio",
      label: "Reply-Time Ratio",
      short: "Ratio of the slowest median reply to the fastest median reply.",
      description:
        "Calculated as the slowest participant's median reply time divided by the fastest participant's median reply time.",
      formula: "max(median_reply) / min(median_reply)",
      interpretation:
        "1.00× represents identical typical response pacing. Values of 2.00× or 3.00× indicate that one participant consistently waits two or three times longer for replies than the other.",
    },
  ],
  style_matching: [
    {
      key: "lsm_percent",
      label: "LSM (Linguistic Style Matching)",
      short: "Ireland & Pennebaker's function-word convergence across adjacent turns.",
      description:
        "Calculates how closely participants subconsciously mirror each other's use of function words (articles, prepositions, pronouns, conjunctions, auxiliary verbs, etc.) across adjacent turn pairs.",
      formula: "Mean of (1 - |a - b| / (a + b)) across 9 function word classes",
      interpretation:
        "Higher convergence indicates high mutual attentiveness and conversational coordination.",
      caveat:
        "LSM increases with engagement of ANY kind — including intense disagreements and arguments. It is NOT a measure of liking or relationship health. Furthermore, Persian function words differ from English, so this figure should only be tracked over time within the same chat, never compared across chats.",
    },
    {
      key: "by_category",
      label: "Function-Word Categories",
      short: "Convergence breakdown across Ireland & Pennebaker's 9 grammatical classes.",
      description:
        "Evaluates stylistic similarity across personal pronouns, impersonal pronouns, articles, prepositions, auxiliary verbs, adverbs, conjunctions, negations, and quantifiers.",
      interpretation:
        "Shows which structural elements of speech are being mirrored most closely.",
    },
    {
      key: "turn_pairs",
      label: "Turn Pairs",
      short: "Number of adjacent turn transitions evaluated.",
      description:
        "Count of adjacent turns by different participants over which the style matching average was calculated.",
    },
  ],
  latency_trend: [
    {
      key: "latency_trend",
      label: "Latency Trend",
      short: "Periodic median reply times over weeks or months.",
      description:
        "Breaks down the timeline into weekly periods (or monthly for chats spanning >6 months) and calculates the median reply latency for each period.",
      interpretation:
        "Shows whether communication is speeding up, remaining steady, or slowing down over months.",
      caveat:
        "A median resting on only 2 or 3 replies moves very easily. Always check the reply count tooltip on each point.",
    },
    {
      key: "drift",
      label: "Latency Drift",
      short: "Percentage change in median reply latency from first half to second half.",
      description:
        "Compares the median reply latency of the first half of the timeline with that of the second half.",
      formula: "(median_second_half - median_first_half) / median_first_half × 100%",
      interpretation:
        "Positive (+) indicates responses have slowed down over time. Negative (-) indicates responses have sped up.",
      caveat:
        "If a conversation naturally tapered off or ended with a few distant replies, drift can read in the thousands of percent. Always inspect the Latency Trend chart.",
    },
  ],
  body_clock: [
    {
      key: "hourly_distribution",
      label: "Hourly Distribution",
      short: "Messages sent by hour of day (0–23).",
      description:
        "Each participant's individual message volume plotted across the 24 hours of the day.",
      interpretation:
        "Reveals daily personal routines, active working hours, and sleep schedules.",
    },
    {
      key: "night",
      label: "Night Owl %",
      short: "Share of messages sent between midnight and 05:00.",
      description:
        "The percentage of this participant's messages sent between 00:00 and 05:00.",
      formula: "Messages (00:00–05:00) / total messages × 100%",
      interpretation:
        "Exposes nocturnal habits that would otherwise be blurred when averaging participants together.",
    },
    {
      key: "peak",
      label: "Peak Hour",
      short: "The single hour when this participant writes most.",
      description:
        "Identifies the hour of day with the highest message count for this participant.",
      interpretation:
        "Useful for understanding when someone is most available and responsive.",
    },
  ],
  volume: [
    {
      key: "messages",
      label: "Messages",
      short: "Total messages sent by this participant.",
      description: "Count of all messages sent by this person in the chat.",
    },
    {
      key: "share",
      label: "Message Share",
      short: "Percentage of total messages sent by this participant.",
      description: "Participant's message count divided by total chat messages.",
      formula: "participant_messages / total_messages × 100%",
    },
    {
      key: "words",
      label: "Words",
      short: "Total words written by this participant.",
      description: "Word count calculated across all text messages.",
    },
    {
      key: "wordShare",
      label: "Word Share",
      short: "Percentage of total words written by this participant.",
      description: "Participant's word count divided by total chat words.",
      formula: "participant_words / total_words × 100%",
    },
    {
      key: "perMessage",
      label: "Words / msg",
      short: "Average words packed into a single message.",
      description: "Total word count divided by total message count for each participant.",
      formula: "word_count / message_count",
      interpretation:
        "Reveals communication style: low values (e.g. 2–5 words) indicate rapid fragment texting; higher values (15+ words) indicate composed, paragraph-style messaging.",
      caveat:
        "When two participants differ sharply, message share and word share will diverge: one person may send 70% of messages but only 40% of words.",
    },
    {
      key: "chars",
      label: "Characters",
      short: "Total character count written by this participant.",
      description: "Sum of characters across all text messages sent.",
    },
  ],
  responsiveness: [
    {
      key: "median",
      label: "Median Reply",
      short: "The typical response wait time within a 6-hour window.",
      description:
        "The 50th percentile of reply times. Measures the gap between a message and the response, capping gaps at 6 hours.",
      formula: "50th percentile of reply latency (window ≤ 6h)",
      interpretation:
        "The single most reliable measure of response speed. Resists distortion from overnight gaps and multi-hour pauses.",
    },
    {
      key: "p90",
      label: "p90 (Slow Tail)",
      short: "The 90th percentile of reply latency.",
      description:
        "Nine out of ten replies arrive faster than this figure; the remaining 10% take longer.",
      formula: "90th percentile of reply latency",
      interpretation:
        "Represents what being left waiting actually looks like during slower moments.",
    },
    {
      key: "avg",
      label: "Average Reply",
      short: "Arithmetic mean reply latency.",
      description:
        "Sum of all reply delays divided by reply count. Skewed upward by outliers.",
      caveat:
        "A few multi-hour delays pull this figure upward significantly. Read the median instead.",
    },
    {
      key: "replies",
      label: "Replies",
      short: "Number of eligible replies the median is computed from.",
      description:
        "Count of message reply pairs inside the 6-hour response window.",
    },
    {
      key: "asked",
      label: "Questions (Punctuation)",
      short: "Questions explicitly ending with '?' or '؟'.",
      description:
        "Count of messages containing standard question mark punctuation. Compare with Questions under Stance, which also identifies question words.",
    },
    {
      key: "answered",
      label: "Answered Live",
      short: "Questions answered while still live within a 1-hour window.",
      description:
        "The proportion of questions that received a response within 1 hour.",
      formula: "Questions replied to within 3,600s / total questions asked",
      interpretation:
        "Measures active conversational uptake. Measured over a standard 24-hour window, any active chat answers almost everything and pins at 100%, which conceals real responsiveness.",
    },
    {
      key: "drift",
      label: "Latency Drift",
      short: "Percentage change in median reply latency from first half to second half.",
      description:
        "Compares the median reply latency of the first half of the timeline with that of the second half.",
      formula: "(median_second_half - median_first_half) / median_first_half × 100%",
      interpretation:
        "Positive (+) indicates responses have slowed down over time. Negative (-) indicates responses have sped up.",
      caveat:
        "If a conversation naturally tapered off or ended with a few distant replies, drift can read in the thousands of percent. Always inspect the Latency Trend chart.",
    },
  ],
  circadian: [
    {
      key: "night",
      label: "Night Owl %",
      short: "Share of messages sent between midnight and 05:00.",
      description:
        "Individual nocturnal messaging proportion for this participant.",
      formula: "Messages (00:00–05:00) / participant total messages",
      interpretation:
        "Unlike the chat-wide figure, this exposes individual circadian asymmetry (e.g. one person sleeping while the other texts).",
    },
    {
      key: "peak",
      label: "Peak Hour",
      short: "Hour of day when this participant writes most.",
      description:
        "The single hour of the day (0–23) with the highest message volume for this participant.",
    },
    {
      key: "activeMedian",
      label: "Active Reply (Median)",
      short: "Reply time excluding gaps longer than 2 hours.",
      description:
        "Filters out gaps over 2 hours to measure response latency while the conversation is live.",
      formula: "Median latency where gap ≤ 7,200s",
      interpretation:
        "Describes attentiveness rather than availability. Unfiltered median includes sleep and workday pauses; active reply isolates live chat speed.",
      caveat:
        "Will routinely disagree with the median under Responsiveness. Both are correct answers to different questions.",
    },
    {
      key: "activeP90",
      label: "Active p90",
      short: "The 90th percentile of live replies (under 2 hours).",
      description:
        "The slow tail inside active conversation sessions.",
      formula: "90th percentile where gap ≤ 7,200s",
      interpretation:
        "Shows the outer wait time experienced when both parties are actively chatting.",
    },
    {
      key: "activeCount",
      label: "Live Replies",
      short: "Count of replies within the 2-hour active window.",
      description:
        "Number of reply pairs that occurred within 2 hours of the previous message.",
    },
    {
      key: "revived",
      label: "Revived",
      short: "Silences over 48 hours ended by this participant.",
      description:
        "Counts how many long silences (>48 hours) this participant was the one to break.",
      formula: "Count of silences (>48h) where this person sent the next message",
      interpretation:
        "Highlights who steps up to resurrect a conversation that had completely stopped.",
      caveat:
        "Usually a very small sample size in most chats. Check the total silence count under Rhythm before drawing conclusions.",
    },
  ],
  engagement: [
    {
      key: "opened",
      label: "Opened",
      short: "Conversations started after a silence (>6 hours).",
      description:
        "The number and percentage of conversation sessions this participant initiated.",
      interpretation:
        "Reflects initiative in maintaining active contact.",
    },
    {
      key: "closed",
      label: "Closed",
      short: "Conversations where this person had the last word.",
      description:
        "Count of sessions where this participant sent the final message before a 6-hour silence.",
      interpretation:
        "Shows who frequently finishes conversations or is left unanswered at session boundaries.",
    },
    {
      key: "turns",
      label: "Turns",
      short: "Uninterrupted message sequences sent by this person.",
      description:
        "A conversational turn is a contiguous block of messages sent by one participant before the other replies.",
      formula: "Count of contiguous sender runs",
      interpretation:
        "Provides the baseline unit of conversation flow.",
    },
    {
      key: "perTurn",
      label: "Msgs / turn",
      short: "Average messages per conversational turn.",
      description:
        "Average number of messages sent consecutively by this participant before the other replies.",
      formula: "message_count / turn_count",
    },
    {
      key: "wordsPerTurn",
      label: "Words / turn",
      short: "Average words packed into a single turn.",
      description:
        "Average word count delivered in an uninterrupted turn.",
      formula: "word_count / turn_count",
    },
    {
      key: "double",
      label: "Double-Text %",
      short: "Share of messages continuing the participant's own turn.",
      description:
        "The percentage of sent messages that followed another message from the same person without waiting for a reply.",
      formula: "(messages - turns) / messages × 100%",
      interpretation:
        "High for fragmented thinkers who press enter frequently. Can indicate conversational pursuit when highly asymmetric.",
      caveat:
        "Primarily a typing habit rather than a psychological signal. It carries meaning mostly when one person double-texts heavily and the other never does.",
    },
    {
      key: "cold",
      label: "Cold Closures",
      short: "Messages consisting of a bare minimal acknowledgement.",
      description:
        "Whole messages that consist only of minimal closure words (e.g. 'ok', 'باشه', 'k', 'cool', 'sure').",
      interpretation:
        "Shows how often a participant terminates conversational momentum with a minimal response.",
    },
    {
      key: "voice",
      label: "Voice Messages",
      short: "Count of voice notes sent.",
      description: "Total voice message recordings sent by this participant.",
    },
    {
      key: "media",
      label: "Media",
      short: "Count of photos, videos, stickers, and files.",
      description: "Non-text multimedia items sent by this participant.",
    },
  ],
  control: [
    {
      key: "turns",
      label: "Turns",
      short: "Uninterrupted message runs.",
      description: "Contiguous sequences of messages before the other person replies.",
    },
    {
      key: "bursts",
      label: "Bursts 3+",
      short: "Turns of 3 or more messages before a reply.",
      description:
        "Counts turns where the participant sent three or more messages in a row before the other person answered.",
      formula: "Turns with message count ≥ 3",
      interpretation:
        "Reflects message chunking and pacing habits.",
      caveat:
        "A burst of 3+ is a pacing style: some people send four short messages where another sends one paragraph. It is NOT anxiety or neediness.",
    },
    {
      key: "longest",
      label: "Longest Burst",
      short: "Maximum consecutive messages sent without an intervening reply.",
      description:
        "The single longest uninterrupted sequence of messages sent by this participant.",
      interpretation:
        "Highlights monologue moments, storytelling, or rapid-fire text bursts.",
    },
    {
      key: "avgBurst",
      label: "Msgs / burst",
      short: "Average message count in uninterrupted runs.",
      description: "Average number of messages sent in each continuous burst.",
      formula: "messages / burst_count",
    },
    {
      key: "lastWord",
      label: "Last Word",
      short: "Conversations where this person's message was last at a 3-hour silence.",
      description:
        "Measures instances where this participant sent the final message followed by at least 3 hours of silence.",
      formula: "Final message in a turn preceding a gap ≥ 3 hours",
      interpretation:
        "Tighter than the 6-hour session closure. Measures who is left holding the unanswered message in practice.",
    },
    {
      key: "collisions",
      label: "Collisions",
      short: "Messages sent within 30 seconds of the other person's.",
      description:
        "Counts messages sent almost simultaneously (within 30 seconds of the other person's message).",
      formula: "Messages where |timestamp - other_timestamp| ≤ 30s",
      interpretation:
        "Indicates simultaneous typing, rapid-fire banter, excitement, and strong mutual co-presence.",
    },
  ],
  composition: [
    {
      key: "vocabulary",
      label: "Vocabulary",
      short: "Unique distinct words used.",
      description: "Count of distinct word tokens used by this participant throughout the chat.",
    },
    {
      key: "diversity",
      label: "Lexical Diversity (MATTR)",
      short: "Moving-average type-token ratio over a 500-token window.",
      description:
        "Calculates the moving-average ratio of unique words to total words using a sliding 500-word window.",
      formula: "Mean of Type-Token Ratio across sliding 500-token windows",
      interpretation:
        "The standard linguistic measure of vocabulary richness. Unlike raw TTR, lexical diversity does NOT decay as text length grows.",
      caveat:
        "Do NOT use Raw TTR for comparisons. Lexical diversity is also not comparable across languages: Persian agglutination naturally produces more tokens than English.",
    },
    {
      key: "ttr",
      label: "Raw TTR (Type-Token Ratio)",
      short: "Unique words divided by total words.",
      description:
        "Simple count of distinct words divided by the total words written.",
      formula: "unique_words / total_words",
      caveat:
        "Raw TTR inherently falls as text volume grows: a sample of 10,000 words cannot help repeating more words than a sample of 100. Comparing two participants by raw TTR mostly measures who wrote more.",
    },
    {
      key: "media",
      label: "Media Share",
      short: "Non-text messages as a percentage of all sent items.",
      description: "Photos, stickers, voice notes, and files over total sent messages.",
    },
    {
      key: "links",
      label: "Links",
      short: "URLs shared by this participant.",
      description: "Count of web links and URLs shared in messages.",
    },
    {
      key: "voice",
      label: "Voice Notes",
      short: "Voice messages sent.",
      description: "Number of audio recordings sent.",
    },
    {
      key: "voiceTime",
      label: "Voice Time",
      short: "Total duration of voice notes with length metadata.",
      description: "Cumulative duration of voice notes whose export included duration metadata.",
    },
    {
      key: "avgVoice",
      label: "Avg Voice Duration",
      short: "Average length of voice notes with duration data.",
      description:
        "Averages duration only over voice notes where the Telegram export included duration metadata.",
      caveat:
        "If a chat was exported without duration tags, this reads '—' rather than 0 to indicate missing export data.",
    },
  ],
  stance: [
    {
      key: "questions",
      label: "Questions (Interrogatives)",
      short: "Questions detected by punctuation OR question wording.",
      description:
        "Counts messages that contain question marks (? or ؟) OR interrogative question words (e.g. Persian چی, چرا, کی, کجا, etc.).",
      interpretation:
        "In Persian informal chat, questions are routinely typed without any question marks. This metric captures conversational inquiry far more accurately than punctuation alone.",
    },
    {
      key: "questionRate",
      label: "Q / 100 msgs",
      short: "Questions asked per 100 messages.",
      description:
        "Normalized rate of questions per 100 messages.",
      formula: "interrogative_count / message_count × 100",
      interpretation:
        "Measures relational curiosity and inquisitiveness: asking about the other person versus broadcasting.",
    },
    {
      key: "hedging",
      label: "Hedging / 1k",
      short: "Frequency of softening/uncertainty words per 1,000 words.",
      description:
        "Rates words like 'maybe', 'probably', 'perhaps', 'شاید', 'فکر کنم' per 1,000 words.",
      interpretation:
        "Epistemic hedging softens assertions and avoids categorical certainty.",
      caveat:
        "Uses token matching, so common roots count wherever they occur. Compare participants within the same chat rather than relying on absolute thresholds.",
    },
    {
      key: "backchannel",
      label: "Backchannel",
      short: "Bare reactive feedback messages ('yeah', 'دقیقا').",
      description:
        "Whole messages consisting solely of active listening tokens (e.g. 'yeah', 'aha', 'sure', 'دقیقا', 'آره').",
      interpretation:
        "Signals attentive listening or minimal agreement, keeping the conversational floor with the speaker.",
      caveat:
        "Backchannels deliberately overlap with cold closures. A single 'ok' can be read as closing a turn cheaply or as acknowledging the speaker; both metrics report it.",
    },
  ],
  expression: [
    {
      key: "affection",
      label: "Affection / 1k",
      short: "Endearments and warm terms per 1,000 words.",
      description:
        "Counts terms of endearment ('love', 'miss', 'dear', 'عزیزم', 'قربونت', 'فدات') per 1,000 words.",
      caveat:
        "A marker count is about wording, not feeling. A warm message with no listed words counts as zero; an offhand 'I love that pizza' counts as an affection marker.",
    },
    {
      key: "gratitude",
      label: "Gratitude / 1k",
      short: "Thanking expressions per 1,000 words.",
      description:
        "Counts expressions of thanks ('thanks', 'thank you', 'مرسی', 'ممنون', 'تشکر') per 1k words.",
    },
    {
      key: "apology",
      label: "Apology / 1k",
      short: "Apologies and regret markers per 1,000 words.",
      description:
        "Counts apologies ('sorry', 'apologies', 'ببخشید', 'شرمنده', 'عذر') per 1k words.",
    },
    {
      key: "emoji",
      label: "Emoji / 100",
      short: "Emoji characters per 100 words.",
      description:
        "Calculated per hundred words (rather than thousand) because emoji are frequent enough that per-thousand creates unwieldy numbers.",
      formula: "emoji_count / word_count × 100",
      interpretation:
        "Shows reliance on non-verbal graphical cues to communicate emotion and tone.",
    },
    {
      key: "elongation",
      label: "Elongation / 1k",
      short: "Stretched words with repeated letters per 1k words.",
      description:
        "Counts words containing character repetitions ('soooo', 'سلاممم') per 1k words.",
      caveat:
        "Counted on raw text before NLP normalization, because normalization deliberately collapses repeating characters.",
    },
    {
      key: "absolutism",
      label: "Absolutism %",
      short: "Share of words from the absolutist dictionary.",
      description:
        "Calculates the percentage of all words matching Al-Mosaiwi & Johnstone's unabridged dictionary of absolutist words.",
      formula: "absolutist_words / total_words × 100%",
      interpretation:
        "Research in clinical psychology connects high absolutist language with cognitive rigidity.",
      caveat:
        "Because the unabridged dictionary includes ordinary words like 'all' and 'must', the absolute percentage is only meaningful when compared between participants in the same chat.",
    },
    {
      key: "exclamations",
      label: "Exclamations / 1k",
      short: "Exclamation marks per 1,000 words.",
      description:
        "Frequency of exclamation marks (! and ！) per 1,000 words.",
      caveat:
        "A weak affect signal outside English. In Persian and multilingual chat, emotional expressiveness is carried almost entirely by emoji.",
    },
    {
      key: "collective",
      label: '"We" Focus',
      short: "Share of first-person references that are 'we' rather than 'I'.",
      description:
        "Calculates the ratio of plural first-person pronouns (we, us, our, ما) against all first-person pronouns (I, me, my, we, us, our, من, ما).",
      formula: "collective_pronouns / (self_pronouns + collective_pronouns) × 100%",
      interpretation:
        "Classic indicator in relationship text psychology reflecting cognitive framing as a joint unit versus separate individuals.",
    },
  ],
};

export const ASSESSMENT_FIELDS: Record<string, FieldDefinition[]> = {
  coverage: [
    {
      key: "coverage",
      label: "Assessment Coverage",
      short: "Percentage of chat messages evaluated by the classifier.",
      description:
        "Measures the share of total messages in the chat that have been read and classified by the machine learning model.",
      formula: "assessed_messages / total_messages × 100%",
      interpretation:
        "There is no requirement to assess 100% of a chat. A sample of 200–500 messages is statistically sufficient to establish stable proportions.",
      caveat:
        "Classified figures are model predictions, and any individual message can be misclassified. Always evaluate rates against the coverage percentage.",
    },
  ],
  valence: [
    {
      key: "assessed",
      label: "Assessed Messages",
      short: "Number of messages classified for this participant.",
      description: "Count of messages processed by the machine learning model.",
    },
    {
      key: "positive",
      label: "Positive Messages",
      short: "Messages classified with warm, appreciative, or playful tone.",
      description:
        "Model classification criteria: warm, appreciative, affectionate, playful, encouraging.",
    },
    {
      key: "neutral",
      label: "Neutral Messages",
      short: "Messages classified as factual, logistical, or informational.",
      description:
        "Model classification criteria: factual, logistical, informational, without emotional charge.",
    },
    {
      key: "negative",
      label: "Negative Messages",
      short: "Messages classified as cold, critical, hurt, or complaining.",
      description:
        "Model classification criteria: cold, critical, hurt, angry, complaining, dismissive.",
    },
    {
      key: "ratio",
      label: "Positivity Ratio",
      short: "Positive messages per negative message.",
      description:
        "Ratio of messages classified as positive divided by messages classified as negative.",
      formula: "positive_count / negative_count",
      interpretation:
        "Compares supportive, warm, or constructive tone against irritated, critical, or distressed tone.",
      caveat:
        "CRITICAL CAVEAT: John Gottman's well-known 5:1 ratio was discovered by observing couples in person over years with video, facial coding, and physiological tracking. A classifier reading text chat shares the vocabulary and NONE of that validation. Text strips tone, banter reads negatively, and chat is only a slice of a relationship.",
    },
  ],
  bids: [
    {
      key: "bids",
      label: "Bids for Connection",
      short: "Reaching out to connect with a thought, joke, question, or feeling.",
      description:
        "Model classification criteria: Is the sender reaching out to share a thought, feeling, joke, or image, or otherwise seeking the other person's engagement? (Gottman's 'bid for connection').",
      interpretation:
        "Measures how frequently each participant reaches out with content meant to engage the other.",
    },
    {
      key: "met",
      label: "Bids Met",
      short: "Bids that received an engaging response.",
      description:
        "Model classification criteria: Does the subsequent response acknowledge, engage with, or validate what the previous message said, rather than ignoring or brushing it off?",
      formula: "Count of bids where response engaged ('turned toward')",
      interpretation:
        "Describes attentiveness and reciprocal emotional engagement.",
    },
    {
      key: "metPct",
      label: "Bids Met %",
      short: "Percentage of live bids that received engagement.",
      description:
        "The share of bids that received an engaging response inside the assessed message range.",
      formula: "bids_met / eligible_bids × 100%",
      interpretation:
        "In a two-person chat, this describes how the OTHER participant responded to this person's bids.",
      caveat:
        "In group chats, the attribution is looser because any participant's reply can meet the bid.",
    },
  ],
  friction: [
    {
      key: "criticism",
      label: "Criticism",
      short: "Attacking the person's character rather than a specific action.",
      description:
        "Model classification criteria: attacks the other person's character or personality rather than an action ('you always forget', 'you never listen').",
      interpretation:
        "One of Gottman's Four Horsemen. Distinguishable from simple complaints by its global, character-attacking framing.",
    },
    {
      key: "defensiveness",
      label: "Defensiveness",
      short: "Warding off perceived attack, making excuses, or counter-blaming.",
      description:
        "Model classification criteria: deflects blame, makes excuses, counter-attacks, or refuses to acknowledge the partner's complaint.",
      interpretation:
        "Indicates escalating conversational tension and difficulty acknowledging the other party's perspective.",
    },
    {
      key: "contempt",
      label: "Contempt",
      short: "Mockery, sneering, name-calling, or hostile condescension.",
      description:
        "Model classification criteria: mockery, sneering, name-calling, condescension, eye-rolling sarcasm, or disgust.",
      interpretation:
        "Identified by Gottman as the single most corrosive factor in communication and the strongest predictor of relationship breakdown.",
    },
    {
      key: "frictionPct",
      label: "Friction %",
      short: "Overall share of messages containing friction.",
      description:
        "Percentage of assessed messages that exhibit criticism, defensiveness, or contempt.",
      formula: "(criticism + defensiveness + contempt) / assessed_messages × 100%",
      interpretation:
        "Provides a single composite metric of conversational conflict and friction.",
    },
    {
      key: "repair",
      label: "Repair Attempts",
      short: "De-escalating tension, apologizing, or soothing conflict.",
      description:
        "Model classification criteria: Is the sender apologizing, making peace, or trying to defuse tension?",
      formula: "Count and % of repair messages",
      interpretation:
        "Gottman found that successful couples are not free from conflict, but actively make and accept repair attempts.",
    },
    {
      key: "sarcasm",
      label: "Sarcasm Score",
      short: "Average sarcasm rating on a 0 to 3 scale.",
      description:
        "Classifier rating from 0 (genuine and straightforward; says what it means) to 3 (heavily sarcastic, barbed, passive-aggressive).",
      formula: "Mean sarcasm score (0–3)",
      interpretation:
        "Differentiates between straightforward communication and indirect or cutting language.",
    },
  ],
  discourse: [
    {
      key: "statements",
      label: "Statements",
      short: "Declarative messages conveying facts, reactions, or thoughts.",
      description:
        "Model classification criteria: states, informs, reacts, or acknowledges.",
    },
    {
      key: "closed",
      label: "Closed Questions",
      short: "Questions expecting a brief, factual, or yes/no answer.",
      description:
        "Model classification criteria: asks something answerable with yes, no, or a fact.",
    },
    {
      key: "open",
      label: "Open Questions",
      short: "Inquiries inviting deeper elaboration or personal vulnerability.",
      description:
        "Model classification criteria: invites the other person to open up, or discloses something personal or vulnerable.",
    },
    {
      key: "curiosity",
      label: "Curiosity / 1k",
      short: "Open questions and self-disclosures per 1,000 words.",
      description:
        "Rate of open-ended inquiry and personal disclosures per 1,000 words.",
      formula: "(open_question_count) / word_count × 1,000",
      interpretation:
        "Measures active interest in exploring the other person's thoughts, experiences, and inner life.",
    },
  ],
};

export function findFieldDefinition(
  category: string,
  key: string,
  source: "analytics" | "assessment" = "analytics",
): FieldDefinition | undefined {
  const dict = source === "analytics" ? ANALYTICS_FIELDS : ASSESSMENT_FIELDS;
  const list = dict[category];
  if (!list) return undefined;
  return list.find((item) => item.key.toLowerCase() === key.toLowerCase());
}
