import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  approveAction,
  clearToken,
  fetchConversations,
  fetchMessages,
  greeting,
  pendingActionLabel,
  resolvePendingAction,
  rejectAction,
  STARTER_CARDS,
  streamChat,
  type ChatMessage,
  type ConversationListItem,
  type PendingAction,
} from "../api";
import { Icon } from "./Icon";
import { MessageRow } from "./MessageRow";

type ChatViewProps = {
  onLogout: () => void;
};

type UiMessage = ChatMessage & { streaming?: boolean };

export function ChatView({ onLogout }: ChatViewProps) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [current, setCurrent] = useState<ConversationListItem | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [showEmpty, setShowEmpty] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollDown = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") {
        onLogout();
      }
    }
  }, [onLogout]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    scrollDown();
  }, [messages, showEmpty, scrollDown]);

  function closeSide() {
    setSideOpen(false);
  }

  async function openConversation(conv: ConversationListItem) {
    if (busy) return;
    setCurrent(conv);
    setShowEmpty(false);
    try {
      const rows = await fetchMessages(conv.id);
      if (!rows.length) {
        setMessages([]);
        setShowEmpty(true);
      } else {
        setMessages(rows);
        setShowEmpty(false);
      }
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") {
        onLogout();
        return;
      }
      setMessages([]);
      setShowEmpty(true);
    }
    closeSide();
  }

  function startNewChat() {
    if (busy) return;
    setCurrent(null);
    setMessages([]);
    setShowEmpty(true);
    setPendingAction(null);
    closeSide();
    textareaRef.current?.focus();
  }

  function onStarterFill(text: string) {
    setDraft(text);
    textareaRef.current?.focus();
  }

  function resizeTextarea() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 144)}px`;
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setShowEmpty(false);

    const userMsg: UiMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };
    const botId = `b-${Date.now()}`;
    const botMsg: UiMessage = {
      id: botId,
      role: "assistant",
      content: "",
      streaming: true,
    };
    setMessages((m) => [...m, userMsg, botMsg]);
    setBusy(true);
    setPendingAction(null);

    try {
      const result = await streamChat(text, current?.id ?? null, (partial) => {
        setMessages((m) =>
          m.map((row) => (row.id === botId ? { ...row, content: partial } : row)),
        );
      });
      setMessages((m) =>
        m.map((row) => (row.id === botId ? { ...row, streaming: false } : row)),
      );
      if (!current) {
        setCurrent({
          id: result.conversationId ?? "",
          title: text.slice(0, 38),
          group: "Today",
        });
      } else if (result.conversationId) {
        setCurrent({ ...current, id: result.conversationId });
      }
      if (result.pendingAction?.action_id) {
        setPendingAction(result.pendingAction);
      } else {
        const resolved = resolvePendingAction(result.pendingAction, result.message);
        if (resolved?.action_id) setPendingAction(resolved);
      }
      await refreshConversations();
    } catch (err) {
      setMessages((m) =>
        m.map((row) =>
          row.id === botId
            ? {
                ...row,
                streaming: false,
                content:
                  err instanceof Error && err.message !== "unauthorized"
                    ? err.message
                    : row.content,
              }
            : row,
        ),
      );
      if (err instanceof Error && err.message === "unauthorized") onLogout();
    } finally {
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  async function onApprovePending() {
    const actionId = pendingAction?.action_id;
    if (!actionId || busy) return;
    setBusy(true);
    try {
      const result = await approveAction(actionId);
      setPendingAction(null);
      setMessages((m) => {
        const lastAssistant = [...m].reverse().find((row) => row.role === "assistant");
        if (lastAssistant) {
          return m.map((row) =>
            row.id === lastAssistant.id
              ? { ...row, content: result.message, streaming: false }
              : row,
          );
        }
        return [
          ...m,
          {
            id: `b-approve-${Date.now()}`,
            role: "assistant",
            content: result.message,
          },
        ];
      });
      if (result.conversation_id) {
        setCurrent((c) =>
          c ? { ...c, id: result.conversation_id } : { id: result.conversation_id, title: "Chat", group: "Today" },
        );
      }
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") {
        onLogout();
      } else {
        setMessages((m) => [
          ...m,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: err instanceof Error ? err.message : "Approve failed.",
          },
        ]);
      }
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
        const lastAssistant = [...m].reverse().find((row) => row.role === "assistant");
        if (lastAssistant) {
          return m.map((row) =>
            row.id === lastAssistant.id ? { ...row, content: result.message, streaming: false } : row,
          );
        }
        return [
          ...m,
          { id: `b-reject-${Date.now()}`, role: "assistant", content: result.message },
        ];
      });
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") {
        onLogout();
      }
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearToken();
    onLogout();
  }

  return (
    <main id="chat">
      <aside id="side" className={sideOpen ? "open" : undefined} aria-label="Chat history">
        <div className="side-top">
          <span className="mark">JARVIS</span>
        </div>
        <button className="btn" type="button" onClick={startNewChat}>
          <Icon paths='<path d="M12 5v14M5 12h14"/>' />
          New chat
        </button>
        <nav id="hist" aria-label="Previous chats">
          {(() => {
            let last = "";
            return conversations.flatMap((c) => {
              const nodes: ReactNode[] = [];
              if (c.group !== last) {
                last = c.group;
                nodes.push(
                  <div key={`grp-${c.group}-${c.id}`} className="grp">
                    {c.group}
                  </div>,
                );
              }
              nodes.push(
                <button
                  key={c.id}
                  type="button"
                  className="item"
                  title={c.title}
                  aria-current={current?.id === c.id ? true : undefined}
                  onClick={() => void openConversation(c)}
                >
                  {c.title}
                </button>,
              );
              return nodes;
            });
          })()}
        </nav>
      </aside>
      <div
        className={sideOpen ? "scrim on" : "scrim"}
        onClick={closeSide}
        onKeyDown={undefined}
        role="presentation"
      />
      <div className="main">
        <header>
          <div className="hin">
            <button
              className="pill menu"
              type="button"
              aria-label="Open chats"
              onClick={() => setSideOpen(true)}
            >
              <Icon paths='<path d="M4 7h16M4 12h16M4 17h10"/>' />
            </button>
            <span className="mark">JARVIS</span>
            <button className="pill" type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>
        <div id="scroll" ref={scrollRef}>
          <div id="log" role="log" aria-live="polite" aria-label="Conversation">
            {showEmpty && messages.length === 0 && (
              <div className="empty">
                <h2>
                  {greeting()}.<br />
                  What can I help with?
                </h2>
                <div className="cards">
                  {STARTER_CARDS.map((card) => (
                    <button
                      key={card.title}
                      type="button"
                      className="card"
                      onClick={() => onStarterFill(card.fill)}
                    >
                      <Icon paths={card.icon} />
                      <b>{card.title}</b>
                      <span>{card.sub}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <MessageRow key={m.id} role={m.role} content={m.content} streaming={m.streaming} />
            ))}
          </div>
        </div>
        {pendingAction?.action_id && (
          <div className="confirm-bar" role="region" aria-label="Action approval">
            <p>
              <strong>{pendingActionLabel(pendingAction)}</strong>
              <span className="confirm-detail"> — allow JARVIS to continue?</span>
            </p>
            <div className="confirm-actions">
              <button
                type="button"
                className="confirm-btn reject"
                disabled={busy}
                onClick={() => void onRejectPending()}
              >
                Reject
              </button>
              <button
                type="button"
                className="confirm-btn approve"
                disabled={busy}
                onClick={() => void onApprovePending()}
              >
                Approve
              </button>
            </div>
          </div>
        )}
        <form className="composer" onSubmit={(e) => void onSend(e)}>
          <div className="box">
            <label htmlFor="msg" className="sr-only">
              Message
            </label>
            <textarea
              id="msg"
              ref={textareaRef}
              rows={1}
              placeholder="Ask JARVIS anything…"
              autoComplete="off"
              value={draft}
              disabled={busy}
              onChange={(e) => {
                setDraft(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button className="send" type="submit" aria-label="Send message" disabled={busy}>
              <Icon paths='<path d="M12 19V5M5 12l7-7 7 7"/>' />
            </button>
          </div>
          <p className="hint">JARVIS can make mistakes. Check important info.</p>
        </form>
      </div>
    </main>
  );
}
