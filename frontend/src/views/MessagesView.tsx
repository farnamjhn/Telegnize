import { useEffect, useState } from "react";

import { ChatSelect } from "../App";
import { Badge, Card, Empty, Field, Notice, Spinner, Toggle } from "../components/Primitives";
import { api } from "../lib/api";
import { CONTENT_TYPE_NAMES, dateTime, directionOf, initials, int, languageName } from "../lib/format";
import type { Chat } from "../lib/types";
import { useAsync } from "../lib/useAsync";

const PAGE_SIZES = [25, 50, 100];

type TextMode = "raw" | "normalized";

const TEXT_MODES = [
  { value: "raw", label: "As exported" },
  { value: "normalized", label: "Normalized" },
] as const;

export function MessagesView({
  chats,
  chatId,
  onChatId,
  onAnalyzeMessage,
}: {
  chats: Chat[];
  chatId: number | null;
  onChatId: (id: number) => void;
  onAnalyzeMessage: (messageId: number) => void;
}) {
  const [sender, setSender] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [text, setText] = useState<TextMode>("raw");

  // Participants come from the analytics aggregate — no page of messages can
  // tell you who is in a chat, only who is on that page.
  const people = useAsync(() => (chatId == null ? null : api.analytics(chatId)), [chatId]);

  const messages = useAsync(
    () =>
      chatId == null
        ? null
        : api.listMessages({ chatId, senderId: sender || undefined, limit, offset }),
    [chatId, sender, limit, offset],
  );

  useEffect(() => setOffset(0), [chatId, sender, limit]);
  useEffect(() => setSender(""), [chatId]);

  if (chats.length === 0) {
    return (
      <div className="view">
        <header className="view-head">
          <h1 className="view-title">Messages</h1>
        </header>
        <Card>
          <Empty title="No messages to browse" body="Import a Telegram export from the Chats tab first." />
        </Card>
      </div>
    );
  }

  const rows = messages.data ?? [];
  const showNormalized = text === "normalized";

  return (
    <div className="view">
      <header className="view-head">
        <div>
          <h1 className="view-title">Messages</h1>
          <p className="view-sub">
            Every message is stored twice — exactly as exported, and normalized. Persian text
            is laid out right-to-left on its own.
          </p>
        </div>
      </header>

      <div className="filters">
        <Field label="Chat" htmlFor="messages-chat">
          <ChatSelect id="messages-chat" chats={chats} value={chatId} onChange={onChatId} />
        </Field>
        <Field label="Sender" htmlFor="messages-sender">
          <select
            id="messages-sender"
            className="select"
            value={sender}
            onChange={(event) => setSender(event.target.value)}
          >
            <option value="">Everyone</option>
            {(people.data?.participants ?? []).map((person) => (
              <option key={person.sender_id} value={person.sender_id}>
                {person.sender_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Per page" htmlFor="messages-limit" tight>
          <select
            id="messages-limit"
            className="select"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </Field>
        {messages.refetching && <Spinner />}
      </div>

      {messages.error && <Notice tone="error">{messages.error}</Notice>}

      <Card
        title="Conversation"
        subtitle={rows.length ? `Showing ${int(offset + 1)}–${int(offset + rows.length)}` : undefined}
        action={<Toggle label="Text shown" value={text} onChange={setText} options={TEXT_MODES} />}
        flush
      >
        {messages.loading ? (
          <div className="card-body">
            <Spinner label="Loading messages…" />
          </div>
        ) : rows.length === 0 ? (
          <Empty
            title={offset > 0 ? "End of the conversation" : "No messages here"}
            body={offset > 0 ? "Go back a page to keep reading." : "This filter matched nothing."}
          />
        ) : (
          <div className={messages.refetching ? "msg-list is-refetching" : "msg-list"}>
            {rows.map((message) => {
              const body = showNormalized ? message.normalized_text : message.text;
              const dir = directionOf(message);
              return (
                <article className="msg" key={message.id}>
                  <div className="msg-avatar" aria-hidden="true">
                    {initials(message.sender_name)}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div className="msg-head">
                      <span className="msg-sender">{message.sender_name}</span>
                      <span className="msg-time">{dateTime(message.timestamp)}</span>
                      <div className="msg-actions">
                        <button
                          className="btn btn--sm btn--ghost"
                          onClick={() => onAnalyzeMessage(message.id)}
                        >
                          Analyze
                        </button>
                      </div>
                    </div>

                    {body ? (
                      <p className="msg-text" dir={dir}>
                        {body}
                      </p>
                    ) : (
                      <p className="msg-text faint">
                        {CONTENT_TYPE_NAMES[message.content_type] ?? message.content_type} — no text
                      </p>
                    )}

                    <div className="msg-meta">
                      <Badge variant="quiet">{languageName(message.language)}</Badge>
                      {message.content_type !== "text" && (
                        <Badge variant="quiet">{CONTENT_TYPE_NAMES[message.content_type]}</Badge>
                      )}
                      {message.is_question && <Badge variant="accent">Question</Badge>}
                      {message.is_cold_closure && <Badge>Cold closure</Badge>}
                      {message.is_forwarded && <Badge variant="quiet">Forwarded</Badge>}
                      {message.reply_to_msg_id != null && (
                        <Badge variant="quiet">Reply to #{message.reply_to_msg_id}</Badge>
                      )}
                      <span className="faint" style={{ fontSize: 11 }}>
                        {int(message.word_count)} words · {int(message.char_count)} chars
                      </span>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Card>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="faint" style={{ fontSize: 12 }}>
          {showNormalized ? "Showing normalized text" : "Showing text exactly as exported"}
        </span>
        <div className="row" style={{ gap: 8 }}>
          <button
            className="btn btn--sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Previous
          </button>
          <button
            className="btn btn--sm"
            disabled={rows.length < limit}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
