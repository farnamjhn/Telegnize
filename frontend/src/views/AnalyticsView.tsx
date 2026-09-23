import { useState } from "react";

import { ChatSelect } from "../App";
import {
  Card,
  Empty,
  Field,
  Hero,
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
import type { Chat, ParticipantStats } from "../lib/types";
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

type MetricGroup = "volume" | "responsiveness" | "engagement" | "expression";

const GROUPS = [
  { value: "volume", label: "Volume" },
  { value: "responsiveness", label: "Responsiveness" },
  { value: "engagement", label: "Engagement" },
  { value: "expression", label: "Expression" },
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
};

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

/** Expression markers are written to columns as messages are stored, so a chat
 *  imported before that feature landed reads as all-zero rather than empty. */
function hasMarkers(participants: ParticipantStats[]): boolean {
  return participants.some((p) =>
    [
      p.expression.emoji_count,
      p.expression.affection_count,
      p.expression.apology_count,
      p.expression.gratitude_count,
      p.expression.exclamation_count,
      p.expression.self_reference_count,
      p.expression.collective_reference_count,
    ].some((count) => count > 0),
  );
}

function Participants({ participants }: { participants: ParticipantStats[] }) {
  const [group, setGroup] = useState<MetricGroup>("volume");
  const columns = COLUMNS[group];
  const markersMissing = group === "expression" && !hasMarkers(participants);

  return (
    <Card
      title="Participants"
      subtitle={GROUP_NOTE[group]}
      action={<Toggle label="Metric group" value={group} onChange={setGroup} options={GROUPS} />}
      flush
    >
      {markersMissing && (
        <div style={{ padding: "0 var(--pad-card) 4px" }}>
          <Notice tone="error">
            Every marker reads zero. These counts are written as messages are stored, so a
            chat imported before the expression metrics existed has none — re-import the
            export to fill them in.
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
  const { data, error, loading, refetching } = useAsync(
    () => (chatId == null ? null : api.analytics(chatId)),
    [chatId],
  );

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
      <div className="filters">
        <Field label="Chat" htmlFor="analytics-chat">
          <ChatSelect id="analytics-chat" chats={chats} value={chatId} onChange={onChatId} />
        </Field>
        {refetching && <Spinner />}
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

              <LatencyTrend participants={participants} />

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

              <Participants participants={participants} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
