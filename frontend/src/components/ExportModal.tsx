import { useState } from "react";
import type { ReactNode } from "react";

import { int } from "../lib/format";
import { Icon } from "./Primitives";

/** The color-theme prompt shared by every "Export to PDF" flow. Each view
 *  supplies its own title and subtitle; the print itself is triggered by
 *  `triggerPdfExport` after the modal closes. */
export function ExportModal({
  title,
  subtitle,
  isOpen,
  onClose,
  onExport,
}: {
  title: string;
  subtitle: string;
  isOpen: boolean;
  onClose: () => void;
  onExport: (options: { theme: "light" | "dark" }) => void;
}) {
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
              {title}
            </h2>
            <p className="faint" style={{ fontSize: 12, marginTop: 2 }}>
              {subtitle}
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
              onExport({ theme });
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

/** Sets the print theme and tab title, opens the browser's print dialog,
 *  then restores both once printing is done (or after a 2s fallback, since
 *  `afterprint` does not fire in every browser when the dialog is cancelled). */
export function triggerPdfExport(options: { theme: "light" | "dark"; documentTitle: string }) {
  const previousTitle = document.title;
  document.title = options.documentTitle;
  document.body.setAttribute("data-print-theme", options.theme);

  const cleanup = () => {
    document.title = previousTitle;
    document.body.removeAttribute("data-print-theme");
    window.removeEventListener("afterprint", cleanup);
  };

  window.addEventListener("afterprint", cleanup);

  setTimeout(() => {
    window.print();
    setTimeout(cleanup, 2000);
  }, 120);
}

/** The masthead that only appears in the printed/exported document — screen
 *  readers of the live page use the normal view header instead. */
export function PrintHeader({
  tag,
  title,
  subLine,
}: {
  tag: string;
  title: string;
  subLine: ReactNode;
}) {
  return (
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
          <span className="print-brand-tag">{tag}</span>
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
        <h1 className="print-chat-title">{title}</h1>
        <div className="print-chat-sub">{subLine}</div>
      </div>
    </div>
  );
}

/** `{count} messages` etc., matching the modal's subtitle line elsewhere. */
export function countLabel(count: number, noun: string): string {
  return `${int(count)} ${noun}${count === 1 ? "" : "s"}`;
}
