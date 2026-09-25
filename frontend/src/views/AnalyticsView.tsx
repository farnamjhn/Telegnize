import { useState } from "react";

import { ChatSelect } from "../App";
import {
  Card,
  Empty,
  Field,
  Hero,
  Icon,
  Notice,
  Spinner,
  Stat,
  Toggle,
  ViewToggle,
} from "../components/Primitives";
import {
  ColumnChart,
  type Point,
  ShareStrip,
  TrendChart,
  type TrendSeries,
  foldToSlices,
} from "../components/charts";
import { api } from "../lib/api";
import {
  compact,
  dateOnly,
  days,
  duration,
  hourLabel,
  humanize,
  int,
  languageName,
  minutes,
  pct,
  pctOrDash,
  periodLabel,
  rate,
  ratio,
  signedPct,
} from "../lib/format";
import type { Chat, ParticipantStats, StyleMatching } from "../lib/types";
import { useAsync } from "../lib/useAsync";

const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

/* ------------------------------------------------ the participant tables */

type MetricGroup =
  | "volume"
  | "responsiveness"
  | "circadian"
  | "engagement"
  | "control"
  | "composition"
  | "expression"
  | "stance";

const GROUPS = [
  { value: "volume", label: "Volume" },
  { value: "responsiveness", label: "Responsiveness" },
  { value: "circadian", label: "Circadian" },
  { value: "engagement", label: "Engagement" },
  { value: "control", label: "Control" },
  { value: "composition", label: "Composition" },
  { value: "expression", label: "Expression" },
  { value: "stance", label: "Stance" },
] as const;

/** What the reader should keep in mind for each group — condensed from
 *  `docs/analytics.md`, which is the authority on what these figures mean. */
const GROUP_NOTE: Record<MetricGroup, string> = {
  volume:
    "Message share and word share can diverge sharply — many short fragments can carry as much as a few long messages.",
  responsiveness:
    "Read the median first: the average is dragged upward by a few long gaps, and p90 is what being left waiting looks like.",
  engagement:
    "Double-texting is a style measure at least as much as a pursuit measure — it says most when two people differ sharply on it.",
  expression:
    "Rates per thousand words, so writing more does not by itself raise the figure. Marker counts describe wording, not feeling.",
  circadian:
    "The active reply time leaves out gaps longer than two hours, so it describes attention rather than availability. It will disagree with the median under Responsiveness, and both are right about different questions.",
  control:
    "A burst of three is a pacing difference — some people think in messages where others think in paragraphs. It is not anxiety, and reading it as anxiety is the mistake this whole document exists to prevent.",
  composition:
    "Use Diversity, not raw TTR: the raw ratio falls as a sample grows, so it mostly measures who wrote more. Neither is comparable across languages.",
  stance:
    "Questions count Persian wording as well as punctuation, so this is higher than the Responsiveness question count and is the better reading of curiosity here.",
};

/** A 0–1 ratio, at the precision it is actually resolved to. */
const decimal = (value: number | null | undefined, digits = 3): string =>
  value == null ? "—" : value.toFixed(digits);

interface Column {
  key: string;
  label: string;
  render: (person: ParticipantStats) => string;
  hint?: string;
}

const COLUMNS: Record<MetricGroup, Column[]> = {
  volume: [
    { key: "messages", label: "Messages", render: (p) => int(p.message_count) },
    { key: "share", label: "Share", render: (p) => pct(p.message_share_percent) },
    { key: "words", label: "Words", render: (p) => compact(p.word_count) },
    { key: "wordShare", label: "Word share", render: (p) => pct(p.word_share_percent) },
    {
      key: "perMessage",
      label: "Words / msg",
      render: (p) => p.avg_words_per_message.toFixed(1),
    },
    { key: "chars", label: "Characters", render: (p) => compact(p.char_count) },
  ],
  responsiveness: [
    {
      key: "median",
      label: "Median reply",
      render: (p) => duration(p.responsiveness.median_seconds),
      hint: "The usual wait",
    },
    {
      key: "p90",
      label: "p90",
      render: (p) => duration(p.responsiveness.p90_seconds),
      hint: "The slow tail — what being left waiting looks like",
    },
    {
      key: "avg",
      label: "Average",
      render: (p) => duration(p.responsiveness.avg_seconds),
      hint: "Skewed upward by a few long gaps; kept for completeness",
    },
    {
      key: "replies",
      label: "Replies",
      render: (p) => compact(p.responsiveness.reply_count),
      hint: "Replies the median is computed from",
    },
    {
      key: "asked",
      label: "Questions",
      render: (p) => int(p.responsiveness.question_count),
      hint: "Questions this person asked",
    },
    {
      key: "answered",
      label: "Answered live",
      render: (p) => pctOrDash(p.responsiveness.questions_answered_percent),
      hint: "Share the other party took up while the question was still live",
    },
    {
      key: "drift",
      label: "Drift",
      render: (p) => signedPct(p.responsiveness.latency_drift_percent),
      hint: "Change from the first half of the trend to the second. Positive means answering more slowly — read the chart, not this number",
    },
  ],
  engagement: [
    {
      key: "opened",
      label: "Opened",
      render: (p) =>
        `${int(p.engagement.opened_count)} · ${pctOrDash(p.engagement.opened_percent, 0)}`,
      hint: "Conversations started after a silence",
    },
    {
      key: "closed",
      label: "Closed",
      render: (p) => int(p.engagement.closed_count),
      hint: "Conversations where they had the last word",
    },
    {
      key: "turns",
      label: "Turns",
      render: (p) => compact(p.engagement.turn_count),
      hint: "Uninterrupted runs of their own messages",
    },
    {
      key: "perTurn",
      label: "Msgs / turn",
      render: (p) => p.engagement.avg_messages_per_turn.toFixed(1),
    },
    {
      key: "wordsPerTurn",
      label: "Words / turn",
      render: (p) => p.engagement.avg_words_per_turn.toFixed(1),
    },
    {
      key: "double",
      label: "Double-text",
      render: (p) => pct(p.engagement.double_text_percent),
      hint: "Share of their messages that continued their own turn",
    },
    {
      key: "cold",
      label: "Cold closures",
      render: (p) =>
        `${int(p.engagement.cold_closure_count)} · ${pct(p.engagement.cold_closure_percent)}`,
      hint: 'Whole messages that are a bare "ok" / "باشه"',
    },
    { key: "voice", label: "Voice", render: (p) => compact(p.engagement.voice_message_count) },
    { key: "media", label: "Media", render: (p) => compact(p.engagement.media_count) },
  ],
  circadian: [
    {
      key: "night",
      label: "Night owl",
      render: (p) => pct(p.circadian.night_owl_percent),
      hint: "Share of their messages sent between midnight and 05:00",
    },
    {
      key: "peak",
      label: "Peak hour",
      render: (p) => (p.circadian.peak_hour == null ? "—" : `${hourLabel(p.circadian.peak_hour)}:00`),
      hint: "The hour they write most in",
    },
    {
      key: "activeMedian",
      label: "Active reply",
      render: (p) => duration(p.circadian.active_median_seconds),
      hint: "Median reply time with the overnight gaps taken out — attention rather than availability",
    },
    {
      key: "activeP90",
      label: "Active p90",
      render: (p) => duration(p.circadian.active_p90_seconds),
      hint: "The slow tail, still inside a live conversation",
    },
    {
      key: "activeCount",
      label: "Live replies",
      render: (p) => compact(p.circadian.active_reply_count),
      hint: "Replies the active figures are computed from",
    },
    {
      key: "revived",
      label: "Revived",
      render: (p) =>
        `${int(p.circadian.revived_count)} · ${pctOrDash(p.circadian.revived_percent, 0)}`,
      hint: "Silences over 48 hours that this person was the one to end. Usually a small sample — check the silence count under Rhythm",
    },
  ],
  control: [
    {
      key: "turns",
      label: "Turns",
      render: (p) => compact(p.control.burst_count),
      hint: "Uninterrupted runs of their own messages",
    },
    {
      key: "bursts",
      label: "Bursts 3+",
      render: (p) =>
        `${compact(p.control.long_burst_count)} · ${pct(p.control.long_burst_percent, 0)}`,
      hint: "Turns of three messages or more before the other person said anything",
    },
    {
      key: "longest",
      label: "Longest",
      render: (p) => int(p.control.longest_burst),
      hint: "The most messages they ever sent in a row",
    },
    {
      key: "avgBurst",
      label: "Msgs / burst",
      render: (p) => p.control.avg_burst_size.toFixed(1),
    },
    {
      key: "lastWord",
      label: "Last word",
      render: (p) =>
        `${int(p.control.last_word_count)} · ${pctOrDash(p.control.last_word_percent, 0)}`,
      hint: "Conversations whose final message was theirs, at a three-hour silence",
    },
    {
      key: "collisions",
      label: "Collisions",
      render: (p) => `${compact(p.control.collision_count)} · ${pct(p.control.collision_percent, 0)}`,
      hint: "Messages sent within 30 seconds of the other person's — the two of you typing at once",
    },
  ],
  composition: [
    {
      key: "vocabulary",
      label: "Vocabulary",
      render: (p) => compact(p.composition.unique_word_count),
      hint: "Distinct words they used",
    },
    {
      key: "diversity",
      label: "Diversity",
      render: (p) => decimal(p.composition.lexical_diversity),
      hint: "Moving-average type-token ratio over a 500-word window. Read this one — it does not fall as someone writes more",
    },
    {
      key: "ttr",
      label: "Raw TTR",
      render: (p) => decimal(p.composition.type_token_ratio),
      hint: "Unique over total words. Falls as a sample grows, so between two people it mostly measures who wrote more",
    },
    {
      key: "media",
      label: "Media",
      render: (p) => `${compact(p.composition.media_message_count)} · ${pct(p.composition.media_percent, 0)}`,
      hint: "Photos, stickers, files and voice notes as a share of everything they sent",
    },
    {
      key: "links",
      label: "Links",
      render: (p) => compact(p.composition.link_count),
    },
    {
      key: "voice",
      label: "Voice",
      render: (p) => compact(p.composition.voice_message_count),
    },
    {
      key: "voiceTime",
      label: "Voice time",
      render: (p) =>
        p.composition.timed_voice_count === 0 ? "—" : duration(p.composition.voice_seconds),
      hint: "Total across voice notes whose length the export carried",
    },
    {
      key: "avgVoice",
      label: "Avg voice",
      render: (p) => duration(p.composition.avg_voice_seconds),
      hint: "Averaged over timed notes only, so it reads — rather than 0 when durations were never imported",
    },
  ],
  stance: [
    {
      key: "questions",
      label: "Questions",
      render: (p) => compact(p.stance.interrogative_count),
      hint: "By punctuation or by wording — Persian questions often carry no ؟ at all",
    },
    {
      key: "questionRate",
      label: "Q / 100 msgs",
      render: (p) => rate(p.stance.questions_per_100_messages),
      hint: "Relational inquisitiveness: asking about the other person rather than broadcasting",
    },
    {
      key: "hedging",
      label: "Hedging / 1k",
      render: (p) => rate(p.stance.hedge_per_1k_words),
      hint: '"maybe", "probably", شاید, فکر کنم — token-matched, so read it against the other participant, not on its own',
    },
    {
      key: "backchannel",
      label: "Backchannel",
      render: (p) =>
        `${compact(p.stance.backchannel_count)} · ${pct(p.stance.backchannel_percent, 0)}`,
      hint: 'Whole messages that are a bare "yeah" / دقیقا — active listening, or a reply that is not one',
    },
  ],
  expression: [
    {
      key: "affection",
      label: "Affection / 1k",
      render: (p) => rate(p.expression.affection_per_1k_words),
      hint: 'Endearments, "miss", "love", عزیزم, قربونت',
    },
    {
      key: "gratitude",
      label: "Gratitude / 1k",
      render: (p) => rate(p.expression.gratitude_per_1k_words),
      hint: '"thanks", مرسی, ممنون',
    },
    {
      key: "apology",
      label: "Apology / 1k",
      render: (p) => rate(p.expression.apology_per_1k_words),
      hint: '"sorry", ببخشید, شرمنده',
    },
    {
      key: "emoji",
      label: "Emoji / 100",
      render: (p) => rate(p.expression.emoji_per_100_words),
      hint: "Per hundred words — emoji are frequent enough that per-thousand reads badly",
    },
    {
      key: "elongation",
      label: "Elongation / 1k",
      render: (p) => rate(p.expression.elongation_per_1k_words),
      hint: 'Stretched words: "soooo", سلاممم — counted before normalization',
    },
    {
      key: "absolutism",
      label: "Absolutism",
      render: (p) => pct(p.expression.absolutism_percent, 2),
      hint: "Absolutist words as a share of everything they wrote. The unabridged dictionary includes ordinary words like \"all\" and \"must\", so read it next to the other participant, not on its own",
    },
    {
      key: "exclamations",
      label: "Exclam. / 1k",
      render: (p) => rate(p.expression.exclamations_per_1k_words),
      hint: "A weak signal outside English-language chat, where emoji carry it instead",
    },
    {
      key: "collective",
      label: '"We" focus',
      render: (p) => pctOrDash(p.expression.collective_focus_percent),
      hint: 'Share of first-person reference that is "we" rather than "I"',
    },
  ],
};

/** Marker columns are written as messages are stored, so a chat imported
 *  before a metric existed reads as all-zero rather than empty.
 *
 *  Only groups whose markers cannot all be legitimately zero belong here. A
 *  chat really can contain no links, so Composition is left out and its one
 *  genuinely unrecoverable gap — voice durations — is reported on its own. */
const MARKER_TOTALS: Partial<Record<MetricGroup, (p: ParticipantStats) => number[]>> = {
  expression: (p) => [
    p.expression.emoji_count,
    p.expression.affection_count,
    p.expression.apology_count,
    p.expression.gratitude_count,
    p.expression.exclamation_count,
    p.expression.self_reference_count,
    p.expression.collective_reference_count,
  ],
  stance: (p) => [
    p.stance.interrogative_count,
    p.stance.hedge_count,
    p.stance.backchannel_count,
  ],
};

function markersMissing(group: MetricGroup, participants: ParticipantStats[]): boolean {
  const totals = MARKER_TOTALS[group];
  if (!totals || participants.length === 0) return false;
  return !participants.some((person) => totals(person).some((count) => count > 0));
}

/** Voice notes with no length on any of them. Unlike the marker columns this
 *  cannot be recomputed: a duration lives in the export, not in the text. */
function voiceDurationsMissing(participants: ParticipantStats[]): boolean {
  const voice = participants.reduce((n, p) => n + p.composition.voice_message_count, 0);
  const timed = participants.reduce((n, p) => n + p.composition.timed_voice_count, 0);
  return voice > 0 && timed === 0;
}

function Participants({
  participants,
  chatId,
  onRederived,
}: {
  participants: ParticipantStats[];
  chatId: number;
  onRederived: () => void;
}) {
  const [group, setGroup] = useState<MetricGroup>("volume");
  const [rederiving, setRederiving] = useState(false);
  const [rederiveError, setRederiveError] = useState<string | null>(null);
  const columns = COLUMNS[group];
  const missing = markersMissing(group, participants);

  async function rederive() {
    setRederiving(true);
    setRederiveError(null);
    try {
      await api.rederive(chatId);
      onRederived();
    } catch (cause) {
      setRederiveError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setRederiving(false);
    }
  }

  return (
    <Card
      title="Participants"
      subtitle={GROUP_NOTE[group]}
      action={<Toggle label="Metric group" value={group} onChange={setGroup} options={GROUPS} />}
      flush
    >
      {missing && (
        <div style={{ padding: "0 var(--pad-card) 4px" }}>
          <Notice tone="error">
            Every marker in this group reads zero. These counts are written as messages are
            stored, so a chat imported before the metric existed has none. They are all
            derived from text already in the database, so recomputing fills them in — the
            export is not needed.
            <div style={{ marginTop: 10 }}>
              <button className="btn" disabled={rederiving} onClick={() => void rederive()}>
                {rederiving && <span className="spinner" />}
                Recompute from stored text
              </button>
            </div>
          </Notice>
        </div>
      )}
      {rederiveError && (
        <div style={{ padding: "0 var(--pad-card) 4px" }}>
          <Notice tone="error">{rederiveError}</Notice>
        </div>
      )}
      {group === "composition" && voiceDurationsMissing(participants) && (
        <div style={{ padding: "0 var(--pad-card) 4px" }}>
          <Notice>
            Voice notes are here but none carry a length, so the time columns read —. A
            duration lives in the export rather than in the message text, which is the one
            thing recomputing cannot recover: re-import the export to fill it in.
          </Notice>
        </div>
      )}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Participant</th>
              {columns.map((column) => (
                <th key={column.key} className="num" title={column.hint}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {participants.map((person) => (
              <tr key={person.sender_id}>
                <td>
                  <div style={{ fontWeight: 500 }}>{person.sender_name}</div>
                  <div className="share" style={{ marginTop: 5, maxWidth: 180 }}>
                    <span className="share-track">
                      <span
                        className="share-fill"
                        style={{ width: `${person.message_share_percent}%` }}
                      />
                    </span>
                    <span className="share-value">{pct(person.message_share_percent)}</span>
                  </div>
                </td>
                {columns.map((column) => (
                  <td key={column.key} className="num">
                    {column.render(person)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------- latency trend */

const TREND_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

function LatencyTrend({ participants }: { participants: ParticipantStats[] }) {
  // Past three participants the lines stop being tellable apart, so the chart
  // steps aside for the table, which carries every median anyway.
  const series: TrendSeries[] = participants
    .slice(0, TREND_COLORS.length)
    .map((person, i) => ({
      key: person.sender_id,
      label: person.sender_name,
      color: TREND_COLORS[i],
      points: person.responsiveness.latency_trend.map((point) => ({
        period: point.period,
        value: point.median_seconds,
        count: point.reply_count,
      })),
    }))
    .filter((line) => line.points.length > 0);

  if (series.length === 0) return null;

  return (
    <Card
      title="Is it slowing down?"
      subtitle="Median reply time per period. A median resting on few replies moves easily — the tooltip says how many are behind each point."
    >
      <TrendChart series={series} formatValue={duration} formatPeriod={periodLabel} />
      {participants.length > TREND_COLORS.length && (
        <p className="faint" style={{ fontSize: 12, marginTop: 4 }}>
          Showing the {TREND_COLORS.length} most active participants. The table has the rest.
        </p>
      )}
    </Card>
  );
}

/* ----------------------------------------------------------- body clock */

/** Each participant's own hour-of-day distribution.
 *
 *  The chat-wide chart above averages everyone together, which describes
 *  nobody when two people keep different hours: opposite schedules produce a
 *  flat curve that looks like neither of them has one. */
function BodyClock({ participants }: { participants: ParticipantStats[] }) {
  // The circadian check is for the moment after a deploy when the page has
  // reloaded and the API has not: one missing group should not blank the view.
  if (participants.length < 2 || !participants[0].circadian) return null;

  return (
    <Card
      title="Body clock"
      subtitle="Each participant's own hours. Compare the shapes — the chat-wide chart above averages them together."
    >
      <div style={{ display: "grid", gap: 22 }}>
        {participants.slice(0, 3).map((person) => {
          const hours: Point[] = Array.from({ length: 24 }, (_, hour) => ({
            key: String(hour),
            label: hourLabel(hour),
            value: person.circadian.hourly_distribution?.[String(hour)] ?? 0,
          }));
          return (
            <div key={person.sender_id}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{person.sender_name}</span>
                <span className="faint" style={{ fontSize: 12 }}>
                  {pct(person.circadian.night_owl_percent)} after midnight
                  {person.circadian.peak_hour != null &&
                    ` · peaks at ${hourLabel(person.circadian.peak_hour)}:00`}
                </span>
              </div>
              <ColumnChart data={hours} height={120} labelEvery={3} />
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* --------------------------------------------------------- style matching */

function StyleMatchingCard({ matching }: { matching: StyleMatching }) {
  if (matching.lsm_percent == null) return null;

  const categories = Object.entries(matching.by_category).sort((a, b) => b[1] - a[1]);

  return (
    <Card
      title="Style matching"
      subtitle="How far the two of you converge on function words — the grammatical scaffolding nobody picks deliberately."
    >
      <div className="grid grid--hero" style={{ marginBottom: 18 }}>
        <Card fill>
          <Hero
            label="Linguistic style matching"
            value={pct(matching.lsm_percent)}
            note={`across ${compact(matching.turn_pairs)} adjacent turn pairs`}
          />
        </Card>
        <Card fill>
          <p className="muted" style={{ fontSize: 13 }}>
            Function-word convergence rises with engagement of any kind, an argument
            included, so this is not a score for how well two people get along. The Persian
            entries are the free-standing forms the normalizer leaves behind, so the figure
            drifts with the language mix. Read it against itself over time in this chat, and
            treat a comparison with another chat as meaningless.
          </p>
        </Card>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {categories.map(([name, value]) => (
          <BalanceMeter key={name} label={humanize(name)} value={value} />
        ))}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------- balance */

function BalanceMeter({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div title={hint}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{label}</span>
        <span className="share-value">{pct(value)}</span>
      </div>
      <div className="meter">
        <div className="meter-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

/* ----------------------------------------------- chart card + table twin */

function Plot({
  title,
  subtitle,
  rows,
  columns,
  children,
}: {
  title: string;
  subtitle?: string;
  rows: Point[];
  columns: [string, string];
  children: React.ReactNode;
}) {
  const [mode, setMode] = useState<"chart" | "table">("chart");
  return (
    <Card title={title} subtitle={subtitle} action={<ViewToggle mode={mode} onChange={setMode} />}>
      {mode === "chart" ? (
        children
      ) : (
        <div className="table-wrap" style={{ maxHeight: 260, overflowY: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ paddingInline: 0 }}>{columns[0]}</th>
                <th className="num" style={{ paddingInline: 0 }}>
                  {columns[1]}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <td style={{ paddingInline: 0 }}>{row.label}</td>
                  <td className="num" style={{ paddingInline: 0 }}>
                    {int(row.value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* ----------------------------------------------------------- export modal */

function ExportModal({
  chatName,
  totalMessages,
  isOpen,
  onClose,
  onExport,
}: {
  chatName: string;
  totalMessages: number;
  isOpen: boolean;
  onClose: () => void;
  onExport: (options: { scope: "full" | "active"; theme: "light" | "dark" }) => void;
}) {
  const [scope, setScope] = useState<"full" | "active">("full");
  const [theme, setTheme] = useState<"light" | "dark">("light");

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-modal-title"
      >
        <header className="modal-head">
          <div>
            <h2 id="export-modal-title" className="modal-title">
              Export Analytics to PDF
            </h2>
            <p className="faint" style={{ fontSize: 12, marginTop: 2 }}>
              {chatName} · {int(totalMessages)} messages
            </p>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <div className="modal-body">
          <div>
            <div className="modal-section-title">Report Scope</div>
            <div className="option-group">
              <label
                className={`option-card ${scope === "full" ? "is-selected" : ""}`}
                onClick={() => setScope("full")}
              >
                <input
                  type="radio"
                  name="export-scope"
                  className="option-radio"
                  checked={scope === "full"}
                  onChange={() => setScope("full")}
                />
                <div className="option-content">
                  <span className="option-label">Full Analytics Dossier</span>
                  <span className="option-hint">
                    Complete report containing all 8 participant metric sections with their reference notes.
                  </span>
                </div>
              </label>

              <label
                className={`option-card ${scope === "active" ? "is-selected" : ""}`}
                onClick={() => setScope("active")}
              >
                <input
                  type="radio"
                  name="export-scope"
                  className="option-radio"
                  checked={scope === "active"}
                  onChange={() => setScope("active")}
                />
                <div className="option-content">
                  <span className="option-label">Current View Only</span>
                  <span className="option-hint">
                    Export charts and only the participant metric section currently open on screen.
                  </span>
                </div>
              </label>
            </div>
          </div>

          <div>
            <div className="modal-section-title">Color Theme</div>
            <div className="option-group">
              <label
                className={`option-card ${theme === "light" ? "is-selected" : ""}`}
                onClick={() => setTheme("light")}
              >
                <input
                  type="radio"
                  name="export-theme"
                  className="option-radio"
                  checked={theme === "light"}
                  onChange={() => setTheme("light")}
                />
                <div className="option-content">
                  <span className="option-label">Print-Friendly Light (Recommended)</span>
                  <span className="option-hint">
                    Crisp white paper layout with dark ink; saves printer toner and reads like a printed dossier.
                  </span>
                </div>
              </label>

              <label
                className={`option-card ${theme === "dark" ? "is-selected" : ""}`}
                onClick={() => setTheme("dark")}
              >
                <input
                  type="radio"
                  name="export-theme"
                  className="option-radio"
                  checked={theme === "dark"}
                  onChange={() => setTheme("dark")}
                />
                <div className="option-content">
                  <span className="option-label">AMOLED Dark</span>
                  <span className="option-hint">
                    Preserves the signature AMOLED dark theme in the exported PDF.
                  </span>
                </div>
              </label>
            </div>
          </div>
        </div>

        <footer className="modal-foot">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              onExport({ scope, theme });
              onClose();
            }}
          >
            <Icon name="pdf" size={15} />
            Export PDF
          </button>
        </footer>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ view */

export function AnalyticsView({
  chats,
  chatId,
  onChatId,
}: {
  chats: Chat[];
  chatId: number | null;
  onChatId: (id: number) => void;
}) {
  const { data, error, loading, refetching, reload } = useAsync(
    () => (chatId == null ? null : api.analytics(chatId)),
    [chatId],
  );

  const [exportModalOpen, setExportModalOpen] = useState(false);

  function handleTriggerExport(options: { scope: "full" | "active"; theme: "light" | "dark" }) {
    if (!data) return;

    const previousTitle = document.title;
    const safeChatName = data.chat_name.replace(/[/\\?%*:|"<>]/g, "-").trim() || "Chat";
    document.title = `${safeChatName} - Telegnize Analytics`;

    document.body.setAttribute("data-print-theme", options.theme);
    document.body.setAttribute("data-print-scope", options.scope);

    const cleanup = () => {
      document.title = previousTitle;
      document.body.removeAttribute("data-print-theme");
      document.body.removeAttribute("data-print-scope");
      window.removeEventListener("afterprint", cleanup);
    };

    window.addEventListener("afterprint", cleanup);

    setTimeout(() => {
      window.print();
      setTimeout(cleanup, 2000);
    }, 120);
  }

  if (chats.length === 0) {
    return (
      <div className="view">
        <header className="view-head">
          <h1 className="view-title">Analytics</h1>
        </header>
        <Card>
          <Empty title="No chat to analyse" body="Import a Telegram export from the Chats tab first." />
        </Card>
      </div>
    );
  }

  const hourly: Point[] = Array.from({ length: 24 }, (_, hour) => ({
    key: String(hour),
    label: hourLabel(hour),
    value: data?.hourly_distribution?.[String(hour)] ?? 0,
  }));

  const weekly: Point[] = WEEKDAYS.map((day) => ({
    key: day,
    label: day.slice(0, 3),
    value: data?.daily_distribution?.[day] ?? 0,
  }));
  const busiestDay = weekly.reduce((best, day) => (day.value > best.value ? day : best), weekly[0]);

  const languages = foldToSlices(Object.entries(data?.language_breakdown ?? {}), languageName);
  const participants = data?.participants ?? [];
  const busiest = hourly.reduce((best, point) => (point.value > best.value ? point : best), hourly[0]);
  const rhythm = data?.rhythm;
  const balance = data?.balance;

  return (
    <div className="view">
      <ExportModal
        chatName={data?.chat_name ?? "Chat"}
        totalMessages={data?.total_messages ?? 0}
        isOpen={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onExport={handleTriggerExport}
      />

      <header className="view-head">
        <div>
          <h1 className="view-title">Analytics</h1>
          <p className="view-sub">
            Behavioural observations drawn from the transcript — who wrote when, how fast
            they answered, which words appear. They describe the messages, not the
            relationship behind them.
          </p>
        </div>
      </header>

      {/* One filter row, above everything it scopes. */}
      <div className="filters" style={{ justifyContent: "space-between", alignItems: "flex-end" }}>
        <div className="row" style={{ gap: 16, alignItems: "flex-end" }}>
          <Field label="Chat" htmlFor="analytics-chat">
            <ChatSelect id="analytics-chat" chats={chats} value={chatId} onChange={onChatId} />
          </Field>
          {refetching && <Spinner />}
        </div>
        <div>
          <button
            type="button"
            className="btn"
            onClick={() => setExportModalOpen(true)}
            disabled={!data || data.total_messages === 0}
            title="Export full analytics report to PDF"
          >
            <Icon name="pdf" size={15} />
            Export to PDF
          </button>
        </div>
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      {loading && (
        <Card>
          <Spinner label="Computing analytics…" />
        </Card>
      )}

      {data && (
        <div className={refetching ? "stack-v is-refetching" : "stack-v"}>
          {data.total_messages === 0 ? (
            <Card>
              <Empty
                title="This chat has no messages"
                body="The export parsed, but every entry was a service event or an empty message."
              />
            </Card>
          ) : (
            <>
              <div className="print-header print-only">
                <div className="print-header-top">
                  <div className="print-brand">
                    <svg className="print-brand-mark" viewBox="0 0 28 28" fill="none" aria-hidden="true">
                      <rect
                        x="0.75"
                        y="0.75"
                        width="26.5"
                        height="26.5"
                        rx="8"
                        stroke="currentColor"
                        strokeOpacity="0.25"
                      />
                      <path
                        d="M8 18.5V13M14 18.5V8.5M20 18.5v-3.2"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                    <span className="print-brand-name">TELEGNIZE</span>
                    <span className="print-brand-tag">Analytics Dossier</span>
                  </div>
                  <div className="print-meta-right">
                    Generated on{" "}
                    {new Date().toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
                <div className="print-title-area">
                  <h1 className="print-chat-title">{data.chat_name}</h1>
                  <div className="print-chat-sub">
                    <span>{compact(data.total_messages)} messages</span>
                    {data.date_range_start && data.date_range_end && (
                      <>
                        <span className="print-sep">·</span>
                        <span>
                          {dateOnly(data.date_range_start)} → {dateOnly(data.date_range_end)} (
                          {int(rhythm?.span_days ?? 0)} days)
                        </span>
                      </>
                    )}
                    <span className="print-sep">·</span>
                    <span>{participants.map((p) => p.sender_name).join(", ")}</span>
                  </div>
                </div>
              </div>
              <div className="grid grid--hero">
                <Card fill>
                  <Hero
                    label="Total messages"
                    value={compact(data.total_messages)}
                    note={
                      rhythm && rhythm.span_days
                        ? `${dateOnly(data.date_range_start)} → ${dateOnly(data.date_range_end)} · ${int(rhythm.span_days)} days`
                        : undefined
                    }
                  />
                </Card>

                <div className="stat-grid">
                  <Stat label="Participants" value={int(participants.length)} />
                  <Stat
                    label="Avg reply"
                    value={duration(data.avg_response_time_seconds)}
                    note="across everyone"
                  />
                  <Stat label="Busiest hour" value={`${busiest.label}:00`} note={`${int(busiest.value)} messages`} />
                  <Stat label="Busiest day" value={busiestDay.key.slice(0, 3)} note={`${int(busiestDay.value)} messages`} />
                </div>
              </div>

              {rhythm && (
                <Card
                  title="Rhythm"
                  subtitle="A session is a run of messages with no long silence in it — roughly, one sitting."
                >
                  <div className="stat-grid stat-grid--plain">
                    <Stat
                      label="Sessions"
                      value={compact(rhythm.session_count)}
                      note={`${rhythm.avg_messages_per_session.toFixed(0)} messages each`}
                    />
                    <Stat
                      label="Typical session"
                      value={minutes(rhythm.avg_session_minutes)}
                      note="one sitting"
                    />
                    <Stat
                      label="Active days"
                      value={`${int(rhythm.active_days)} / ${int(rhythm.span_days)}`}
                      note={`${pct(rhythm.active_day_percent)} of the span`}
                    />
                    <Stat
                      label="Longest silence"
                      value={days(rhythm.longest_silence_days)}
                      note="no contact"
                    />
                    <Stat
                      label="Late night"
                      value={pct(rhythm.late_night_percent)}
                      note="midnight to 05:00"
                    />
                    <Stat
                      label="Silences"
                      value={int(rhythm.silence_count)}
                      note="over 48 hours"
                    />
                  </div>
                </Card>
              )}

              <Plot
                title="When they talk"
                subtitle="Messages by hour of day"
                rows={hourly}
                columns={["Hour", "Messages"]}
              >
                <ColumnChart data={hourly} labelEvery={3} />
              </Plot>

              <div className="grid grid--2">
                <Plot
                  title="Which days they talk"
                  subtitle="Messages by day of week"
                  rows={weekly}
                  columns={["Day", "Messages"]}
                >
                  <ColumnChart data={weekly} />
                </Plot>

                <Card title="Language" subtitle="Script classification of every stored message" fill>
                  {languages.length ? <ShareStrip slices={languages} /> : <Empty title="No language data" />}
                </Card>
              </div>

              <BodyClock participants={participants} />

              <LatencyTrend participants={participants} />

              {data.style_matching && <StyleMatchingCard matching={data.style_matching} />}

              {balance && (
                <Card
                  title="Balance"
                  subtitle="100% is an even split, falling toward 0 as one person dominates."
                >
                  <div className="stat-grid stat-grid--plain">
                    <BalanceMeter
                      label="Messages"
                      value={balance.message_balance_percent}
                      hint="How evenly the message count is shared"
                    />
                    <BalanceMeter
                      label="Words"
                      value={balance.word_balance_percent}
                      hint="How evenly the word count is shared"
                    />
                    <BalanceMeter
                      label="Who opens"
                      value={balance.initiation_balance_percent}
                      hint="How evenly conversations are started"
                    />
                    <div title="Slowest participant's median reply over the fastest's">
                      <div className="stat-label">Reply-time ratio</div>
                      <div className="stat-value">{ratio(balance.response_time_ratio)}</div>
                      <div className="stat-note">1.00× is the same pace</div>
                    </div>
                  </div>
                </Card>
              )}

              <div className="screen-only-participants">
                <Participants
                  participants={participants}
                  chatId={data.chat_id}
                  onRederived={reload}
                />
              </div>

              <div className="print-full-dossier">
                {GROUPS.map((g) => {
                  const columns = COLUMNS[g.value];
                  return (
                    <Card
                      key={g.value}
                      title={`Participants · ${g.label}`}
                      subtitle={GROUP_NOTE[g.value]}
                      flush
                    >
                      <div className="table-wrap">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Participant</th>
                              {columns.map((column) => (
                                <th key={column.key} className="num" title={column.hint}>
                                  {column.label}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {participants.map((person) => (
                              <tr key={person.sender_id}>
                                <td>
                                  <div style={{ fontWeight: 500 }}>{person.sender_name}</div>
                                  <div className="share" style={{ marginTop: 5, maxWidth: 180 }}>
                                    <span className="share-track">
                                      <span
                                        className="share-fill"
                                        style={{ width: `${person.message_share_percent}%` }}
                                      />
                                    </span>
                                    <span className="share-value">{pct(person.message_share_percent)}</span>
                                  </div>
                                </td>
                                {columns.map((column) => (
                                  <td key={column.key} className="num">
                                    {column.render(person)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
