/** Presentation helpers. Nothing here computes analysis — it only renders it. */

import type { Message } from "./types";

const NBSP = " ";

/** Thousands-separated integer, for table columns and axis ticks. */
export const int = (value: number): string => value.toLocaleString("en-US");

/** Auto-compacted figure for stat tiles and hero numbers: 1,284 / 12.9K / 4.2M. */
export function compact(value: number): string {
  if (Math.abs(value) < 10_000) return int(value);
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export const pct = (value: number, digits = 1): string =>
  `${value.toFixed(digits)}%`;

/** Human response latency. `null` means the participant never answered anyone. */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds < 1) return `<1${NBSP}s`;
  if (seconds < 60) return `${Math.round(seconds)}${NBSP}s`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return rest ? `${minutes}${NBSP}m ${rest}${NBSP}s` : `${minutes}${NBSP}m`;
  }
  if (seconds < 86_400) return `${(seconds / 3600).toFixed(1)}${NBSP}h`;
  return `${(seconds / 86_400).toFixed(1)}${NBSP}d`;
}

/** A nullable percentage, for the figures the API leaves null when there is
 *  nothing to divide by. */
export const pctOrDash = (value: number | null | undefined, digits = 1): string =>
  value == null ? "—" : pct(value, digits);

/** A session length, which the API reports in minutes. */
export const minutes = (value: number): string => duration(value * 60);

export function days(value: number): string {
  if (value < 1) return duration(value * 86_400);
  return `${value.toFixed(1)} days`;
}

/** A rate per thousand words. These run small, so two decimals earn their
 *  place; an exact zero stays "0" rather than "0.00". */
export const rate = (value: number): string =>
  value === 0 ? "0" : value.toFixed(2);

export const ratio = (value: number | null): string =>
  value == null ? "—" : `${value.toFixed(2)}×`;

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const DATE_ONLY = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export const dateTime = (value: string | null | undefined): string => {
  const date = parse(value);
  return date ? DATE_TIME.format(date) : "—";
};

export const dateOnly = (value: string | null | undefined): string => {
  const date = parse(value);
  return date ? DATE_ONLY.format(date) : "—";
};

/** Two-digit hour label for the hour-of-day axis. */
export const hourLabel = (hour: number): string => String(hour).padStart(2, "0");

/** "relationship_dynamic" → "Relationship dynamic". */
export const humanize = (key: string): string => {
  const words = key.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

const LANGUAGE_NAMES: Record<string, string> = {
  fa: "Persian",
  en: "English",
  mixed: "Mixed",
  other: "Other",
  unknown: "Unknown",
};

export const languageName = (tag: string): string =>
  LANGUAGE_NAMES[tag] ?? humanize(tag);

const RTL_SCRIPT = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/;

/** Text direction for a message: the tag first, the script as the fallback,
 *  since `mixed` and `unknown` both routinely carry Persian. */
export function directionOf(message: Pick<Message, "language" | "text">): "rtl" | "ltr" {
  if (message.language === "fa") return "rtl";
  if (message.language === "en") return "ltr";
  return RTL_SCRIPT.test(message.text) ? "rtl" : "ltr";
}

/** Up to two initials for an avatar, working for Persian names too. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export const CONTENT_TYPE_NAMES: Record<string, string> = {
  text: "Text",
  photo: "Photo",
  voice_message: "Voice",
  sticker: "Sticker",
  document: "Document",
};

/** Renders whatever a decision engine put in `result_value`. */
export function decisionValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? int(value) : value.toFixed(2);
  if (typeof value === "string") return humanize(value);
  return JSON.stringify(value);
}
