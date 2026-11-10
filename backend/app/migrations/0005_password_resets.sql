-- Password reset without an email service: an admin issues a one-time code that
-- the user redeems. Only the SHA-256 of the code is stored.
CREATE TABLE password_resets (
    id          {{PK}},
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    issued_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    expires_at  {{TS}} NOT NULL,
    used_at     {{TS}},
    created_at  {{TS}} NOT NULL
);
CREATE INDEX ix_password_resets_user ON password_resets(user_id);
