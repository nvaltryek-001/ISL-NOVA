-- Sign out everywhere: tokens carry a 'tv' claim that must match users.token_version.
ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
