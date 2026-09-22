CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS memory_facts_user_created_idx
    ON memory_facts (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS memory_facts_content_trgm_idx
    ON memory_facts USING gin (content gin_trgm_ops);
