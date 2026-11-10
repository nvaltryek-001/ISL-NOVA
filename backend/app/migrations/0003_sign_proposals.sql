-- ISL NOVA v2: proposals for new vocabulary entries (toward 500 signs), reviewed by linguists.
CREATE TABLE sign_proposals (
    id              {{PK}},
    gloss           VARCHAR(200) NOT NULL,
    gloss_key       VARCHAR(200) NOT NULL,
    category        VARCHAR(60) NOT NULL,
    english_meaning VARCHAR(200),
    hindi_meaning   VARCHAR(200),
    kannada_meaning VARCHAR(200),
    reference_url   TEXT,
    notes           TEXT,
    proposer_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewer_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decision_note   TEXT,
    created_sign_id VARCHAR(16),
    created_at      {{TS}} NOT NULL,
    decided_at      {{TS}},
    CHECK (status IN ('pending','accepted','rejected'))
);
CREATE INDEX ix_sign_proposals_status ON sign_proposals(status);
CREATE INDEX ix_sign_proposals_key ON sign_proposals(gloss_key);
