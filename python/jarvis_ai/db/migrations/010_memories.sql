-- Personal memory on the pgvector extension created in 005_rag_pgvector.sql.
-- user_id stays TEXT so it matches memory_facts, documents, and conversations.

CREATE TABLE IF NOT EXISTS memories (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           TEXT NOT NULL,
    kind              TEXT NOT NULL CHECK (kind IN ('fact', 'preference', 'person', 'goal', 'episode')),
    content           TEXT NOT NULL,
    embedding         vector(1536),
    embedding_model   TEXT,
    importance        SMALLINT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    confidence        REAL NOT NULL DEFAULT 0.8,
    source            TEXT NOT NULL CHECK (source IN ('explicit', 'extracted', 'backfill', 'chat', 'manual', 'note')),
    source_message_id UUID,
    superseded_by     UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at  TIMESTAMPTZ,
    access_count      INT NOT NULL DEFAULT 0,
    expires_at        TIMESTAMPTZ,
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS memories_user_kind_idx
    ON memories (user_id, kind)
    WHERE deleted_at IS NULL AND superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS memories_embedding_idx
    ON memories USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS memories_pending_embed_idx
    ON memories (created_at)
    WHERE embedding IS NULL AND deleted_at IS NULL;

ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS migrated_at TIMESTAMPTZ;

INSERT INTO memories (user_id, kind, content, source, created_at, importance, confidence)
SELECT f.user_id, 'fact', f.content, 'backfill', f.created_at, 3, 0.8
FROM memory_facts f
WHERE f.migrated_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM memories m
      WHERE m.user_id = f.user_id AND m.content = f.content
  );

UPDATE memory_facts
SET migrated_at = NOW()
WHERE migrated_at IS NULL;

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS summary TEXT;
