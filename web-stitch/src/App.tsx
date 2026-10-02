import { useEffect, useState } from "react";
import { clearToken, fetchConversations, getToken } from "./api";
import { AuthView } from "./components/AuthView";
import { CommandCoreView } from "./components/CommandCoreView";
import { LandingView } from "./components/LandingView";
import { SettingsView } from "./components/SettingsView";

type Screen = "landing" | "auth" | "chat" | "settings";

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    async function boot() {
      if (!getToken()) {
        setBooting(false);
        return;
      }
      try {
        await fetchConversations();
        setScreen("chat");
      } catch {
        clearToken();
        setScreen("landing");
      } finally {
        setBooting(false);
      }
    }
    void boot();
  }, []);

  if (booting) {
    return (
      <div className="min-h-screen bg-surface-container-lowest flex items-center justify-center">
        <span className="font-label-sm text-label-sm text-primary animate-pulse">SYS_INIT…</span>
      </div>
    );
  }

  if (screen === "landing") {
    return <LandingView onGetStarted={() => setScreen("auth")} onSignIn={() => setScreen("auth")} />;
  }

  if (screen === "auth") {
    return (
      <AuthView onSuccess={() => setScreen("chat")} onBack={() => setScreen("landing")} />
    );
  }

  if (screen === "settings") {
    return (
      <SettingsView
        onBack={() => setScreen("chat")}
        onLogout={() => {
          clearToken();
          setScreen("landing");
        }}
      />
    );
  }

  return (
    <CommandCoreView
      onLogout={() => setScreen("landing")}
      onOpenSettings={() => setScreen("settings")}
    />
  );
}
