import { useState } from "react";
import { Icon } from "./Icon";

type MessageRowProps = {
  role: string;
  content: string;
  streaming?: boolean;
};

export function MessageRow({ role, content, streaming }: MessageRowProps) {
  const [copied, setCopied] = useState(false);
  const isUser = role === "user";

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  if (isUser) {
    return (
      <div className="row user">
        <div className="msg">{content}</div>
      </div>
    );
  }

  const cls = streaming ? "msg streaming" : "msg";

  return (
    <div className="row">
      <div className="av" aria-hidden="true">
        J
      </div>
      <div className="body">
        <div className={cls}>{content}</div>
        {!streaming && (
          <div className="tools">
            <button type="button" className="tool" onClick={() => void copy()}>
              <Icon paths='<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6.5A2.5 2.5 0 017.5 4H15"/>' />
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
