import { useCallback, useEffect, useState } from "react";
import { clearToken, fetchConversations, getToken } from "./api";
import { AuthView } from "./components/AuthView";
import { ChatView } from "./components/ChatView";
import "./app.css";

type Screen = "auth" | "chat";

export default function App() {
  const [screen, setScreen] = useState<Screen>("auth");
  const [booting, setBooting] = useState(true);

  const goAuth = useCallback(() => {
    clearToken();
    setScreen("auth");
  }, []);

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
      } finally {
        setBooting(false);
      }
    }
    void boot();
  }, []);

  if (booting) return null;

  if (screen === "auth") {
    return <AuthView onSuccess={() => setScreen("chat")} />;
  }

  return <ChatView onLogout={goAuth} />;
}
