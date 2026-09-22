CREATE TABLE IF NOT EXISTS tool_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    tool_name TEXT NOT NULL,
    arguments JSONB NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tool_call_logs_user_created_idx
    ON tool_call_logs (user_id, created_at DESC);
