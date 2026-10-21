import { useEffect, useState, type FormEvent } from "react";
import {
  deleteMemory,
  exportMemories,
  fetchMemories,
  forgetAllMemories,
  updateMemory,
  type MemoryItem,
} from "../api";
import { ArcCoreHologram } from "./ArcCoreHologram";
import { MaterialIcon } from "./MaterialIcon";

type MemoryViewProps = {
  onBack: () => void;
  onLogout: () => void;
};

const KINDS = ["", "fact", "preference", "person", "goal", "episode"];

export function MemoryView({ onBack, onLogout }: MemoryViewProps) {
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(nextKind = kind, nextQuery = query) {
    setLoading(true);
    setError("");
    try {
      setRows(await fetchMemories(nextKind, nextQuery));
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not load memories");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // Initial load only. Search and kind changes go through the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    void load(kind, query);
  }

  async function onSave(id: string) {
    const content = draft.trim();
    if (!content) return;
    setBusy(true);
    setError("");
    try {
      const updated = await updateMemory(id, content);
      setRows((current) => current.map((row) => (row.id === id ? updated : row)));
      setEditing(null);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    setBusy(true);
    setError("");
    try {
      await deleteMemory(id);
      setRows((current) => current.filter((row) => row.id !== id));
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not delete");
    } finally {
      setBusy(false);
    }
  }

  async function onForgetAll() {
    if (!window.confirm("Delete every memory JARVIS has stored? This cannot be undone.")) return;
    setBusy(true);
    setError("");
    try {
      await forgetAllMemories();
      setRows([]);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not forget everything");
    } finally {
      setBusy(false);
    }
  }

  async function onExport() {
    setBusy(true);
    setError("");
    try {
      const payload = await exportMemories();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "jarvis-memories.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not export");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-container-lowest font-body-md text-on-surface">
      <header className="sticky top-0 z-40 h-16 bg-surface-container-lowest/90 backdrop-blur-2xl flex items-center justify-between px-space-lg shadow-[0_1px_8px_rgba(0,0,0,0.4)]">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-space-xs text-primary font-label-sm hover:text-on-primary-container"
        >
          <MaterialIcon name="arrow_back" className="text-lg" />
          Back to chat
        </button>
        <div className="flex items-center gap-space-sm">
          <ArcCoreHologram variant="sm" className="h-7 w-7" />
          <span className="font-label-md text-label-md text-primary tracking-widest uppercase">Memory</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-gutter py-space-lg space-y-space-lg">
        {error ? <p className="text-error">{error}</p> : null}
        <form onSubmit={onSearch} className="flex flex-wrap gap-space-sm">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memories"
            className="flex-1 min-w-48 rounded-lg bg-surface-container-high px-space-md py-space-sm"
          />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded-lg bg-surface-container-high px-space-md py-space-sm"
          >
            {KINDS.map((item) => (
              <option key={item || "all"} value={item}>
                {item || "all kinds"}
              </option>
            ))}
          </select>
          <button type="submit" className="rounded-lg bg-primary-container text-on-primary px-space-md py-space-sm">
            Search
          </button>
        </form>

        <div className="flex gap-space-sm">
          <button type="button" disabled={busy} onClick={() => void onExport()} className="text-primary font-label-sm">
            Export JSON
          </button>
          <button type="button" disabled={busy} onClick={() => void onForgetAll()} className="text-error font-label-sm">
            Forget everything
          </button>
        </div>

        {loading ? <p className="text-on-surface-variant">Loading memories…</p> : null}
        {!loading && rows.length === 0 ? (
          <p className="text-on-surface-variant">Nothing stored yet. Ask JARVIS to remember something.</p>
        ) : null}

        <ul className="space-y-space-md">
          {rows.map((row) => (
            <li key={row.id} className="rounded-xl bg-surface-container-low p-space-lg space-y-space-sm">
              <div className="flex items-center justify-between gap-space-sm">
                <span className="font-label-sm text-label-sm text-primary uppercase">{row.kind}</span>
                <span className="text-label-sm text-outline">{row.source}</span>
              </div>
              {editing === row.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void onSave(row.id);
                  }}
                  className="space-y-space-sm"
                >
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    className="w-full rounded-lg bg-surface-container-high px-space-md py-space-sm"
                    rows={3}
                  />
                  <div className="flex gap-space-sm">
                    <button type="submit" disabled={busy} className="text-primary font-semibold">
                      Save
                    </button>
                    <button type="button" onClick={() => setEditing(null)} className="text-on-surface-variant">
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <p>{row.content}</p>
                  <div className="flex gap-space-md">
                    <button
                      type="button"
                      disabled={busy}
                      className="text-primary font-label-sm"
                      onClick={() => {
                        setEditing(row.id);
                        setDraft(row.content);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      className="text-error font-label-sm"
                      onClick={() => void onDelete(row.id)}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
