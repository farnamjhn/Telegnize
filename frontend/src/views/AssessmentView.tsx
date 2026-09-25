import { useEffect, useRef, useState } from "react";

import { ChatSelect } from "../App";
import { Card, Empty, Field, Hero, Icon, Notice, Spinner } from "../components/Primitives";
import { ShareStrip, type Slice } from "../components/charts";
import { ExportModal, PrintHeader, triggerPdfExport } from "../components/ExportModal";
import { ApiError, api } from "../lib/api";
import { compact, int, pct, pctOrDash, rate } from "../lib/format";
import type { AssessmentRun, Chat, ParticipantAssessment } from "../lib/types";
import { useAsync } from "../lib/useAsync";

/** Small by default. A full pass runs a model over every message, which on a
 *  large chat is hours — so the page size is a deliberate choice, not a
 *  default to fall into. Time a page before raising it. */
const PAGE_SIZES = [5, 25, 50, 100, 200];

/** How often a running assessment is asked how far it has got. */
const POLL_MS = 1000;

function seconds(value: number): string {
  if (value < 60) return `${value.toFixed(1)}s`;
  const minutes = Math.floor(value / 60);
  return `${minutes}m ${Math.round(value % 60)}s`;
}

/** What the background run is doing, in a sentence. */
function RunNotice({ run }: { run: AssessmentRun }) {
  const counts =
    `${int(run.assessed)} assessed` +
    (run.skipped > 0 ? `, ${int(run.skipped)} already done` : "") +
    ` in ${seconds(run.elapsed_seconds)}` +
    (run.seconds_per_message != null ? ` (${run.seconds_per_message.toFixed(2)}s a message)` : "");

  switch (run.state) {
    case "loading":
      return (
        <Notice>
          <span className="spinner" /> Loading the model — the first run of a session pays this
          once, and it can take a minute. {seconds(run.elapsed_seconds)} so far.
        </Notice>
      );
    case "running":
    case "stopping":
      return (
        <Notice>
          <span className="spinner" /> {run.state === "stopping" ? "Finishing the page in flight. " : ""}
          Page {int(run.pages + 1)}
          {run.max_pages != null ? ` of ${int(run.max_pages)}` : ""}, from message{" "}
          {int(run.next_offset)} — {counts}. Coverage {pct(run.coverage_percent)}. You can leave
          this view; the run keeps going.
        </Notice>
      );
    case "done":
      return (
        <Notice tone="good">
          Done: {counts}.{" "}
          {run.coverage_percent >= 100
            ? "The chat is fully assessed."
            : `Resume at ${int(run.next_offset)}.`}
        </Notice>
      );
    case "stopped":
      return (
        <Notice>
          Stopped: {counts}. Resume at {int(run.next_offset)}.
        </Notice>
      );
    case "failed":
      return (
        <Notice tone="error">
          The run failed after {int(run.assessed)} messages: {run.error}. Resume at{" "}
          {int(run.next_offset)}.
        </Notice>
      );
    default:
      return null;
  }
}

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
  const [run, setRun] = useState<AssessmentRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);

  const assessment = useAsync(
    () => (chatId == null ? null : api.assessment(chatId)),
    [chatId],
  );
  const reloadAssessment = assessment.reload;

  const active = run?.is_active ?? false;

  // The run lives on the server, so picking a chat — or coming back to this
  // view — picks up whatever that chat's run is doing.
  useEffect(() => {
    setRun(null);
    setError(null);
    if (chatId == null) return;
    let cancelled = false;
    api.assessmentRun(chatId).then(
      (status) => {
        if (cancelled) return;
        if (status.state === "idle") return;
        setRun(status);
        setOffset(status.next_offset);
      },
      () => undefined,
    );
    return () => {
      cancelled = true;
    };
  }, [chatId]);

  // Poll while a run is going. The aggregate is re-read whenever a page lands,
  // so the tables fill in as the run works rather than at the end.
  const pagesSeen = useRef(0);
  useEffect(() => {
    if (chatId == null || !active) return;
    let cancelled = false;
    const tick = window.setInterval(() => {
      api.assessmentRun(chatId).then(
        (status) => {
          if (cancelled) return;
          setRun(status);
          setOffset(status.next_offset);
          if (status.pages !== pagesSeen.current || !status.is_active) {
            pagesSeen.current = status.pages;
            reloadAssessment();
          }
        },
        (cause: unknown) => {
          if (!cancelled) setError(cause instanceof ApiError ? cause.message : String(cause));
        },
      );
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(tick);
    };
  }, [chatId, active, reloadAssessment]);

  /** Starts a background run: one page, or until the chat is done. */
  async function start(pages: number | null) {
    if (chatId == null) return;
    setError(null);
    pagesSeen.current = 0;
    try {
      setRun(await api.startAssessmentRun(chatId, offset, pageSize, pages));
    } catch (cause) {
      setError(
        // A plain 404 with no chat named means the route itself is missing:
        // the page was updated and the API process is still the old one.
        cause instanceof ApiError && cause.status === 404 && cause.message === "Not Found"
          ? "The API server is running older code that cannot run assessments in the background. Restart it (stop launch.sh and run it again), then try again."
          : cause instanceof ApiError
            ? cause.message
            : String(cause),
      );
    }
  }

  async function stop() {
    if (chatId == null) return;
    try {
      setRun(await api.stopAssessmentRun(chatId));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
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
  const chatName = chats.find((c) => c.id === chatId)?.name ?? "Chat";

  function handleTriggerExport(options: { theme: "light" | "dark" }) {
    if (!data) return;
    const safeChatName = chatName.replace(/[/\\?%*:|"<>]/g, "-").trim() || "Chat";
    triggerPdfExport({ theme: options.theme, documentTitle: `${safeChatName} - Telegnize Assessment` });
  }

  return (
    <div className="view">
      <ExportModal
        title="Export Assessment to PDF"
        subtitle={`${chatName} · ${int(data?.assessed_messages ?? 0)} messages read`}
        isOpen={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onExport={handleTriggerExport}
      />

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
            }}
          />
        </Field>
        <Field label="Page size" htmlFor="assessment-page" tight>
          <select
            id="assessment-page"
            className="select"
            value={pageSize}
            disabled={active}
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
            disabled={active}
            onChange={(event) => setOffset(Math.max(0, Number(event.target.value) || 0))}
          />
        </Field>
        {active ? (
          <button
            className="btn btn--primary"
            disabled={run?.state === "stopping"}
            onClick={() => void stop()}
          >
            <span className="spinner" />
            {run?.state === "stopping" ? "Stopping after this page…" : "Stop"}
          </button>
        ) : (
          <>
            <button
              className="btn btn--primary"
              disabled={chatId == null}
              onClick={() => void start(null)}
            >
              Assess to the end
            </button>
            <button
              className="btn btn--ghost"
              disabled={chatId == null}
              onClick={() => void start(1)}
            >
              Assess {pageSize} messages
            </button>
          </>
        )}
        <button
          type="button"
          className="btn"
          onClick={() => setExportModalOpen(true)}
          disabled={!started}
          title="Export the assessment report to PDF"
          style={{ marginInlineStart: "auto" }}
        >
          <Icon name="pdf" size={15} />
          Export to PDF
        </button>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {run && <RunNotice run={run} />}

      {assessment.error && <Notice tone="error">{assessment.error}</Notice>}
      {assessment.loading && (
        <Card>
          <Spinner label="Loading the assessment…" />
        </Card>
      )}

      {data && (
        <div className={assessment.refetching ? "stack-v is-refetching" : "stack-v"}>
          <PrintHeader
            tag="Assessment Report"
            title={chatName}
            subLine={
              <>
                <span>{compact(data.assessed_messages)} of {compact(data.total_messages)} messages read</span>
                <span className="print-sep">·</span>
                <span>{pct(data.coverage_percent)} coverage</span>
                <span className="print-sep">·</span>
                <span>{participants.map((p) => p.sender_name).join(", ")}</span>
              </>
            }
          />
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

              {GROUPS.map((g) => {
                const groupColumns = COLUMNS[g.value];
                return (
                  <Card key={g.value} title={`Participants · ${g.label}`} subtitle={GROUP_NOTE[g.value]} flush>
                    <div className="table-wrap">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Participant</th>
                            {groupColumns.map((column) => (
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
                              {groupColumns.map((column) => (
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
