import { useRef, useState } from "react";

import { Badge, Card, Empty, Icon, Notice, Spinner } from "../components/Primitives";
import type { ViewName } from "../components/Shell";
import { ApiError, api } from "../lib/api";
import { dateOnly, int } from "../lib/format";
import type { Chat, ImportSummary } from "../lib/types";
import type { AsyncState } from "../lib/useAsync";

export function ChatsView({
  state,
  onOpen,
}: {
  state: AsyncState<Chat[]>;
  onOpen: (chatId: number, view: ViewName) => void;
}) {
  const chats = state.data ?? [];

  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [path, setPath] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  async function run(label: string, task: () => Promise<ImportSummary>) {
    setBusy(label);
    setError(null);
    setResult(null);
    try {
      setResult(await task());
      state.reload();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  const upload = (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".json")) {
      setError("Telegram exports are JSON — pick the result.json from the export folder.");
      return;
    }
    void run("upload", () => api.uploadChat(file));
  };

  async function remove(chat: Chat) {
    if (!window.confirm(`Delete “${chat.name}” and all ${int(chat.total_messages)} of its messages?`)) {
      return;
    }
    setError(null);
    try {
      await api.deleteChat(chat.id);
      state.reload();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  }

  return (
    <div className="view">
      <header className="view-head">
        <div>
          <h1 className="view-title">Chats</h1>
          <p className="view-sub">
            Import a Telegram export and Telegnize streams it into storage — a multi-gigabyte
            file costs the same memory as a small one.
          </p>
        </div>
      </header>

      {error && <Notice tone="error">{error}</Notice>}
      {result && (
        <Notice tone="good">
          Imported <strong>{result.chat.name}</strong> — {int(result.total_messages)} messages.
        </Notice>
      )}

      <div className="grid grid--2">
        <Card title="Upload an export" subtitle="The result.json Telegram writes into the export folder.">
          <div
            className={over ? "drop is-over" : "drop"}
            onClick={() => fileInput.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setOver(false);
              upload(event.dataTransfer.files[0]);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") fileInput.current?.click();
            }}
          >
            {busy === "upload" ? (
              <Spinner label="Streaming the export…" />
            ) : (
              <>
                <Icon name="upload" size={22} />
                <span style={{ fontSize: 13 }}>Drop a .json export here, or click to choose</span>
                <span className="faint" style={{ fontSize: 12 }}>
                  Parsed as a stream — large files are fine
                </span>
              </>
            )}
          </div>
          <input
            ref={fileInput}
            className="sr-only"
            type="file"
            accept="application/json,.json"
            onChange={(event) => {
              upload(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </Card>

        <Card title="Import from the server" subtitle="A path the API process can read directly.">
          <form
            className="row"
            style={{ gap: 10, flexWrap: "nowrap" }}
            onSubmit={(event) => {
              event.preventDefault();
              if (path.trim()) void run("local", () => api.importLocal(path.trim()));
            }}
          >
            <input
              className="input mono"
              placeholder="/path/to/result.json"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              aria-label="Export path on the server"
            />
            <button className="btn btn--primary" type="submit" disabled={!path.trim() || busy !== null}>
              {busy === "local" ? <span className="spinner" /> : null}
              Import
            </button>
          </form>
          <p className="faint" style={{ fontSize: 12, marginTop: 10 }}>
            Skips the upload entirely — the fastest route for an export that already sits
            next to the server.
          </p>
        </Card>
      </div>

      <Card
        title="Imported chats"
        subtitle={chats.length ? `${chats.length} chat${chats.length === 1 ? "" : "s"} in the database` : undefined}
        flush
      >
        {state.loading ? (
          <div className="card-body">
            <Spinner label="Loading chats…" />
          </div>
        ) : state.error ? (
          <div className="card-body">
            <Notice tone="error">{state.error}</Notice>
          </div>
        ) : chats.length === 0 ? (
          <Empty
            title="Nothing imported yet"
            body="Import an export above and its analytics, messages and decisions unlock."
          />
        ) : (
          <div className={state.refetching ? "table-wrap is-refetching" : "table-wrap"}>
            <table className="table">
              <thead>
                <tr>
                  <th>Chat</th>
                  <th>Type</th>
                  <th className="num">Messages</th>
                  <th>Imported</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {chats.map((chat) => (
                  <tr key={chat.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{chat.name}</div>
                      <div className="faint mono">#{chat.telegram_chat_id}</div>
                    </td>
                    <td>
                      <Badge variant="quiet">{chat.type.replace(/_/g, " ")}</Badge>
                    </td>
                    <td className="num">{int(chat.total_messages)}</td>
                    <td className="muted">{dateOnly(chat.created_at)}</td>
                    <td>
                      <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
                        <button className="btn btn--sm" onClick={() => onOpen(chat.id, "analytics")}>
                          Analytics
                        </button>
                        <button className="btn btn--sm" onClick={() => onOpen(chat.id, "messages")}>
                          Messages
                        </button>
                        <button
                          className="btn btn--sm btn--ghost btn--danger"
                          onClick={() => void remove(chat)}
                          aria-label={`Delete ${chat.name}`}
                        >
                          <Icon name="trash" size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
