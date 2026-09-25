/** Typed access to the Telegnize API.
 *
 * Paths stay relative so Vite's dev proxy handles them; set `VITE_API_BASE`
 * to point a build at an API on another origin (the server's
 * `TELEGNIZE_CORS_ORIGINS` has to allow it).
 */

import type {
  AssessmentProgress,
  AssessmentRun,
  Chat,
  ChatAnalytics,
  Decision,
  Health,
  ImportSummary,
  Message,
  RederiveSummary,
  RelationalAssessment,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** An API call that came back with a non-2xx status. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/api${path}`, {
      headers: init?.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Could not reach the Telegnize API. Is it running?");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** FastAPI puts the message in `detail`, which is a string or a list of them. */
async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg ?? JSON.stringify(d)).join("; ");
    }
  } catch {
    /* fall through to the status line */
  }
  return `${response.status} ${response.statusText}`;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/health"),

  listChats: () => request<Chat[]>("/chats"),
  getChat: (id: number) => request<Chat>(`/chats/${id}`),
  deleteChat: (id: number) => request<void>(`/chats/${id}`, { method: "DELETE" }),

  uploadChat: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportSummary>("/chats/upload", { method: "POST", body: form });
  },

  importLocal: (filePath: string, overrideName?: string) =>
    request<ImportSummary>(
      "/chats/import-local",
      json({ file_path: filePath, override_name: overrideName || null }),
    ),

  analytics: (chatId: number) => request<ChatAnalytics>(`/analytics/${chatId}`),

  /** Recomputes the derived columns from text already stored, for a chat
   *  imported before a metric existed. Rewrites every row, so it is slow on a
   *  large chat and worth showing a spinner for. */
  rederive: (chatId: number) =>
    request<RederiveSummary>(`/chats/${chatId}/rederive`, { method: "POST" }),

  assessment: (chatId: number) => request<RelationalAssessment>(`/assessments/${chatId}`),

  /** Assesses one page. Slow by nature — the caller decides the page size and
   *  drives the loop, because this runs a model over every message. */
  assessPage: (chatId: number, offset: number, limit: number) =>
    request<AssessmentProgress>(
      `/assessments/${chatId}?offset=${offset}&limit=${limit}`,
      { method: "POST" },
    ),

  /** Starts a background run: `pages` of `limit` messages, or to the end
   *  when `pages` is null. Returns at once; poll `assessmentRun`. */
  startAssessmentRun: (chatId: number, offset: number, limit: number, pages: number | null) =>
    request<AssessmentRun>(
      `/assessments/${chatId}/run?offset=${offset}&limit=${limit}` +
        (pages == null ? "" : `&pages=${pages}`),
      { method: "POST" },
    ),
  assessmentRun: (chatId: number) => request<AssessmentRun>(`/assessments/${chatId}/run`),
  stopAssessmentRun: (chatId: number) =>
    request<AssessmentRun>(`/assessments/${chatId}/run`, { method: "DELETE" }),

  listMessages: (params: {
    chatId?: number;
    senderId?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.chatId != null) query.set("chat_id", String(params.chatId));
    if (params.senderId) query.set("sender_id", params.senderId);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    return request<Message[]>(`/messages?${query}`);
  },

  getMessage: (id: number) => request<Message>(`/messages/${id}`),

  evaluateMessage: (id: number) =>
    request<Decision[]>(`/decisions/messages/${id}`, json({})),
  cachedMessageDecisions: (id: number) =>
    request<Decision[]>(`/decisions/messages/${id}`),

  /** The most recent `limit` messages, or with `wholeChat` windows of that
   *  size sampled across the whole chat and combined. */
  evaluateChat: (id: number, limit: number, wholeChat: boolean) =>
    request<Decision[]>(`/decisions/chats/${id}`, json({ limit, whole_chat: wholeChat })),
  cachedChatDecisions: (id: number) => request<Decision[]>(`/decisions/chats/${id}`),
};
