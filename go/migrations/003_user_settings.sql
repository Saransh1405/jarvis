-- Phase 4 M0: per-user settings (timezone, brief, quiet hours, channels)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id            UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    timezone           TEXT NOT NULL DEFAULT 'UTC',
    locale             TEXT NOT NULL DEFAULT 'en',
    preferred_channel  TEXT NOT NULL DEFAULT 'web',
    quiet_hours_start  TIME NULL,
    quiet_hours_end    TIME NULL,
    brief_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    brief_time_local   TIME NOT NULL DEFAULT '08:00',
    brief_sections     JSONB NOT NULL DEFAULT '{"reminders":true,"calendar":true,"email":true,"weather":false}',
    feature_flags      JSONB NOT NULL DEFAULT '{}',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_settings_preferred_channel_check
        CHECK (preferred_channel IN ('web', 'telegram')),
    CONSTRAINT user_settings_quiet_hours_pair_check
        CHECK (
            (quiet_hours_start IS NULL AND quiet_hours_end IS NULL)
            OR (quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL)
        )
);

INSERT INTO user_settings (user_id)
SELECT id FROM users
ON CONFLICT (user_id) DO NOTHING;
