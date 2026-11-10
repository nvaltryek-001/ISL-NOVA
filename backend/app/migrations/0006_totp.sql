-- Optional TOTP two-factor sign-in. totp_last_step blocks replay of a used code.
ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64);
ALTER TABLE users ADD COLUMN totp_enabled {{BOOL}} NOT NULL DEFAULT {{FALSE}};
ALTER TABLE users ADD COLUMN totp_last_step BIGINT;
