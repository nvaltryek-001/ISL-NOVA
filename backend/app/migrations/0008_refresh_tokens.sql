-- Rotating refresh tokens. Only a SHA-256 of each token is stored. Every refresh
-- replaces the token (rotation); presenting a token that was already rotated
-- revokes the whole family (theft detection). Tokens issued before a
-- "sign out everywhere" (users.token_version bump) stop working.
CREATE TABLE refresh_tokens (
    id            {{PK}},
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    VARCHAR(64) NOT NULL UNIQUE,
    family        VARCHAR(32) NOT NULL,
    token_version INTEGER NOT NULL,
    expires_at    {{TS}} NOT NULL,
    created_at    {{TS}} NOT NULL,
    used_at       {{TS}},
    revoked_at    {{TS}},
    user_agent    VARCHAR(200)
);
CREATE INDEX ix_refresh_user ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_family ON refresh_tokens(family);
