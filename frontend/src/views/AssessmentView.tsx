import { useState } from "react";

import { ChatSelect } from "../App";
import { Card, Empty, Field, Hero, Notice, Spinner, Toggle } from "../components/Primitives";
import { ShareStrip, type Slice } from "../components/charts";
import { ApiError, api } from "../lib/api";
import { compact, int, pct, pctOrDash, rate } from "../lib/format";
import type { AssessmentProgress, Chat, ParticipantAssessment } from "../lib/types";
import { useAsync } from "../lib/useAsync";

/** Small by default. A full pass runs a model over every message, which on a
 *  large chat is hours — so the page size is a deliberate choice, not a
 *  default to fall into. Time a page before raising it. */
const PAGE_SIZES = [5, 25, 50, 100, 200];

type Group = "valence" | "bids" | "friction" | "discourse";

const GROUPS = [
  { value: "valence", label: "Valence" },
  { value: "bids", label: "Bids" },
  { value: "friction", label: "Friction" },
  { value: "discourse", label: "Discourse" },
] as const;

const GROUP_NOTE: Record<Group, string> = {
  valence:
    "How each message read. The well-known 5:1 ratio is not a threshold to hold this against — it comes from coded observation of people in a room, not from a classifier reading text.",
  bids:
    "Reaching out, and whether the reply engaged. Computed over bids that got a reply inside the assessed range; in a two-person chat it describes how the other participant responded.",
  friction:
    "Named for Gottman's categories, which a classifier reading chat text shares the vocabulary of and none of the validation. Use these to find stretches worth reading yourself.",
  discourse: "What each message was doing, as a conversational move.",
};

interface Column {
  key: string;
  label: string;
  render: (person: ParticipantAssessment) => string;
  hint?: string;
}

const COLUMNS: Record<Group, Column[]> = {
  valence: [
    { key: "assessed", label: "Assessed", render: (p) => compact(p.assessed_message_count) },
    { key: "positive", label: "Positive", render: (p) => compact(p.positive_count) },
    { key: "neutral", label: "Neutral", render: (p) => compact(p.neutral_count) },
    { key: "negative", label: "Negative", render: (p) => compact(p.negative_count) },
    {
      key: "ratio",
      label: "Positivity",
      render: (p) => (p.positivity_ratio == null ? "—" : `${p.positivity_ratio.toFixed(2)}:1`),
      hint: "Positive messages per negative one. Undefined when nothing read negative",
    },
  ],
  bids: [
    {
      key: "bids",
      label: "Bids",
      render: (p) => compact(p.bid_count),
      hint: "Reaching out to share a thought, feeling, joke or image",
    },
    { key: "met", label: "Met", render: (p) => compact(p.bids_met_count) },
    {
      key: "metPct",
      label: "Met %",
      render: (p) => pctOrDash(p.bids_met_percent),
      hint: "Bids the other participant engaged with rather than brushing off",
    },
  ],
  friction: [
    {
      key: "criticism",
      label: "Criticism",
      render: (p) => compact(p.criticism_count),
      hint: "Attacks the person rather than the action",
    },
    { key: "defensiveness", label: "Defensiveness", render: (p) => compact(p.defensiveness_count) },
    {
      key: "contempt",
      label: "Contempt",
      render: (p) => compact(p.contempt_count),
      hint: "Mockery, sneering, name-calling, condescension",
    },
    { key: "frictionPct", label: "Friction %", render: (p) => pct(p.friction_percent) },
    {
      key: "repair",
      label: "Repair",
      render: (p) => `${compact(p.repair_count)} · ${pct(p.repair_percent)}`,
      hint: "Apologising, making peace, defusing tension",
    },
    {
      key: "sarcasm",
      label: "Sarcasm",
      render: (p) => (p.avg_sarcasm_score == null ? "—" : p.avg_sarcasm_score.toFixed(2)),
      hint: "0 is straightforward, 3 is heavily barbed",
    },
  ],
  discourse: [
    { key: "statements", label: "Statements", render: (p) => compact(p.statement_count) },
    { key: "closed", label: "Closed Q", render: (p) => compact(p.closed_question_count) },
    {
      key: "open",
      label: "Open Q",
      render: (p) => compact(p.open_question_count),
      hint: "Invites the other person to open up, or discloses something personal",
    },
    {
      key: "curiosity",
      label: "Curiosity / 1k",
      render: (p) => rate(p.curiosity_per_1k_words),
      hint: "Open questions and self-disclosures per thousand words",
    },
  ],
};

/** Positive reads white, negative orange — orange is the alarm end of every
 *  scale in this UI, and valence is the clearest case of one. */
function valenceSlices(person: ParticipantAssessment): Slice[] {
  return [
    { key: "positive", label: "Positive", value: person.positive_count, color: "var(--series-1)" },
    { key: "neutral", label: "Neutral", value: person.neutral_count, color: "var(--series-3)" },
    { key: "negative", label: "Negative", value: person.negative_count, color: "var(--series-2)" },
  ];
}

export function AssessmentView({
  chats,
  chatId,
  onChatId,
}: {
  chats: Chat[];
  chatId: number | null;
  onChatId: (id: number) => void;
}) {
  const [pageSize, setPageSize] = useState(25);
  const [offset, setOffset] = useState(0);
  const [progress, setProgress] = useState<AssessmentProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [group, setGroup] = useState<Group>("valence");

  const assessment = useAsync(
    () => (chatId == null ? null : api.assessment(chatId)),
    [chatId],
  );

  async function assessNextPage() {
    if (chatId == null) return;
    setRunning(true);
    setError(null);
    try {
      const result = await api.assessPage(chatId, offset, pageSize);
      setProgress(result);
      setOffset(result.next_offset);
      assessment.reload();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setRunning(false);
    }
  }

  if (chats.length === 0) {
    return (
      <div className="view">
        <header className="view-head">
          <h1 className="view-title">Assessment</h1>
        </header>
        <Card>
          <Empty title="Nothing to assess" body="Import a Telegram export from the Chats tab first." />
        </Card>
      </div>
    );
  }

  const data = assessment.data;
  const participants = data?.participants ?? [];
  const started = (data?.assessed_messages ?? 0) > 0;
  const columns = COLUMNS[group];

  return (
    <div className="view">
      <header className="view-head">
        <div>
          <h1 className="view-title">Assessment</h1>
          <p className="view-sub">
            Classified figures — a model reads every message and answers a fixed question set.
            Unlike the counted figures in Analytics, these are a reading, and a reading can be
            wrong about any individual message. Read every one against the coverage below.
          </p>
        </div>
      </header>

      <div className="filters">
        <Field label="Chat" htmlFor="assessment-chat">
          <ChatSelect
            id="assessment-chat"
            chats={chats}
            value={chatId}
            onChange={(id) => {
              onChatId(id);
              setOffset(0);
              setProgress(null);
            }}
          />
        </Field>
        <Field label="Page size" htmlFor="assessment-page" tight>
          <select
            id="assessment-page"
            className="select"
            value={pageSize}
            onChange={(event) => setPageSize(Number(event.target.value))}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Resume at" htmlFor="assessment-offset" tight>
          <input
            id="assessment-offset"
            className="input num"
            type="number"
            min={0}
            value={offset}
            onChange={(event) => setOffset(Math.max(0, Number(event.target.value) || 0))}
          />
        </Field>
        <button
          className="btn btn--primary"
          disabled={chatId == null || running}
          onClick={() => void assessNextPage()}
        >
          {running && <span className="spinner" />}
          Assess {pageSize} messages
        </button>
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      {running && (
        <Notice>
          Running the question set over {pageSize} messages. Every message that has not been
          read yet costs a forward pass, so time a small page on this machine before committing
          to a long run. The first call of a session also loads the checkpoints, which it pays
          once.
        </Notice>
      )}

      {progress && !running && (
        <Notice tone="good">
          Assessed {int(progress.assessed_now)}
          {progress.skipped_already_done > 0 &&
            `, skipped ${int(progress.skipped_already_done)} already done`}
          . {progress.is_complete ? "The chat is fully assessed." : `Resume at ${int(progress.next_offset)}.`}
        </Notice>
      )}

      {assessment.error && <Notice tone="error">{assessment.error}</Notice>}
      {assessment.loading && (
        <Card>
          <Spinner label="Loading the assessment…" />
        </Card>
      )}

      {data && (
        <div className={assessment.refetching ? "stack-v is-refetching" : "stack-v"}>
          <div className="grid grid--hero">
            <Card fill>
              <Hero
                label="Coverage"
                value={pct(data.coverage_percent)}
                note={`${compact(data.assessed_messages)} of ${compact(data.total_messages)} messages read`}
              />
            </Card>
            <Card fill>
              <div className="meter" style={{ height: 8 }}>
                <div className="meter-fill" style={{ width: `${data.coverage_percent}%` }} />
              </div>
              <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
                {started
                  ? "There is no requirement to assess a whole chat, and usually no reason to. A few hundred messages is enough to read a rate off, and the coverage figure keeps a partial result honest."
                  : "Nothing assessed yet. Time one small page on this machine before committing to a long run — a full pass over a large chat can take hours."}
              </p>
            </Card>
          </div>

          {!started ? (
            <Card>
              <Empty
                title="No assessment yet"
                body="Assess a page above to begin. The pass is resumable and cached, so re-running a range costs nothing."
              />
            </Card>
          ) : (
            <>
              <Card
                title="Valence"
                subtitle="How each assessed message read, per participant."
              >
                <div style={{ display: "grid", gap: 18 }}>
                  {participants.map((person) => (
                    <div key={person.sender_id}>
                      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{person.sender_name}</span>
                        <span className="faint" style={{ fontSize: 12 }}>
                          {person.positivity_ratio == null
                            ? "no negative messages read"
                            : `${person.positivity_ratio.toFixed(2)}:1 positive to negative`}
                        </span>
                      </div>
                      <ShareStrip slices={valenceSlices(person)} />
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="Participants" subtitle={GROUP_NOTE[group]}
                action={<Toggle label="Metric group" value={group} onChange={setGroup} options={GROUPS} />}
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
                          <td style={{ fontWeight: 500 }}>{person.sender_name}</td>
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

              <Notice>
                These borrow the vocabulary of Gottman's observational research, which coded
                trained observers watching people over years against real outcomes. A classifier
                reading chat text inherits none of that validation, text strips tone, and a chat
                is a slice of a relationship that also happens in person and in silence. Use
                these to find stretches of conversation worth reading yourself, not to conclude
                anything.
              </Notice>
            </>
          )}
        </div>
      )}
    </div>
  );
}
