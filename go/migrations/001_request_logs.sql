CREATE TABLE IF NOT EXISTS request_logs (
    id          BIGSERIAL PRIMARY KEY,
    request_id  TEXT        NOT NULL,
    method      TEXT        NOT NULL,
    path        TEXT        NOT NULL,
    status      INT         NOT NULL,
    latency_ms  BIGINT      NOT NULL,
    client_ip   TEXT,
    user_id     TEXT,
    bytes_out   INT         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_request_logs_request_id ON request_logs (request_id);
