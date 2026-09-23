import type { ReactNode } from "react";

import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { Icon } from "./Primitives";

export type ViewName = "chats" | "analytics" | "assessment" | "messages" | "decisions";

const NAV: { id: ViewName; label: string; icon: "chats" | "analytics" | "assessment" | "messages" | "decisions" }[] = [
  { id: "chats", label: "Chats", icon: "chats" },
  { id: "analytics", label: "Analytics", icon: "analytics" },
  { id: "assessment", label: "Assessment", icon: "assessment" },
  { id: "messages", label: "Messages", icon: "messages" },
  { id: "decisions", label: "Decisions", icon: "decisions" },
];

function HealthPill() {
  const { data, error } = useAsync(() => api.health(), []);
  const engine = data?.decision_engine ?? {};
  const engineName = typeof engine.engine === "string" ? engine.engine : "engine";
  const engineStatus = typeof engine.status === "string" ? engine.status : "unknown";

  const tone = error ? "var(--critical)" : data ? "var(--good)" : "var(--text-faint)";
  const label = error ? "API unreachable" : data ? "API connected" : "Checking…";

  return (
    <div style={{ padding: "0 8px", display: "grid", gap: 4 }}>
      <span className="row" style={{ gap: 7, fontSize: 12, color: "var(--text-secondary)" }}>
        <span className="dot" style={{ color: tone }} />
        {label}
      </span>
      {data && (
        <span className="faint" style={{ fontSize: 11, paddingInlineStart: 14 }}>
          {engineName} · {engineStatus.replace(/_/g, " ")}
        </span>
      )}
    </div>
  );
}

export function Shell({
  view,
  onView,
  chatCount,
  children,
}: {
  view: ViewName;
  onView: (view: ViewName) => void;
  chatCount?: number;
  children: ReactNode;
}) {
  return (
    <div className="app">
      <nav className="sidebar" aria-label="Sections">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <rect x="0.75" y="0.75" width="26.5" height="26.5" rx="8"
              stroke="rgba(255,255,255,0.13)" />
            <path d="M8 18.5V13M14 18.5V8.5M20 18.5v-3.2" stroke="var(--accent)"
              strokeWidth="2" strokeLinecap="round" />
          </svg>
          <div>
            <div className="brand-name">Telegnize</div>
            <div className="brand-version">v0.3.0</div>
          </div>
        </div>

        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-current={view === item.id ? "page" : undefined}
            onClick={() => onView(item.id)}
          >
            <Icon name={item.icon} />
            {item.label}
            {item.id === "chats" && chatCount != null && (
              <span className="nav-count">{chatCount}</span>
            )}
          </button>
        ))}

        <div className="sidebar-foot">
          <HealthPill />
        </div>
      </nav>

      <main className="main">{children}</main>
    </div>
  );
}
