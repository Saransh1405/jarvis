-- Phase 4 Phase 1: channels, durable jobs, notification audit log.

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'web',
    ADD COLUMN IF NOT EXISTS channel_chat_id TEXT NULL;

CREATE INDEX IF NOT EXISTS conversations_channel_chat_idx
    ON conversations (user_id, channel, channel_chat_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_channels (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           TEXT NOT NULL,
    channel           TEXT NOT NULL,
    external_id       TEXT NOT NULL,
    external_username TEXT NULL,
    status            TEXT NOT NULL DEFAULT 'active',
    linked_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_inbound_at   TIMESTAMPTZ NULL,
    CONSTRAINT user_channels_status_check
        CHECK (status IN ('active', 'blocked', 'unlinked')),
    CONSTRAINT user_channels_user_channel_unique UNIQUE (user_id, channel),
    CONSTRAINT user_channels_external_unique UNIQUE (channel, external_id)
);

CREATE TABLE IF NOT EXISTS channel_link_tokens (
    token_hash BYTEA PRIMARY KEY,
    user_id    TEXT NOT NULL,
    channel    TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS channel_link_tokens_user_idx
    ON channel_link_tokens (user_id, channel, expires_at DESC);

CREATE TABLE IF NOT EXISTS channel_updates_seen (
    channel     TEXT NOT NULL,
    update_id   BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (channel, update_id)
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind         TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    run_at       TIMESTAMPTZ NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'scheduled',
    attempts     INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    locked_until TIMESTAMPTZ NULL,
    last_error   TEXT NULL,
    dedupe_key   TEXT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT scheduled_jobs_status_check
        CHECK (status IN ('scheduled', 'running', 'done', 'failed', 'cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS scheduled_jobs_dedupe
    ON scheduled_jobs (dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS scheduled_jobs_due
    ON scheduled_jobs (run_at) WHERE status IN ('scheduled', 'running');

CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    kind       TEXT NOT NULL,
    ref_id     UUID NULL,
    channel    TEXT NOT NULL,
    status     TEXT NOT NULL,
    dedupe_key TEXT NULL,
    error      TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at    TIMESTAMPTZ NULL,
    CONSTRAINT notifications_status_check
        CHECK (status IN ('queued', 'sent', 'failed', 'skipped'))
);

-- Failed rows stay for audit and do not block a retry of the same key.
CREATE UNIQUE INDEX IF NOT EXISTS notifications_dedupe_active
    ON notifications (dedupe_key)
    WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'sent');

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    id      TEXT PRIMARY KEY,
    beat_at TIMESTAMPTZ NOT NULL
);
