-- ISL NOVA v2: transliteration and review timestamp for en/hi/kn meanings.
ALTER TABLE translations ADD COLUMN transliteration TEXT;
ALTER TABLE translations ADD COLUMN reviewed_at {{TS}};
