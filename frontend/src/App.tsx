import { useEffect, useState } from "react";

import { Shell, type ViewName } from "./components/Shell";
import { api } from "./lib/api";
import { useAsync } from "./lib/useAsync";
import type { Chat } from "./lib/types";
import { AnalyticsView } from "./views/AnalyticsView";
import { ChatsView } from "./views/ChatsView";
import { DecisionsView } from "./views/DecisionsView";
import { MessagesView } from "./views/MessagesView";

/** The chat picker every scoped view shares, so one selection follows you
 *  from analytics to messages to decisions. */
export function ChatSelect({
  chats,
  value,
  onChange,
  id = "chat-select",
}: {
  chats: Chat[];
  value: number | null;
  onChange: (id: number) => void;
  id?: string;
}) {
  return (
    <select
      id={id}
      className="select"
      value={value ?? ""}
      onChange={(event) => onChange(Number(event.target.value))}
      disabled={chats.length === 0}
    >
      {chats.length === 0 && <option value="">No chats imported</option>}
      {chats.map((chat) => (
        <option key={chat.id} value={chat.id}>
          {chat.name} · {chat.total_messages.toLocaleString("en-US")}
        </option>
      ))}
    </select>
  );
}

export default function App() {
  const [view, setView] = useState<ViewName>("chats");
  const [chatId, setChatId] = useState<number | null>(null);
  const [messageTarget, setMessageTarget] = useState<number | null>(null);

  const chats = useAsync(() => api.listChats(), []);
  const list = chats.data ?? [];

  // Keep the selection valid: land on the first chat, and move off one that
  // was just deleted.
  useEffect(() => {
    if (!chats.data) return;
    const stillThere = chatId != null && chats.data.some((chat) => chat.id === chatId);
    if (!stillThere) setChatId(chats.data[0]?.id ?? null);
  }, [chats.data, chatId]);

  const openChat = (id: number, next: ViewName) => {
    setChatId(id);
    setView(next);
  };

  const analyzeMessage = (id: number) => {
    setMessageTarget(id);
    setView("decisions");
  };

  return (
    <Shell view={view} onView={setView} chatCount={chats.data?.length}>
      {view === "chats" && (
        <ChatsView state={chats} onOpen={openChat} />
      )}
      {view === "analytics" && (
        <AnalyticsView chats={list} chatId={chatId} onChatId={setChatId} />
      )}
      {view === "messages" && (
        <MessagesView
          chats={list}
          chatId={chatId}
          onChatId={setChatId}
          onAnalyzeMessage={analyzeMessage}
        />
      )}
      {view === "decisions" && (
        <DecisionsView
          chats={list}
          chatId={chatId}
          onChatId={setChatId}
          messageTarget={messageTarget}
          onMessageTarget={setMessageTarget}
        />
      )}
    </Shell>
  );
}
