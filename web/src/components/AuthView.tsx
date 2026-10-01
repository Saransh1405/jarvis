import { useState, type FormEvent } from "react";
import { authRequest, setToken, type AuthMode } from "../api";
import { Icon } from "./Icon";

type AuthViewProps = {
  onSuccess: () => void;
};

export function AuthView({ onSuccess }: AuthViewProps) {
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

  function toggleMode() {
    setMode(isSignup ? "login" : "signup");
    setError("");
  }

  return (
    <main id="auth">
      <section className="hero">
        <span className="mark">JARVIS</span>
        <h1>Your assistant, ready when you are.</h1>
        <div className="demo" aria-hidden="true">
          <div className="b u">Remind me to review the PR before standup</div>
          <div className="b a">Done. I&apos;ll nudge you at 9:15.</div>
        </div>
      </section>
      <section className="formside">
        <div className="panel">
          <h2>{isSignup ? "Create your account" : "Welcome back"}</h2>
          <p className="sub">It takes under a minute.</p>
          <form onSubmit={onSubmit} noValidate>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <div className="pw">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  minLength={8}
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  className="eye"
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <Icon paths='<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>' />
                </button>
              </div>
            </div>
            <p className="err" role="alert">
              {error}
            </p>
            <button className="btn" type="submit" disabled={submitting}>
              {isSignup ? "Sign up" : "Log in"}
            </button>
          </form>
          <p className="swap">
            <span>{isSignup ? "Already have an account?" : "New here?"} </span>
            <button className="link" type="button" onClick={toggleMode}>
              {isSignup ? "Log in" : "Sign up"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}
