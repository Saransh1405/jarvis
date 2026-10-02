export const TOKEN_KEY = "jarvis_token";

export type AuthMode = "signup" | "login";

export type ConversationListItem = {
  id: string;
  title: string;
  group: string;
};

export type ChatMessage = {
  id: string;
  role: string;
  content: string;
};

export type StreamResult = {
  conversationId: string | null;
  message: string;
  pendingAction: PendingAction | null;
};

export type PendingAction = {
  action_id: string | null;
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
};

export type ApproveChatResult = {
  message: string;
  conversation_id: string;
  tools_used?: string[] | null;
};

export type BriefSections = {
  reminders: boolean;
  calendar: boolean;
  email: boolean;
  weather: boolean;
};

export type UserSettings = {
  user_id: string;
  timezone: string;
  locale: string;
  preferred_channel: "web" | "telegram";
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  brief_enabled: boolean;
  brief_time_local: string;
  brief_sections: BriefSections;
  feature_flags: Record<string, unknown>;
};

export type UserSettingsPatch = {
  timezone?: string;
  locale?: string;
  preferred_channel?: "web" | "telegram";
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  brief_enabled?: boolean;
  brief_time_local?: string;
  brief_sections?: BriefSections;
};

type ApiErrorBody = {
  error?: { message?: string } | string;
  detail?: string;
};

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const t = getToken();
  const h = { ...extra };
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

async function parseJSON(res: Response): Promise<unknown | null> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function apiErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const d = data as ApiErrorBody;
  if (d.error && typeof d.error === "object" && d.error.message) return d.error.message;
  if (typeof d.detail === "string") return d.detail;
  if (typeof d.error === "string") return d.error;
  return fallback;
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export async function authRequest(
  mode: AuthMode,
  email: string,
  password: string,
): Promise<{ access_token: string }> {
  const path = mode === "signup" ? "/api/v1/auth/signup" : "/api/v1/auth/login";
  const body: Record<string, string> = { email, password };
  if (mode === "signup") {
    body.timezone = browserTimezone();
  }
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await parseJSON(res);
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, "Something went wrong. Try again."));
  }
  const tokenBody = data as { access_token?: string };
  if (!tokenBody.access_token) throw new Error("Invalid auth response");
  return { access_token: tokenBody.access_token };
}

export async function fetchSettings(): Promise<UserSettings> {
  const res = await fetch("/api/v1/me/settings", { headers: authHeaders() });
  const data = await parseJSON(res);
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, "Could not load settings."));
  }
  return data as UserSettings;
}

export async function updateSettings(patch: UserSettingsPatch): Promise<UserSettings> {
  const res = await fetch("/api/v1/me/settings", {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(patch),
  });
  const data = await parseJSON(res);
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, "Could not save settings."));
  }
  return data as UserSettings;
}

export function dayGroup(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startYesterday = new Date(startToday);
  startYesterday.setDate(startYesterday.getDate() - 1);
  if (d >= startToday) return "Today";
  if (d >= startYesterday) return "Yesterday";
  return "Earlier";
}

type ConversationApi = {
  id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
};

export async function fetchConversations(): Promise<ConversationListItem[]> {
  const res = await fetch("/api/v1/conversations", { headers: authHeaders() });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) return [];
  const items = (await res.json()) as ConversationApi[];
  return (items ?? []).map((c) => ({
    id: c.id,
    title: c.title || "New chat",
    group: dayGroup(c.updated_at || c.created_at),
  }));
}

type MessageApi = {
  id: string;
  role: string;
  content: string;
};

export async function fetchMessages(conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
    { headers: authHeaders() },
  );
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) return [];
  const rows = (await res.json()) as MessageApi[];
  return (rows ?? [])
    .filter((r) => r.role !== "tool")
    .map((r) => ({ id: r.id, role: r.role, content: r.content }));
}

type StreamEvent = {
  type: string;
  content?: string;
  conversation_id?: string;
  error?: string;
  pending_action?: PendingAction;
};

function parsePendingAction(raw: unknown): PendingAction | null {
  if (!raw || typeof raw !== "object") return null;
  const p = raw as PendingAction;
  if (!p.tool_name) return null;
  return p;
}

/** Backend embeds action id in the approval message if SSE payload omits it. */
export function extractActionIdFromMessage(message: string): string | null {
  const backtick = message.match(/Approve action `([^`]+)`/);
  if (backtick?.[1]) return backtick[1];
  const paren = message.match(/\(action `([^`]+)`\)/);
  if (paren?.[1]) return paren[1];
  const plain = message.match(/Approve action ([0-9a-f-]{36})/i);
  return plain?.[1] ?? null;
}

export function resolvePendingAction(
  pending: PendingAction | null,
  assistantMessage: string,
): PendingAction | null {
  if (!pending?.tool_name) return null;
  if (pending.action_id) return pending;
  const actionId = extractActionIdFromMessage(assistantMessage);
  if (!actionId) return null;
  return { ...pending, action_id: actionId };
}

export async function approveAction(actionId: string): Promise<ApproveChatResult> {
  const res = await fetch(`/api/v1/actions/${encodeURIComponent(actionId)}/approve`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: "{}",
  });
  const data = await parseJSON(res);
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, "Could not approve that action."));
  }
  const body = data as ApproveChatResult & { message?: string; conversation_id?: string };
  if (!body.message || !body.conversation_id) {
    throw new Error("Invalid approve response");
  }
  return body;
}

export async function rejectAction(actionId: string): Promise<{ message: string }> {
  const res = await fetch(`/api/v1/actions/${encodeURIComponent(actionId)}/reject`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: "{}",
  });
  const data = await parseJSON(res);
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    throw new Error(apiErrorMessage(data, "Could not reject that action."));
  }
  const body = data as { message?: string };
  return { message: body.message ?? "Action cancelled." };
}

export function pendingActionLabel(action: PendingAction): string {
  if (action.tool_name === "save_note") return "Save a note";
  if (action.tool_name === "set_reminder") return "Set a reminder";
  return action.tool_name.replace(/_/g, " ");
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  onUpdate: (text: string) => void,
): Promise<StreamResult> {
  const res = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    const data = await parseJSON(res);
    throw new Error(apiErrorMessage(data, "Chat request failed"));
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let full = "";
  let convId = conversationId;
  let pendingAction: PendingAction | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";
    for (const block of blocks) {
      const line = block.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      let ev: StreamEvent;
      try {
        ev = JSON.parse(line.slice(6)) as StreamEvent;
      } catch {
        continue;
      }
      if (ev.type === "token" && ev.content) {
        full += ev.content;
        onUpdate(full);
      } else if (ev.type === "status") {
        onUpdate("");
      } else if (ev.type === "done") {
        if (ev.conversation_id) convId = ev.conversation_id;
        const pending = parsePendingAction(ev.pending_action);
        if (pending) pendingAction = pending;
      } else if (ev.type === "confirm_required") {
        if (ev.conversation_id) convId = ev.conversation_id;
        const pending = parsePendingAction(ev.pending_action);
        if (pending) pendingAction = pending;
      } else if (ev.type === "error") {
        throw new Error(ev.error ?? "Chat error");
      }
    }
  }
  return { conversationId: convId, message: full, pendingAction };
}

export const STARTER_CARDS = [
  {
    icon: '<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M8 2v4M16 2v4M3 10h18"/>',
    title: "Plan my day",
    sub: "Turn tasks into a schedule",
    fill: "Plan my day: ",
  },
  {
    icon: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
    title: "Draft a message",
    sub: "Written in your tone",
    fill: "Draft a message to ",
  },
  {
    icon: '<path d="M4 17l6-5-6-5M12 19h8"/>',
    title: "Explain an error",
    sub: "Paste a stack trace",
    fill: "Explain this error: ",
  },
  {
    icon: '<path d="M4 6h16M4 12h16M4 18h10"/>',
    title: "Summarize text",
    sub: "Get the key points",
    fill: "Summarize this: ",
  },
] as const;

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
