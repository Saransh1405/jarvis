import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  browserTimezone,
  disconnectTelegram,
  fetchSettings,
  fetchTelegramStatus,
  startTelegramLink,
  updateSettings,
  type BriefSections,
  type TelegramStatus,
  type UserSettings,
} from "../api";
import { ArcCoreHologram } from "./ArcCoreHologram";
import { MaterialIcon } from "./MaterialIcon";

type SettingsViewProps = {
  onBack: () => void;
  onLogout: () => void;
};

const SECTION_LABELS: { key: keyof BriefSections; label: string; hint?: string }[] = [
  { key: "reminders", label: "Reminders" },
  { key: "calendar", label: "Calendar", hint: "Available after connecting Google" },
  { key: "email", label: "Email", hint: "Available after connecting Google" },
  { key: "weather", label: "Weather" },
];

function supportedTimezones(): string[] {
  try {
    return [...Intl.supportedValuesOf("timeZone")].sort();
  } catch {
    return ["UTC", "Asia/Kolkata", "America/New_York", "Europe/London"];
  }
}

export function SettingsView({ onBack, onLogout }: SettingsViewProps) {
  const timezones = useMemo(() => supportedTimezones(), []);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [tzFilter, setTzFilter] = useState("");

  const [timezone, setTimezone] = useState("UTC");
  const [briefEnabled, setBriefEnabled] = useState(true);
  const [briefTime, setBriefTime] = useState("08:00");
  const [sections, setSections] = useState<BriefSections>({
    reminders: true,
    calendar: true,
    email: true,
    weather: false,
  });
  const [quietEnabled, setQuietEnabled] = useState(false);
  const [quietStart, setQuietStart] = useState("22:00");
  const [quietEnd, setQuietEnd] = useState("07:00");
  const [preferredChannel, setPreferredChannel] = useState<"web" | "telegram">("web");
  const [featureFlags, setFeatureFlags] = useState<Record<string, unknown>>({});
  const [learnFromChats, setLearnFromChats] = useState(true);
  const [telegram, setTelegram] = useState<TelegramStatus>({
    linked: false,
    status: null,
    username: null,
  });
  const [telegramBusy, setTelegramBusy] = useState(false);
  const [telegramNote, setTelegramNote] = useState("");
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, tg] = await Promise.all([fetchSettings(), fetchTelegramStatus().catch(() => null)]);
        if (cancelled) return;
        applySettings(s);
        if (tg) setTelegram(tg);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof Error && err.message === "unauthorized") onLogout();
          else setError(err instanceof Error ? err.message : "Failed to load settings");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onLogout]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopTelegramPoll() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function connectTelegram() {
    setTelegramBusy(true);
    setError("");
    setTelegramNote("");
    try {
      const link = await startTelegramLink();
      window.open(link.url, "_blank", "noopener,noreferrer");
      setTelegramNote("Press Start in Telegram. This page updates when the chat is linked.");
      stopTelegramPoll();
      const started = Date.now();
      pollRef.current = window.setInterval(() => {
        void (async () => {
          try {
            const status = await fetchTelegramStatus();
            setTelegram(status);
            if (status.linked) {
              stopTelegramPoll();
              setPreferredChannel("telegram");
              setTelegramNote("Telegram connected.");
              setTelegramBusy(false);
            } else if (Date.now() - started > 120_000) {
              stopTelegramPoll();
              setTelegramNote("Still waiting. Generate a new link if the previous one expired.");
              setTelegramBusy(false);
            }
          } catch {
            // Keep polling until the link window ends.
          }
        })();
      }, 2000);
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not connect Telegram");
      setTelegramBusy(false);
    }
  }

  async function onDisconnectTelegram() {
    setTelegramBusy(true);
    setError("");
    try {
      await disconnectTelegram();
      stopTelegramPoll();
      setTelegram({ linked: false, status: "unlinked", username: null });
      setPreferredChannel("web");
      setTelegramNote("Telegram disconnected.");
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Could not disconnect Telegram");
    } finally {
      setTelegramBusy(false);
    }
  }

  function applySettings(s: UserSettings) {
    setTimezone(s.timezone);
    setBriefEnabled(s.brief_enabled);
    setBriefTime(s.brief_time_local);
    setSections({
      reminders: s.brief_sections?.reminders ?? true,
      calendar: s.brief_sections?.calendar ?? true,
      email: s.brief_sections?.email ?? true,
      weather: s.brief_sections?.weather ?? false,
    });
    const hasQuiet = Boolean(s.quiet_hours_start && s.quiet_hours_end);
    setQuietEnabled(hasQuiet);
    setQuietStart(s.quiet_hours_start ?? "22:00");
    setQuietEnd(s.quiet_hours_end ?? "07:00");
    setPreferredChannel(s.preferred_channel === "telegram" ? "telegram" : "web");
    const flags = s.feature_flags ?? {};
    setFeatureFlags(flags);
    setLearnFromChats(flags.learn_from_conversations !== false);
  }

  const filteredTz = useMemo(() => {
    const q = tzFilter.trim().toLowerCase();
    if (!q) return timezones;
    return timezones.filter((z) => z.toLowerCase().includes(q));
  }, [timezones, tzFilter]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const patch = {
        timezone,
        brief_enabled: briefEnabled,
        brief_time_local: briefTime,
        brief_sections: sections,
        preferred_channel: preferredChannel,
        quiet_hours_start: quietEnabled ? quietStart : "",
        quiet_hours_end: quietEnabled ? quietEnd : "",
        feature_flags: { ...featureFlags, learn_from_conversations: learnFromChats },
      };
      const updated = await updateSettings(patch);
      applySettings(updated);
      setSuccess("Settings saved.");
    } catch (err) {
      if (err instanceof Error && err.message === "unauthorized") onLogout();
      else setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
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
          <span className="font-label-md text-label-md text-primary tracking-widest uppercase">Settings</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-space-lg py-space-xl">
        {loading ? (
          <p className="text-on-surface-variant animate-pulse">Loading settings…</p>
        ) : (
          <form onSubmit={(e) => void onSubmit(e)} className="space-y-space-xl">
            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Timezone</h2>
              <input
                type="search"
                placeholder="Search timezones…"
                value={tzFilter}
                onChange={(e) => setTzFilter(e.target.value)}
                className="w-full rounded-lg bg-surface-container-high px-space-md py-space-sm text-body-md"
              />
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full rounded-lg bg-surface-container-high px-space-md py-space-sm text-body-md"
                size={8}
              >
                {filteredTz.map((z) => (
                  <option key={z} value={z}>{z}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setTimezone(browserTimezone())}
                className="text-sm text-primary hover:underline"
              >
                Use browser timezone ({browserTimezone()})
              </button>
            </section>

            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Daily brief</h2>
              <label className="flex items-center gap-space-sm">
                <input
                  type="checkbox"
                  checked={briefEnabled}
                  onChange={(e) => setBriefEnabled(e.target.checked)}
                />
                Enable morning brief
              </label>
              <label className="block">
                <span className="text-label-sm text-on-surface-variant">Delivery time (local)</span>
                <input
                  type="time"
                  value={briefTime}
                  onChange={(e) => setBriefTime(e.target.value)}
                  className="mt-1 rounded-lg bg-surface-container-high px-space-md py-space-sm"
                />
              </label>
              <div className="space-y-2">
                {SECTION_LABELS.map(({ key, label, hint }) => (
                  <label key={key} className="flex flex-col gap-0.5">
                    <span className="flex items-center gap-space-sm">
                      <input
                        type="checkbox"
                        checked={sections[key]}
                        onChange={(e) => setSections((s) => ({ ...s, [key]: e.target.checked }))}
                      />
                      {label}
                    </span>
                    {hint ? <span className="text-label-sm text-outline pl-6">{hint}</span> : null}
                  </label>
                ))}
              </div>
            </section>

            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Memory</h2>
              <label className="flex items-center gap-space-sm">
                <input
                  type="checkbox"
                  checked={learnFromChats}
                  onChange={(e) => setLearnFromChats(e.target.checked)}
                />
                Learn from my conversations
              </label>
              <p className="text-label-sm text-on-surface-variant">
                When this is off, JARVIS only stores memories you explicitly ask it to remember.
              </p>
            </section>

            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Quiet hours</h2>
              <label className="flex items-center gap-space-sm">
                <input
                  type="checkbox"
                  checked={quietEnabled}
                  onChange={(e) => setQuietEnabled(e.target.checked)}
                />
                Limit notifications during quiet hours
              </label>
              {quietEnabled ? (
                <div className="flex flex-wrap gap-space-md">
                  <label>
                    <span className="text-label-sm text-on-surface-variant">Start</span>
                    <input
                      type="time"
                      value={quietStart}
                      onChange={(e) => setQuietStart(e.target.value)}
                      className="mt-1 block rounded-lg bg-surface-container-high px-space-md py-space-sm"
                    />
                  </label>
                  <label>
                    <span className="text-label-sm text-on-surface-variant">End</span>
                    <input
                      type="time"
                      value={quietEnd}
                      onChange={(e) => setQuietEnd(e.target.value)}
                      className="mt-1 block rounded-lg bg-surface-container-high px-space-md py-space-sm"
                    />
                  </label>
                </div>
              ) : null}
            </section>

            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Telegram</h2>
              <p className="text-label-sm text-on-surface-variant">
                {telegram.linked
                  ? `Connected${telegram.username ? ` as @${telegram.username}` : ""}.`
                  : "Link a Telegram chat so JARVIS can reply there."}
              </p>
              {telegram.linked ? (
                <button
                  type="button"
                  disabled={telegramBusy}
                  onClick={() => void onDisconnectTelegram()}
                  className="px-space-md py-space-sm rounded-lg bg-surface-container-high disabled:opacity-50"
                >
                  Disconnect Telegram
                </button>
              ) : (
                <button
                  type="button"
                  disabled={telegramBusy}
                  onClick={() => void connectTelegram()}
                  className="px-space-md py-space-sm rounded-lg bg-primary-container text-on-primary disabled:opacity-50"
                >
                  {telegramBusy ? "Waiting for Telegram…" : "Connect Telegram"}
                </button>
              )}
              {telegramNote ? <p className="text-label-sm text-on-surface-variant">{telegramNote}</p> : null}
            </section>

            <section className="rounded-xl bg-surface-container-low p-space-lg space-y-space-md">
              <h2 className="font-headline-sm text-headline-sm text-primary">Preferred channel</h2>
              <div className="flex flex-col gap-space-sm">
                <label className="flex items-center gap-space-sm">
                  <input
                    type="radio"
                    name="channel"
                    checked={preferredChannel === "web"}
                    onChange={() => setPreferredChannel("web")}
                  />
                  Web
                </label>
                <label className={`flex items-center gap-space-sm ${telegram.linked ? "" : "opacity-60"}`}>
                  <input
                    type="radio"
                    name="channel"
                    disabled={!telegram.linked}
                    checked={preferredChannel === "telegram"}
                    onChange={() => setPreferredChannel("telegram")}
                  />
                  Telegram
                </label>
              </div>
            </section>

            {error ? <p className="text-error text-sm">{error}</p> : null}
            {success ? <p className="text-primary text-sm">{success}</p> : null}

            <button
              type="submit"
              disabled={saving}
              className="w-full py-space-sm rounded-lg bg-primary-container text-on-primary font-semibold disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save settings"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
