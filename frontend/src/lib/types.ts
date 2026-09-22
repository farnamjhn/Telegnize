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
}

/** Who carries the conversation, and how they hold the floor. */
export interface Engagement {
  opened_count: number;
  opened_percent: number | null;
  closed_count: number;
  turn_count: number;
  avg_messages_per_turn: number;
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
  exclamations_per_1k_words: number;
  emoji_per_1k_words: number;
  affection_per_1k_words: number;
  apology_per_1k_words: number;
  gratitude_per_1k_words: number;
  /** Share of first-person reference that is "we" rather than "I". */
  collective_focus_percent: number | null;
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
