import { useState, type FormEvent } from "react";
import { authRequest, setToken, type AuthMode } from "../api";
import { ArcCoreHologram } from "./ArcCoreHologram";
import { MaterialIcon } from "./MaterialIcon";

type AuthViewProps = {
  onSuccess: () => void;
  onBack?: () => void;
};

export function AuthView({ onSuccess, onBack }: AuthViewProps) {
  const [mode, setMode] = useState<AuthMode>("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || password.length < 8) {
      setError("Enter an email and a password of at least 8 characters.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const { access_token } = await authRequest(mode, trimmed, password);
      setToken(access_token);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const tabActive =
    "py-space-xs px-space-sm rounded-lg font-headline-sm text-body-sm font-semibold flex items-center justify-center gap-space-xs bg-primary-container text-on-primary-container shadow-[0_0_16px_rgba(25,227,255,0.4)]";
  const tabIdle =
    "py-space-xs px-space-sm rounded-lg font-headline-sm text-body-sm font-medium flex items-center justify-center gap-space-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/50 transition-all";

  return (
    <div className="min-h-screen bg-surface font-body-md text-on-surface flex flex-col">
      <header className="fixed top-0 w-full z-50 bg-surface-container-lowest/85 backdrop-blur-xl shadow-[0_1px_16px_rgba(0,0,0,0.6)]">
        <div className="h-20 w-full px-gutter flex items-center gap-space-sm">
          <ArcCoreHologram variant="sm" className="h-8 w-8" />
          <span className="font-headline-md text-headline-md tracking-tight uppercase text-primary">JARVIS</span>
        </div>
      </header>

      <main className="flex-1 pt-20 flex items-center justify-center p-space-md md:p-space-xl relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-primary-container/10 to-transparent blur-3xl" />
        </div>

        <div className="relative w-full max-w-[540px] z-10">
          <div className="absolute -top-3 -left-3 w-6 h-6 border-t-2 border-l-2 border-primary-container/70 pointer-events-none" />
          <div className="absolute -top-3 -right-3 w-6 h-6 border-t-2 border-r-2 border-primary-container/70 pointer-events-none" />
          <div className="absolute -bottom-3 -left-3 w-6 h-6 border-b-2 border-l-2 border-primary-container/70 pointer-events-none" />
          <div className="absolute -bottom-3 -right-3 w-6 h-6 border-b-2 border-r-2 border-primary-container/70 pointer-events-none" />

          <div className="w-full bg-surface-container-low/80 backdrop-blur-2xl rounded-2xl shadow-[0_16px_48px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col">
            <div className="h-1 w-full bg-gradient-to-r from-transparent via-primary-container to-transparent shadow-[0_0_12px_rgba(25,227,255,0.8)]" />

            <div className="p-space-lg md:p-space-xl flex flex-col gap-space-lg">
              <div className="flex flex-col items-center text-center gap-space-md">
                <ArcCoreHologram variant="auth" />
                <h1 className="font-headline-md text-headline-md tracking-tight uppercase text-on-surface">
                  {isSignup ? "Initialize Neural Link" : "Resume Session"}
                </h1>
                <p className="font-body-sm text-body-sm text-on-surface-variant max-w-sm">
                  Direct telemetry uplink to autonomous workspace intelligence.
                </p>
                <div className="flex items-center gap-space-xs px-space-md py-space-xs rounded-full bg-surface-container-high/80">
                  <span className="w-2 h-2 rounded-full bg-primary-container animate-pulse" />
                  <span className="font-label-sm text-label-sm text-primary uppercase">STATUS: ENCRYPTED</span>
                </div>
              </div>

              <div className="w-full grid grid-cols-2 p-1 rounded-xl bg-surface-container-lowest/80 gap-1" role="tablist">
                <button type="button" role="tab" className={isSignup ? tabActive : tabIdle} onClick={() => { setMode("signup"); setError(""); }}>
                  <MaterialIcon name="fingerprint" className="text-[16px]" />
                  Create Identity
                </button>
                <button type="button" role="tab" className={!isSignup ? tabActive : tabIdle} onClick={() => { setMode("login"); setError(""); }}>
                  <MaterialIcon name="terminal" className="text-[16px]" />
                  Resume Session
                </button>
              </div>

              <form className="flex flex-col gap-space-md" onSubmit={onSubmit} noValidate>
                <div className="flex flex-col gap-1.5">
                  <label className="font-label-sm text-label-sm uppercase text-on-surface-variant flex items-center gap-space-xs" htmlFor="email">
                    <span className="text-primary-container">&gt;_</span>
                    COMM_HANDLE // NEURAL ID
                  </label>
                  <div className="relative group">
                    <MaterialIcon
                      name="alternate_email"
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline group-focus-within:text-primary-container"
                    />
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="w-full bg-surface-container/90 text-on-surface placeholder:text-outline font-label-md text-label-md pl-10 pr-space-md py-3 rounded-xl shadow-[inset_0_1px_4px_rgba(0,0,0,0.6)] focus:outline-none focus:shadow-[0_0_14px_rgba(25,227,255,0.2)] transition-all"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="font-label-sm text-label-sm uppercase text-on-surface-variant flex items-center gap-space-xs" htmlFor="password">
                    <span className="text-primary-container">#_</span>
                    CIPHER_PASSPHRASE
                  </label>
                  <div className="relative group">
                    <MaterialIcon
                      name="lock"
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline group-focus-within:text-primary-container"
                    />
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      minLength={8}
                      autoComplete={isSignup ? "new-password" : "current-password"}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full bg-surface-container/90 text-on-surface placeholder:text-outline font-label-md text-label-md pl-10 pr-11 py-3 rounded-xl shadow-[inset_0_1px_4px_rgba(0,0,0,0.6)] focus:outline-none focus:shadow-[0_0_14px_rgba(25,227,255,0.2)] transition-all tracking-wider"
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-outline hover:text-primary"
                      onClick={() => setShowPassword((v) => !v)}
                    >
                      <MaterialIcon name={showPassword ? "visibility_off" : "visibility"} className="text-[20px]" />
                    </button>
                  </div>
                </div>

                {error ? (
                  <p className="text-secondary font-body-sm text-body-sm" role="alert">
                    {error}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={submitting}
                  className="relative w-full py-space-md px-space-lg rounded-xl bg-primary-container text-on-primary-container font-headline-sm text-headline-sm font-bold uppercase shadow-[0_0_24px_rgba(25,227,255,0.45)] hover:brightness-110 active:scale-[0.99] transition-all flex items-center justify-center gap-space-sm disabled:opacity-60"
                >
                  <MaterialIcon name="power_settings_new" className="text-[24px]" />
                  {submitting ? "LINKING…" : isSignup ? "INITIALIZE JARVIS →" : "RESUME SESSION →"}
                </button>
              </form>

              {onBack ? (
                <button type="button" onClick={onBack} className="font-label-md text-label-md text-on-surface-variant hover:text-primary flex items-center gap-1 justify-center">
                  <MaterialIcon name="west" className="text-[16px]" />
                  RETURN TO INTRO
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
