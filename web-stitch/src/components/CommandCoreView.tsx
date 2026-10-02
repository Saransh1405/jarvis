import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  approveAction,
  clearToken,
  fetchConversations,
  fetchMessages,
  greeting,
  pendingActionLabel,
  resolvePendingAction,
  rejectAction,
  streamChat,
  type ChatMessage,
  type ConversationListItem,
  type PendingAction,
} from "../api";
import { QUICK_PROMPTS } from "../constants";
import { ArcCoreHologram } from "./ArcCoreHologram";
import { MaterialIcon } from "./MaterialIcon";

type CommandCoreViewProps = {
  onLogout: () => void;
};

type UiMessage = ChatMessage & { streaming?: boolean };

export function CommandCoreView({ onLogout }: CommandCoreViewProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [current, setCurrent] = useState<ConversationListItem | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [showEmpty, setShowEmpty] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollDown = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
    }
  }, [onLogout]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    scrollDown();
  }, [messages, pendingAction, scrollDown]);

  function startNewChat() {
    if (busy) return;
    setCurrent(null);
    setMessages([]);
    setShowEmpty(true);
    setPendingAction(null);
    setDraft("");
  }

  async function openConversation(conv: ConversationListItem) {
    if (busy) return;
    setCurrent(conv);
    setShowEmpty(false);
    try {
      const rows = await fetchMessages(conv.id);
      setMessages(rows.length ? rows : []);
      setShowEmpty(rows.length === 0);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") {
        onLogout();
        return;
      }
      setMessages([]);
      setShowEmpty(true);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setDraft("");
    setShowEmpty(false);

    const userMsg: UiMessage = { id: `u-${Date.now()}`, role: "user", content: trimmed };
    const botId = `b-${Date.now()}`;
    const botMsg: UiMessage = { id: botId, role: "assistant", content: "", streaming: true };
    setMessages((m) => [...m, userMsg, botMsg]);
    setBusy(true);
    setPendingAction(null);

    try {
      const result = await streamChat(trimmed, current?.id ?? null, (partial) => {
        setMessages((m) => m.map((row) => (row.id === botId ? { ...row, content: partial } : row)));
      });
      setMessages((m) => m.map((row) => (row.id === botId ? { ...row, streaming: false } : row)));
      if (!current && result.conversationId) {
        setCurrent({ id: result.conversationId, title: trimmed.slice(0, 38), group: "Today" });
      } else if (current && result.conversationId) {
        setCurrent({ ...current, id: result.conversationId });
      }
      const resolved = result.pendingAction?.action_id
        ? result.pendingAction
        : resolvePendingAction(result.pendingAction, result.message);
      if (resolved?.action_id) setPendingAction(resolved);
      await refreshConversations();
    } catch (err) {
      setMessages((m) =>
        m.map((row) =>
          row.id === botId
            ? {
                ...row,
                streaming: false,
                content: err instanceof Error && err.message !== "unauthorized" ? err.message : row.content,
              }
            : row,
        ),
      );
      if (err instanceof Error && err.message === "unauthorized") onLogout();
    } finally {
      setBusy(false);
    }
  }

  function onSend(e: FormEvent) {
    e.preventDefault();
    void sendMessage(draft);
  }

  async function onApprovePending() {
    const actionId = pendingAction?.action_id;
    if (!actionId || busy) return;
    setBusy(true);
    try {
      const result = await approveAction(actionId);
      setPendingAction(null);
      setMessages((m) => {
        const last = [...m].reverse().find((r) => r.role === "assistant");
        if (last) {
          return m.map((row) => (row.id === last.id ? { ...row, content: result.message, streaming: false } : row));
        }
        return [...m, { id: `b-approve-${Date.now()}`, role: "assistant", content: result.message }];
      });
      if (result.conversation_id) {
        setCurrent((c) =>
          c ? { ...c, id: result.conversation_id } : { id: result.conversation_id, title: "Chat", group: "Today" },
        );
      }
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
    } finally {
      setBusy(false);
    }
  }

  async function onRejectPending() {
    const actionId = pendingAction?.action_id;
    if (!actionId || busy) return;
    setBusy(true);
    try {
      const result = await rejectAction(actionId);
      setPendingAction(null);
      setMessages((m) => {
        const last = [...m].reverse().find((r) => r.role === "assistant");
        if (last) {
          return m.map((row) => (row.id === last.id ? { ...row, content: result.message, streaming: false } : row));
        }
        return [...m, { id: `b-reject-${Date.now()}`, role: "assistant", content: result.message }];
      });
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearToken();
    onLogout();
  }

  const grouped = conversations.reduce<{ group: string; items: ConversationListItem[] }[]>((acc, c) => {
    const last = acc[acc.length - 1];
    if (last?.group === c.group) last.items.push(c);
    else acc.push({ group: c.group, items: [c] });
    return acc;
  }, []);

  const showSuggestions = showEmpty && messages.length === 0;

  return (
    <div className="min-h-screen bg-surface-container-lowest font-body-md text-on-surface">
      <aside className="fixed left-0 top-0 h-full w-72 bg-surface-container-low/90 backdrop-blur-2xl z-50 flex flex-col shadow-[0_1px_8px_rgba(0,0,0,0.6)] hidden lg:flex">
        <div className="p-space-lg flex flex-col h-full overflow-hidden">
          <div className="flex items-center gap-space-sm mb-space-lg">
            <ArcCoreHologram variant="sm" className="h-8 w-8" />
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-primary tracking-wider uppercase leading-none">J.A.R.V.I.S.</span>
              <span className="font-label-sm text-label-sm text-on-surface-variant tracking-widest">MARK VII // OS</span>
            </div>
          </div>
          <button
            type="button"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-space-sm py-space-sm px-space-md bg-primary-container text-on-primary text-sm rounded-lg shadow-[0_0_16px_rgba(25,227,255,0.35)] hover:bg-primary-fixed-dim transition-all mb-space-lg"
          >
            <MaterialIcon name="add" className="text-lg" />
            Initialize New Thread
          </button>
          <div className="flex-1 overflow-y-auto space-y-space-lg">
            <div>
              <div className="px-space-sm py-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">COMMAND CORE</div>
              <nav className="space-y-space-xs mt-1">
                <div className="flex items-center justify-between px-space-sm py-space-sm rounded bg-surface-container-high text-primary font-semibold">
                  <div className="flex items-center gap-space-sm">
                    <MaterialIcon name="terminal" className="text-lg" />
                    <span className="font-body-md text-body-md">Chat Stream</span>
                  </div>
                  <span className="h-2 w-2 rounded-full bg-primary-container shadow-[0_0_8px_rgba(25,227,255,0.8)]" />
                </div>
              </nav>
            </div>
            <div>
              <div className="px-space-sm py-space-xs font-label-sm text-label-sm text-outline uppercase">Archive</div>
              {grouped.map(({ group, items }) => (
                <div key={group} className="mt-2 space-y-1">
                  <span className="font-label-sm text-label-sm text-outline px-space-sm">{group}</span>
                  {items.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => void openConversation(c)}
                      className={`block w-full text-left px-space-sm py-1 rounded text-body-sm truncate transition-all ${
                        current?.id === c.id
                          ? "bg-surface-container-high text-primary"
                          : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                      }`}
                    >
                      {c.title}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="p-space-md mt-auto bg-surface-container-lowest/80">
            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-space-xs py-1.5 rounded bg-surface-container-high/60 text-secondary hover:bg-secondary-container transition-all font-label-sm text-label-sm"
            >
              <MaterialIcon name="power_settings_new" className="text-base" />
              TERMINATE SESSION
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-72 flex flex-col min-h-screen">
        <header className="fixed top-0 left-0 lg:left-72 right-0 h-16 bg-surface-container-lowest/90 backdrop-blur-2xl z-40 flex items-center justify-between px-space-lg shadow-[0_1px_8px_rgba(0,0,0,0.4)]">
          <div className="flex items-center gap-space-sm">
            <span className="h-2 w-2 rounded-full bg-primary-container shadow-[0_0_8px_rgba(25,227,255,0.9)]" />
            <span className="font-label-md text-label-md text-primary tracking-widest uppercase hidden sm:inline">SYS // NEURAL STREAM ONLINE</span>
          </div>
          <div className="flex items-center gap-space-sm">
            <button type="button" className="lg:hidden text-primary font-label-sm" onClick={startNewChat}>
              New
            </button>
            <div className="relative flex items-center justify-center p-0.5 rounded-full bg-surface-container-high ring-2 ring-primary-container/40 shadow-[0_0_12px_rgba(25,227,255,0.3)] overflow-hidden">
              <ArcCoreHologram variant="sm" className="h-7 w-7" alt="Session" />
            </div>
          </div>
        </header>

        <main className="pt-16 flex-1 flex flex-col px-gutter pb-space-lg max-w-6xl mx-auto w-full">
          <div ref={scrollRef} className="flex-1 overflow-y-auto py-space-md space-y-space-lg">
            <div className="rounded-xl bg-surface-container-low/80 backdrop-blur-xl p-space-lg shadow-xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-md">
                <div>
                  <span className="font-label-sm text-label-sm text-primary tracking-widest uppercase">STREAM PROTOCOL</span>
                  <h1 className="font-headline-md text-headline-md text-on-surface mt-1">
                    {greeting()}. <span className="text-primary-container">Telemetry nominal.</span>
                  </h1>
                </div>
              </div>
              {showSuggestions ? (
                <div className="mt-space-lg grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
                  {QUICK_PROMPTS.map((p) => (
                    <button
                      key={p.text}
                      type="button"
                      disabled={busy}
                      onClick={() => void sendMessage(p.text)}
                      className="group flex items-center justify-between p-space-sm rounded-lg bg-surface-container/70 hover:bg-surface-container-high transition-all text-left"
                    >
                      <span className="font-body-sm text-body-sm truncate">
                        {p.emoji} {p.text}
                      </span>
                      <MaterialIcon name="arrow_outward" className="text-sm text-outline group-hover:text-primary" />
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex flex-col items-end pl-8">
                  <div className="p-space-md rounded-xl rounded-tr-none bg-surface-container-high/90 text-on-surface shadow-lg max-w-2xl relative">
                    <div className="absolute top-0 right-0 h-full w-1 bg-primary-container/80" />
                    <p className="font-body-md text-body-md whitespace-pre-wrap">{m.content}</p>
                  </div>
                </div>
              ) : (
                <div key={m.id} className="flex items-start gap-space-md pr-4">
                  <div className="shrink-0 rounded-lg bg-surface-container-high shadow-[0_0_16px_rgba(25,227,255,0.35)] p-0.5">
                    <ArcCoreHologram variant="chat" alt="" />
                  </div>
                  <div className="flex flex-col gap-space-sm min-w-0 flex-1">
                    <span className="font-headline-sm text-sm text-primary tracking-wide">JARVIS // MK-VII</span>
                    <div className="p-space-md rounded-xl rounded-tl-none bg-surface-container-low/90 shadow-xl relative">
                      <div className="absolute top-0 left-0 h-1 w-full bg-gradient-to-r from-primary-container via-transparent to-transparent" />
                      <p className="font-body-md text-body-md whitespace-pre-wrap leading-relaxed">
                        {m.content}
                        {m.streaming ? (
                          <span className="inline-block text-primary-container animate-pulse font-mono ml-1 font-bold">▋</span>
                        ) : null}
                      </p>
                    </div>
                  </div>
                </div>
              ),
            )}

            {pendingAction?.action_id ? (
              <div className="rounded-xl bg-surface-container/95 p-space-md backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.8),0_0_24px_rgba(25,227,255,0.12)] relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary-container via-primary-fixed-dim to-secondary-container" />
                <div className="flex items-center gap-space-sm mb-space-sm">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-container opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-primary-container" />
                  </span>
                  <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest font-semibold">
                    ACTION PENDING CONFIRMATION
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-md">
                  <strong className="text-on-surface">{pendingActionLabel(pendingAction)}</strong> — allow JARVIS to continue?
                </p>
                <div className="flex flex-col sm:flex-row gap-space-sm">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onApprovePending()}
                    className="flex items-center justify-center gap-space-xs py-2 px-space-md bg-primary-container text-on-primary text-sm rounded-lg shadow-[0_0_16px_rgba(25,227,255,0.4)] hover:bg-primary-fixed-dim transition-all disabled:opacity-50"
                  >
                    <MaterialIcon name="check" className="text-base font-bold" />
                    Approve &amp; Execute
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onRejectPending()}
                    className="flex items-center justify-center gap-space-xs py-2 px-space-md text-secondary hover:bg-secondary-container/20 text-sm rounded-lg transition-all disabled:opacity-50"
                  >
                    <MaterialIcon name="close" className="text-base" />
                    Reject Action
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <form onSubmit={onSend} className="sticky bottom-0 z-30 pt-space-md bg-surface-container-lowest/90 backdrop-blur-2xl">
            <div className="p-space-xs rounded-xl bg-surface-container-low/95 shadow-[0_8px_32px_rgba(0,0,0,0.9),0_0_20px_rgba(25,227,255,0.12)]">
              <div className="flex items-center gap-space-sm px-space-sm py-space-xs">
                <span className="font-label-md text-label-md text-primary-container font-bold">&gt;_</span>
                <input
                  value={draft}
                  disabled={busy}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask JARVIS, paste documents, or hold space for voice..."
                  className="w-full bg-transparent text-on-surface placeholder:text-outline font-body-md text-body-md focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={busy || !draft.trim()}
                  className="p-2 rounded-lg bg-primary-container text-on-primary hover:bg-primary-fixed-dim transition-all shadow-[0_0_12px_rgba(25,227,255,0.5)] disabled:opacity-40"
                  aria-label="Send"
                >
                  <MaterialIcon name="arrow_upward" className="text-lg font-bold" />
                </button>
              </div>
            </div>
            <p className="font-label-sm text-label-sm text-outline px-space-sm pt-space-xs flex items-center gap-1">
              <MaterialIcon name="lock" className="text-xs text-primary-container" />
              E2EE ENCRYPTED // CONNECTED TO GATEWAY API
            </p>
          </form>
        </main>
      </div>
    </div>
  );
}
