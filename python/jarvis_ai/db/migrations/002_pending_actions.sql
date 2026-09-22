CREATE TABLE IF NOT EXISTS pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    tool_call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments JSONB NOT NULL,
    messages JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pending_actions_user_status_idx
    ON pending_actions (user_id, status, created_at DESC);
