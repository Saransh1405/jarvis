-- Reminder delivery state and one row per morning-brief attempt.

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'UTC';
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS last_fired_at TIMESTAMPTZ NULL;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS rrule TEXT NULL;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS lead_minutes INT NULL;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'chat';

-- Nullable first so existing done rows can be backfilled before the default applies.
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS status TEXT;

UPDATE reminders
SET status = CASE WHEN done THEN 'done' ELSE 'scheduled' END
WHERE status IS NULL;

ALTER TABLE reminders ALTER COLUMN status SET DEFAULT 'scheduled';
ALTER TABLE reminders ALTER COLUMN status SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'reminders_status_check'
    ) THEN
        ALTER TABLE reminders
            ADD CONSTRAINT reminders_status_check
            CHECK (status IN ('scheduled', 'fired', 'done', 'snoozed', 'cancelled', 'missed'));
    END IF;
END $$;

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS body TEXT NULL;

CREATE TABLE IF NOT EXISTS brief_runs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    local_date DATE NOT NULL,
    status     TEXT NOT NULL,
    dedupe_key TEXT NULL,
    error      TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT brief_runs_status_check
        CHECK (status IN ('sent', 'skipped', 'failed', 'deduped'))
);

CREATE INDEX IF NOT EXISTS brief_runs_user_date_idx
    ON brief_runs (user_id, local_date DESC);
