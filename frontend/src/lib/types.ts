/** Mirrors of the Pydantic DTOs the API serves. Keep in sync with
 *  `application/dtos/` — these are the wire shapes, nothing more. */

export type Language = "fa" | "en" | "mixed" | "other" | "unknown";

export type ContentType =
  | "text"
  | "photo"
  | "voice_message"
  | "sticker"
  | "document";

export type DecisionTarget = "message" | "chat";

export type DecisionKind = "choice" | "score" | "noul";

export interface Chat {
  id: number;
  telegram_chat_id: number;
  name: string;
  type: string;
  total_messages: number;
  created_at: string | null;
}

export interface ImportSummary {
  chat: Chat;
  total_messages: number;
}

export interface Message {
  id: number;
  chat_id: number;
  telegram_msg_id: number;
  sender_id: string;
  sender_name: string;
  timestamp: string;
  text: string;
  normalized_text: string;
  language: Language;
  content_type: ContentType;
  reply_to_msg_id: number | null;
  is_forwarded: boolean;
  word_count: number;
  char_count: number;
  is_question: boolean;
  is_cold_closure: boolean;
}

/** One point of a latency trend: the median reply time over one period,
 *  with the number of replies behind it — a median resting on three replies
 *  should be visible as such. */
export interface LatencyPoint {
  period: string;
  median_seconds: number;
  reply_count: number;
}

/** How readily a participant answers. Latency is skewed by a few long gaps,
 *  so the median describes the usual wait and p90 the worst of it. */
export interface Responsiveness {
  avg_seconds: number | null;
  median_seconds: number | null;
  p90_seconds: number | null;
  reply_count: number;
  question_count: number;
  /** Taken up while the question was still live (a one-hour window). */
  questions_answered_count: number;
  questions_answered_percent: number | null;
  /** One point per week, or per month for a chat spanning over half a year. */
  latency_trend: LatencyPoint[];
  /** Positive when they are answering more slowly than they were. Read the
   *  series; this only says which direction to look in. */
  latency_drift_percent: number | null;
}

/** Who carries the conversation, and how they hold the floor. */
export interface Engagement {
  opened_count: number;
  opened_percent: number | null;
  closed_count: number;
  turn_count: number;
  avg_messages_per_turn: number;
  avg_words_per_turn: number;
  double_text_percent: number;
  cold_closure_count: number;
  cold_closure_percent: number;
  voice_message_count: number;
  media_count: number;
}

/** Marker counts from the lexicons, plus rates per thousand words. Read the
 *  rates: someone who writes twice as much has twice as much of everything. */
export interface Expression {
  exclamation_count: number;
  emoji_count: number;
  affection_count: number;
  apology_count: number;
  gratitude_count: number;
  self_reference_count: number;
  collective_reference_count: number;
  absolutist_count: number;
  elongation_count: number;
  exclamations_per_1k_words: number;
  affection_per_1k_words: number;
  apology_per_1k_words: number;
  gratitude_per_1k_words: number;
  /** Stretched words: "soooo", سلاممم. Counted before normalization. */
  elongation_per_1k_words: number;
  /** Per HUNDRED words — emoji are frequent enough that per-thousand reads
   *  badly. Do not rename this to match the others. */
  emoji_per_100_words: number;
  /** Al-Mosaiwi & Johnstone's absolutist dictionary, unabridged, so it
   *  includes ordinary words like "all" and "must". Only meaningful next to
   *  another participant in the same conversation. */
  absolutism_percent: number;
  /** Share of first-person reference that is "we" rather than "I". */
  collective_focus_percent: number | null;
}

/** When someone writes, and how fast they answer while still awake. */
export interface Circadian {
  hourly_distribution: Record<string, number>;
  night_owl_percent: number;
  peak_hour: number | null;
  active_median_seconds: number | null;
  active_p90_seconds: number | null;
  active_reply_count: number;
  revived_count: number;
  revived_percent: number | null;
}

/** Who sets the pace of a conversation, and who is left holding it. */
export interface Control {
  burst_count: number;
  long_burst_count: number;
  long_burst_percent: number;
  longest_burst: number;
  avg_burst_size: number;
  last_word_count: number;
  last_word_percent: number | null;
  collision_count: number;
  collision_percent: number;
}

/** What the messages are made of: vocabulary, media, voice. */
export interface Composition {
  unique_word_count: number;
  type_token_ratio: number | null;
  /** Moving-average TTR. The comparable one — raw TTR falls as a sample grows. */
  lexical_diversity: number | null;
  text_message_count: number;
  media_message_count: number;
  media_percent: number;
  link_count: number;
  voice_message_count: number;
  voice_seconds: number;
  avg_voice_seconds: number | null;
  /** Voice notes whose length the export carried. Zero means the durations
   *  were never imported, not that the notes were empty. */
  timed_voice_count: number;
}

/** Asking, hedging, and going along with what the other person said. */
export interface Stance {
  interrogative_count: number;
  questions_per_100_messages: number;
  hedge_count: number;
  hedge_per_1k_words: number;
  backchannel_count: number;
  backchannel_percent: number;
}

/** Function-word convergence across adjacent turns. Describes a pair, so it
 *  is chat-level rather than per participant. */
export interface StyleMatching {
  lsm_percent: number | null;
  by_category: Record<string, number>;
  turn_pairs: number;
}

export interface RederiveSummary {
  chat_id: number;
  messages_rewritten: number;
}

export interface ParticipantStats {
  sender_id: string;
  sender_name: string;
  message_count: number;
  word_count: number;
  char_count: number;
  avg_words_per_message: number;
  message_share_percent: number;
  word_share_percent: number;
  responsiveness: Responsiveness;
  engagement: Engagement;
  expression: Expression;
  circadian: Circadian;
  control: Control;
  composition: Composition;
  stance: Stance;
}

/** The shape of the conversation over time. A session is one sitting — a run
 *  of messages with no silence longer than the configured gap. */
export interface ConversationRhythm {
  session_count: number;
  avg_messages_per_session: number;
  avg_session_minutes: number;
  active_days: number;
  span_days: number;
  active_day_percent: number;
  longest_silence_days: number;
  /** Silences longer than 48 hours — the conversation stopped, not paused. */
  silence_count: number;
  late_night_percent: number;
}

/** Normalised entropy over the participants' shares: 100 is an even split,
 *  falling toward 0 as one person dominates. */
export interface Balance {
  message_balance_percent: number;
  word_balance_percent: number;
  initiation_balance_percent: number;
  /** Slowest participant's median reply over the fastest's. */
  response_time_ratio: number | null;
}

export interface ChatAnalytics {
  chat_id: number;
  chat_name: string;
  total_messages: number;
  date_range_start: string | null;
  date_range_end: string | null;
  participants: ParticipantStats[];
  hourly_distribution: Record<string, number>;
  daily_distribution: Record<string, number>;
  language_breakdown: Record<string, number>;
  avg_response_time_seconds: number | null;
  rhythm: ConversationRhythm;
  balance: Balance;
  style_matching: StyleMatching;
}

export interface Decision {
  target_type: DecisionTarget;
  target_id: number;
  question_key: string;
  decision_type: DecisionKind;
  result_value: unknown;
  confidence: number;
  probabilities: Record<string, number>;
  created_at: string | null;
}

export interface Health {
  status: string;
  app: string;
  database: string;
  decision_engine: Record<string, unknown>;
}

/* ---------------------------------------------------------- assessment */

/** Per-participant read of the classifier's answers. Every figure here is a
 *  reading rather than a count, and should be read against the assessment's
 *  `coverage_percent`. */
export interface ParticipantAssessment {
  sender_id: string;
  sender_name: string;
  assessed_message_count: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  /** Positive messages per negative one; null when nothing read negative. */
  positivity_ratio: number | null;
  bid_count: number;
  bids_met_count: number;
  bids_met_percent: number | null;
  criticism_count: number;
  defensiveness_count: number;
  contempt_count: number;
  friction_percent: number;
  repair_count: number;
  repair_percent: number;
  /** 0 (straightforward) to 3 (heavily barbed). */
  avg_sarcasm_score: number | null;
  statement_count: number;
  closed_question_count: number;
  open_question_count: number;
  curiosity_per_1k_words: number;
}

export interface RelationalAssessment {
  chat_id: number;
  chat_name: string;
  total_messages: number;
  assessed_messages: number;
  coverage_percent: number;
  participants: ParticipantAssessment[];
}

/** What one paged assessment call got through. The pass is resumable: call
 *  again with `next_offset` until `is_complete`. */
export interface AssessmentProgress {
  chat_id: number;
  assessed_now: number;
  skipped_already_done: number;
  next_offset: number;
  is_complete: boolean;
  coverage_percent: number;
}
