import { useEffect, useRef, useState } from "react";
import { Icon } from "./Primitives";
import type { FieldDefinition } from "../lib/fieldDescriptions";

/* ------------------------------------------------------------- InfoPopover */

export function InfoPopover({
  field,
  anchorRect,
  onClose,
}: {
  field: FieldDefinition;
  anchorRect: DOMRect | null;
  onClose: () => void;
}) {
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        onClose();
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  if (!anchorRect) return null;

  // Calculate positioning so the popover remains within the viewport
  const popoverWidth = Math.min(340, window.innerWidth - 24);
  let left = anchorRect.left + anchorRect.width / 2 - popoverWidth / 2;
  if (left < 12) left = 12;
  if (left + popoverWidth > window.innerWidth - 12) {
    left = window.innerWidth - popoverWidth - 12;
  }

  // Position above or below depending on available space
  const spaceBelow = window.innerHeight - anchorRect.bottom;
  const isAbove = spaceBelow < 220 && anchorRect.top > 220;
  const top = isAbove ? anchorRect.top - 8 : anchorRect.bottom + 8;
  const transform = isAbove ? "translateY(-100%)" : "translateY(0)";

  return (
    <div
      ref={popoverRef}
      className="info-popover screen-only"
      style={{
        position: "fixed",
        top: `${top}px`,
        left: `${left}px`,
        width: `${popoverWidth}px`,
        transform,
        zIndex: 1100,
      }}
      role="dialog"
      aria-label={`Definition for ${field.label}`}
    >
      <div className="info-popover-head">
        <div className="row" style={{ gap: 6, flex: 1, minWidth: 0 }}>
          <span className="info-popover-title">{field.label}</span>
          {field.formula && <span className="info-popover-formula">{field.formula}</span>}
        </div>
        <button
          type="button"
          className="info-popover-close"
          onClick={onClose}
          aria-label="Close definition"
        >
          <Icon name="close" size={14} />
        </button>
      </div>

      <div className="info-popover-desc">{field.description}</div>

      {field.interpretation && (
        <div className="info-popover-note">
          <strong style={{ color: "var(--text-primary)" }}>Interpretation: </strong>
          {field.interpretation}
        </div>
      )}

      {field.caveat && (
        <div className="info-popover-caveat">
          <strong style={{ color: "var(--amber-text)" }}>Keep in mind: </strong>
          {field.caveat}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- InfoTrigger */

export function InfoTrigger({
  field,
  className,
}: {
  field?: FieldDefinition;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  if (!field) return null;

  function toggle(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (!open && triggerRef.current) {
      setRect(triggerRef.current.getBoundingClientRect());
    }
    setOpen((prev) => !prev);
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={
          className
            ? `info-trigger ${className} ${open ? "is-active" : ""}`
            : `info-trigger ${open ? "is-active" : ""}`
        }
        onClick={toggle}
        title={`Field info: ${field.label}`}
        aria-label={`Field info: ${field.label}`}
        aria-expanded={open}
      >
        <Icon name="info" size={12} />
      </button>

      {open && (
        <InfoPopover
          field={field}
          anchorRect={rect}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------- InfoSection */

export function InfoSection({
  fields,
  title = "Field definitions & interpretation guide",
  defaultOpen = false,
  forceOpen,
}: {
  fields?: FieldDefinition[];
  title?: string;
  defaultOpen?: boolean;
  forceOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    if (forceOpen !== undefined) {
      setIsOpen(forceOpen);
    }
  }, [forceOpen]);

  if (!fields || fields.length === 0) return null;

  return (
    <div className="info-section">
      <button
        type="button"
        className="info-section-toggle screen-only"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <span className="row" style={{ gap: 8 }}>
          <Icon name="info" size={14} />
          <span>{title}</span>
          <span className="badge badge--quiet" style={{ fontSize: 10, padding: "1px 6px" }}>
            {fields.length} {fields.length === 1 ? "field" : "fields"}
          </span>
        </span>
        <Icon name={isOpen ? "chevronUp" : "chevronDown"} size={14} />
      </button>

      {isOpen && (
        <div className="info-section-body">
          <div className="info-grid">
            {fields.map((f) => (
              <div key={f.key} className="info-card">
                <div className="info-card-head">
                  <span className="info-card-title">{f.label}</span>
                  {f.formula && <span className="info-card-formula">{f.formula}</span>}
                </div>
                <p className="info-card-desc">{f.description}</p>
                {f.interpretation && (
                  <div className="info-card-note">
                    <strong style={{ color: "var(--text-primary)" }}>Interpretation: </strong>
                    {f.interpretation}
                  </div>
                )}
                {f.caveat && (
                  <div className="info-card-caveat">
                    <strong style={{ color: "var(--amber-text)" }}>Keep in mind: </strong>
                    {f.caveat}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
