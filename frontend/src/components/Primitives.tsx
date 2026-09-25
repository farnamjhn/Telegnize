import type { ReactNode } from "react";

/* ------------------------------------------------------------------ icons */

type IconName =
  | "chats"
  | "analytics"
  | "assessment"
  | "messages"
  | "decisions"
  | "upload"
  | "trash"
  | "pdf"
  | "info"
  | "chevronDown"
  | "chevronUp"
  | "close";

const PATHS: Record<IconName, ReactNode> = {
  chats: (
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h9A1.5 1.5 0 0 1 16 5.5v5A1.5 1.5 0 0 1 14.5 12H8l-4 3z" />
  ),
  analytics: (
    <>
      <path d="M4 16V9M9 16V4M14 16v-5" />
      <path d="M2.5 19h15" />
    </>
  ),
  assessment: (
    <>
      <circle cx="10" cy="10" r="6.6" />
      <path d="M10 6.4v3.8l2.6 1.6" />
    </>
  ),
  messages: (
    <>
      <path d="M3 5.5h14M3 10h14M3 14.5h9" />
    </>
  ),
  decisions: (
    <>
      <path d="M10 3.2 17 7v6l-7 3.8L3 13V7z" />
      <path d="M10 9.4 17 7M10 9.4 3 7M10 9.4v7.4" />
    </>
  ),
  upload: (
    <>
      <path d="M10 13V3.5M6.5 7 10 3.5 13.5 7" />
      <path d="M3.5 13v2.5A1.5 1.5 0 0 0 5 17h10a1.5 1.5 0 0 0 1.5-1.5V13" />
    </>
  ),
  trash: (
    <>
      <path d="M3.5 5.5h13M8 5.5V4h4v1.5M5 5.5 5.8 16h8.4L15 5.5" />
    </>
  ),
  pdf: (
    <>
      <path d="M4.5 3.5A1.5 1.5 0 0 1 6 2h5.5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5z" />
      <path d="M11.5 2v4H15.5" />
      <path d="M7 11h6M7 14h4" />
    </>
  ),
  info: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 9v4.5M10 6.5h.01" />
    </>
  ),
  chevronDown: <path d="m6 8 4 4 4-4" />,
  chevronUp: <path d="m6 12 4-4 4 4" />,
  close: <path d="M6 6l8 8M14 6l-8 8" />,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

/* ------------------------------------------------------------------ cards */

export function Card({
  title,
  subtitle,
  action,
  flush,
  fill,
  children,
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  flush?: boolean;
  fill?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={fill ? "card card--fill" : "card"}>
      {(title || action) && (
        <header className="card-head">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={flush ? "card-body card-body--flush" : "card-body"}>
        {children}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ stats */

export function Hero({
  label,
  value,
  note,
}: {
  label: ReactNode;
  value: string;
  note?: string;
}) {
  return (
    <div className="hero">
      <span className="hero-label">{label}</span>
      {/* Proportional figures on purpose — tabular-nums looks loose this big. */}
      <span className="hero-value">{value}</span>
      {note && <span className="hero-note">{note}</span>}
    </div>
  );
}

export function Stat({
  label,
  value,
  note,
}: {
  label: ReactNode;
  value: string;
  note?: string;
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

/* --------------------------------------------------------------- feedback */

export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {body && <p className="empty-body">{body}</p>}
      {action}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="row" style={{ gap: 9 }}>
      <span className="spinner" role="status" aria-label={label ?? "Loading"} />
      {label && <span className="muted">{label}</span>}
    </span>
  );
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "error" | "good";
  children: ReactNode;
}) {
  const cls = tone === "error" ? "notice notice--error" : tone === "good" ? "notice notice--good" : "notice";
  return (
    <p className={cls} role={tone === "error" ? "alert" : undefined}>
      {children}
    </p>
  );
}

export function Badge({
  children,
  variant = "default",
  color,
}: {
  children: ReactNode;
  variant?: "default" | "accent" | "quiet";
  color?: string;
}) {
  const cls =
    variant === "accent" ? "badge badge--accent" : variant === "quiet" ? "badge badge--quiet" : "badge";
  return (
    <span className={cls}>
      {color && <span className="swatch" style={{ background: color }} />}
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- toggles */

export function Toggle<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

const CHART_TABLE = [
  { value: "chart", label: "Chart" },
  { value: "table", label: "Table" },
] as const;

export function ViewToggle({
  mode,
  onChange,
}: {
  mode: "chart" | "table";
  onChange: (mode: "chart" | "table") => void;
}) {
  return <Toggle label="Display as" value={mode} onChange={onChange} options={CHART_TABLE} />;
}

export function Field({
  label,
  htmlFor,
  tight,
  children,
}: {
  label: string;
  htmlFor?: string;
  tight?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={tight ? "field field--tight" : "field"}>
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}
