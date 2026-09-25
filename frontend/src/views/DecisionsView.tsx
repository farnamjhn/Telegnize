import { useState } from "react";

import { ChatSelect } from "../App";
import { Badge, Card, Empty, Field, Icon, Notice } from "../components/Primitives";
import { ProbabilityBars } from "../components/charts";
import { ExportModal, PrintHeader, triggerPdfExport } from "../components/ExportModal";
import { ApiError, api } from "../lib/api";
import { dateTime, decisionValue, directionOf, humanize } from "../lib/format";
import type { Chat, Decision } from "../lib/types";
import { useAsync } from "../lib/useAsync";

type Mode = "chat" | "message";

/** Confidence is a state, so it wears the reserved status colors — always
 *  beside its own word, never color alone. */
function confidenceBand(confidence: number): { label: string; color: string } {
  if (confidence >= 0.7) return { label: "High confidence", color: "var(--good)" };
  if (confidence >= 0.4) return { label: "Moderate confidence", color: "var(--warning)" };
  return { label: "Low confidence", color: "var(--critical)" };
}

/** For a whole-chat reading, how much of the chat it actually read. */
function coverageNote(decision: Decision): string | null {
  const meta = decision.engine_metadata ?? {};
  if (meta.scope !== "whole_chat") return null;
  const windows = Number(meta.windows);
  const read = Number(meta.messages_read);
  const total = Number(meta.total_messages);
  return (
    `Combined from ${windows.toLocaleString("en-US")} window${windows === 1 ? "" : "s"} ` +
    `across the chat — ${read.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} messages read.`
  );
}

function DecisionCard({ decision }: { decision: Decision }) {
  const band = confidenceBand(decision.confidence);
  const winner = typeof decision.result_value === "string" ? decision.result_value : undefined;

  return (
    <Card title={humanize(decision.question_key)} action={<Badge variant="quiet">{decision.decision_type}</Badge>}>
      <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>
        {decisionValue(decision.result_value)}
      </div>

      <div className="row" style={{ gap: 8, marginTop: 10, marginBottom: 6 }}>
        <span className="dot" style={{ color: band.color }} />
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{band.label}</span>
        <span className="share-value" style={{ marginInlineStart: "auto" }}>
          {(decision.confidence * 100).toFixed(1)}%
        </span>
      </div>
      <div className="meter">
        <div
          className="meter-fill"
          style={{ width: `${decision.confidence * 100}%`, background: band.color }}
        />
      </div>

      {Object.keys(decision.probabilities).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <ProbabilityBars
            probabilities={decision.probabilities}
            winner={winner}
            format={humanize}
          />
        </div>
      )}

      {coverageNote(decision) && (
        <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
          {coverageNote(decision)}
        </p>
      )}

      {decision.created_at && (
        <p className="faint" style={{ fontSize: 11, marginTop: 14 }}>
          Cached {dateTime(decision.created_at)}
        </p>
      )}
    </Card>
  );
}

export function DecisionsView({
  chats,
  chatId,
  onChatId,
  messageTarget,
  onMessageTarget,
}: {
  chats: Chat[];
  chatId: number | null;
  onChatId: (id: number) => void;
  messageTarget: number | null;
  onMessageTarget: (id: number | null) => void;
}) {
  const [mode, setMode] = useState<Mode>(messageTarget != null ? "message" : "chat");
  const [windowSize, setWindowSize] = useState(20);
  const [wholeChat, setWholeChat] = useState(false);
  const [decisions, setDecisions] = useState<Decision[] | null>(null);
  const [busy, setBusy] = useState<"run" | "cache" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState<string | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);

  const preview = useAsync(
    () => (mode === "message" && messageTarget != null ? api.getMessage(messageTarget) : null),
    [mode, messageTarget],
  );

  const ready = mode === "chat" ? chatId != null : messageTarget != null;

  async function call(kind: "run" | "cache") {
    if (!ready) return;
    setBusy(kind);
    setError(null);
    setEmpty(null);
    try {
      const result =
        mode === "chat"
          ? kind === "run"
            ? await api.evaluateChat(chatId!, windowSize, wholeChat)
            : await api.cachedChatDecisions(chatId!)
          : kind === "run"
            ? await api.evaluateMessage(messageTarget!)
            : await api.cachedMessageDecisions(messageTarget!);
      setDecisions(result);
      if (result.length === 0) {
        setEmpty(
          kind === "cache"
            ? "Nothing cached for this target yet — run an evaluation first."
            : "The engine returned no decisions for this target.",
        );
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
      setDecisions(null);
    } finally {
      setBusy(null);
    }
  }

  if (chats.length === 0) {
    return (
      <div className="view">
        <header className="view-head">
          <h1 className="view-title">Decisions</h1>
        </header>
        <Card>
          <Empty title="Nothing to decide about" body="Import a Telegram export from the Chats tab first." />
        </Card>
      </div>
    );
  }

  const chatName = chats.find((c) => c.id === chatId)?.name ?? "Chat";
  const targetLabel =
    mode === "chat"
      ? chatName
      : preview.data
        ? `${preview.data.sender_name} · ${dateTime(preview.data.timestamp)}`
        : `Message ${messageTarget ?? ""}`;

  function handleTriggerExport(options: { theme: "light" | "dark" }) {
    if (!decisions || decisions.length === 0) return;
    const safeTarget = targetLabel.replace(/[/\\?%*:|"<>]/g, "-").trim() || "Decisions";
    triggerPdfExport({ theme: options.theme, documentTitle: `${safeTarget} - Telegnize Decisions` });
  }

  return (
    <div className="view">
      <ExportModal
        title="Export Decisions to PDF"
        subtitle={`${targetLabel} · ${decisions?.length ?? 0} decision${decisions?.length === 1 ? "" : "s"}`}
        isOpen={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onExport={handleTriggerExport}
      />

      <header className="view-head">
        <div>
          <h1 className="view-title">Decisions</h1>
          <p className="view-sub">
            Typed answers from the Laya System 1 engine — a tone, a dynamic, a yes/no — each with
            the probability it assigned to every alternative.
          </p>
        </div>
      </header>

      <div className="filters">
        <Field label="Target">
          <div className="seg" role="group" aria-label="Decision target">
            <button
              type="button"
              aria-pressed={mode === "chat"}
              onClick={() => {
                setMode("chat");
                setDecisions(null);
              }}
            >
              Conversation
            </button>
            <button
              type="button"
              aria-pressed={mode === "message"}
              onClick={() => {
                setMode("message");
                setDecisions(null);
              }}
            >
              Message
            </button>
          </div>
        </Field>

        {mode === "chat" ? (
          <>
            <Field label="Chat" htmlFor="decisions-chat">
              <ChatSelect id="decisions-chat" chats={chats} value={chatId} onChange={onChatId} />
            </Field>
            <Field label="Window">
              <div className="seg" role="group" aria-label="Window">
                <button
                  type="button"
                  aria-pressed={!wholeChat}
                  onClick={() => setWholeChat(false)}
                >
                  Recent
                </button>
                <button
                  type="button"
                  aria-pressed={wholeChat}
                  onClick={() => setWholeChat(true)}
                >
                  Whole chat
                </button>
              </div>
            </Field>
            {!wholeChat && (
              <Field label="Turns" htmlFor="decisions-window" tight>
                <input
                  id="decisions-window"
                  className="input num"
                  type="number"
                  min={1}
                  max={200}
                  value={windowSize}
                  onChange={(event) =>
                    setWindowSize(Math.min(200, Math.max(1, Number(event.target.value) || 1)))
                  }
                />
              </Field>
            )}
          </>
        ) : (
          <Field label="Message id" htmlFor="decisions-message">
            <input
              id="decisions-message"
              className="input num"
              type="number"
              min={1}
              placeholder="e.g. 42"
              value={messageTarget ?? ""}
              onChange={(event) => {
                const next = Number(event.target.value);
                onMessageTarget(Number.isFinite(next) && next > 0 ? next : null);
                setDecisions(null);
              }}
            />
          </Field>
        )}

        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn--primary" disabled={!ready || busy !== null} onClick={() => void call("run")}>
            {busy === "run" && <span className="spinner" />}
            Evaluate
          </button>
          <button className="btn" disabled={!ready || busy !== null} onClick={() => void call("cache")}>
            Load cached
          </button>
        </div>

        <button
          type="button"
          className="btn"
          onClick={() => setExportModalOpen(true)}
          disabled={!decisions || decisions.length === 0}
          title="Export these decisions to PDF"
          style={{ marginInlineStart: "auto" }}
        >
          <Icon name="pdf" size={15} />
          Export to PDF
        </button>
      </div>

      {mode === "message" && preview.data && (
        <Card title="Target message" subtitle={`${preview.data.sender_name} · ${dateTime(preview.data.timestamp)}`}>
          <p className="msg-text" dir={directionOf(preview.data)}>
            {preview.data.text || "— no text —"}
          </p>
        </Card>
      )}
      {mode === "message" && preview.error && <Notice tone="error">{preview.error}</Notice>}

      {busy === "run" && (
        <Notice>
          Evaluating. The first run after a restart loads the model weights, which can take
          a while; every run after that is fast.
        </Notice>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {empty && <Notice>{empty}</Notice>}

      {decisions && decisions.length > 0 ? (
        <>
          <PrintHeader
            tag="Decisions Report"
            title={targetLabel}
            subLine={<span>{decisions.length} decision{decisions.length === 1 ? "" : "s"}</span>}
          />
          <div className="grid grid--2">
            {decisions.map((decision) => (
              <DecisionCard key={`${decision.target_type}-${decision.target_id}-${decision.question_key}`} decision={decision} />
            ))}
          </div>
        </>
      ) : (
        !error &&
        !empty &&
        busy === null && (
          <Card>
            <Empty
              title="No evaluation yet"
              body={
                mode === "chat"
                  ? wholeChat
                    ? "Evaluate reads windows spread evenly across the whole chat — up to 40 of them — asks each about the relationship dynamic and the overall sentiment, and combines the answers."
                    : "Evaluate reads the chat's most recent window and asks about the relationship dynamic and the overall sentiment."
                  : "Pick a message — from here or from the Messages tab — and Evaluate asks about its tone and whether it carries conflict."
              }
            />
          </Card>
        )
      )}
    </div>
  );
}
