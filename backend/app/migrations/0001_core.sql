-- ISL NOVA core schema (portable: tokens are expanded per dialect by migrate.py)
-- {{PK}} integer surrogate key, {{TS}} UTC timestamp, {{JSON}} JSON document,
-- {{BOOL}} boolean, {{TRUE}}/{{FALSE}} boolean literals.

CREATE TABLE roles (
    name        VARCHAR(40) PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE users (
    id            {{PK}},
    email         VARCHAR(254) NOT NULL UNIQUE,
    display_name  VARCHAR(120) NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     {{BOOL}} NOT NULL DEFAULT {{TRUE}},
    preferred_language VARCHAR(8) NOT NULL DEFAULT 'en',
    settings      {{JSON}},
    created_at    {{TS}} NOT NULL,
    last_login_at {{TS}}
);

CREATE TABLE user_roles (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_name  VARCHAR(40) NOT NULL REFERENCES roles(name),
    granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    granted_at {{TS}} NOT NULL,
    PRIMARY KEY (user_id, role_name)
);

CREATE TABLE signs (
    sign_id                VARCHAR(16) PRIMARY KEY,
    canonical_sign_name    VARCHAR(200) NOT NULL,
    source_gloss           VARCHAR(120),
    category               VARCHAR(60) NOT NULL,
    category_label         VARCHAR(120),
    source_category        VARCHAR(120),
    linguistic_description TEXT,
    dominant_hand          VARCHAR(20),
    hands_required         VARCHAR(20),
    movement_type          VARCHAR(20),
    body_movement          TEXT,
    non_manual_cue         TEXT,
    regional_variation     TEXT,
    annotation_notes       TEXT,
    verification_status    VARCHAR(20) NOT NULL DEFAULT 'proposed',
    data_readiness         VARCHAR(30) NOT NULL DEFAULT 'no_data',
    reviewer               VARCHAR(120),
    approval_date          {{TS}},
    external_train_videos  INTEGER NOT NULL DEFAULT 0,
    external_val_videos    INTEGER NOT NULL DEFAULT 0,
    external_test_videos   INTEGER NOT NULL DEFAULT 0,
    retired                {{BOOL}} NOT NULL DEFAULT {{FALSE}},
    created_at             {{TS}} NOT NULL,
    updated_at             {{TS}} NOT NULL,
    CHECK (verification_status IN ('proposed','reference_found','review_pending','verified','rejected')),
    CHECK (data_readiness IN ('no_data','collecting','insufficient_data','ready_for_review','approved_for_training','excluded'))
);
CREATE INDEX ix_signs_category ON signs(category);
CREATE INDEX ix_signs_status ON signs(verification_status);

CREATE TABLE translations (
    id         {{PK}},
    sign_id    VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    language   VARCHAR(8) NOT NULL,
    text       TEXT NOT NULL DEFAULT '',
    status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    source     TEXT,
    reviewer   VARCHAR(120),
    updated_at {{TS}} NOT NULL,
    UNIQUE (sign_id, language),
    CHECK (status IN ('pending','source_gloss','draft','verified','rejected'))
);

CREATE TABLE sign_references (
    id                 {{PK}},
    sign_id            VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    source_name        VARCHAR(120) NOT NULL,
    source_url         TEXT,
    doi                VARCHAR(120),
    license            VARCHAR(120),
    media_type         VARCHAR(60),
    media_url          TEXT,
    training_permitted VARCHAR(200),
    attribution        TEXT,
    notes              TEXT
);
CREATE INDEX ix_refs_sign ON sign_references(sign_id);

CREATE TABLE verification_events (
    id          {{PK}},
    sign_id     VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    from_status VARCHAR(20),
    to_status   VARCHAR(20) NOT NULL,
    actor_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    note        TEXT,
    created_at  {{TS}} NOT NULL
);
CREATE INDEX ix_verif_sign ON verification_events(sign_id);

CREATE TABLE pseudonymous_signers (
    id            {{PK}},
    signer_code   VARCHAR(32) NOT NULL UNIQUE,
    dominant_hand VARCHAR(10),
    age_band      VARCHAR(20),
    region        VARCHAR(80),
    deaf_status   VARCHAR(40),
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    {{TS}} NOT NULL
);

CREATE TABLE consent_records (
    id                   {{PK}},
    signer_id            INTEGER NOT NULL REFERENCES pseudonymous_signers(id) ON DELETE CASCADE,
    consent_text_version VARCHAR(40) NOT NULL,
    scopes               {{JSON}} NOT NULL,
    retention_until      {{TS}},
    recorded_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    granted_at           {{TS}} NOT NULL,
    revoked_at           {{TS}},
    revocation_reason    TEXT
);
CREATE INDEX ix_consent_signer ON consent_records(signer_id);

CREATE TABLE recording_sessions (
    id              {{PK}},
    session_code    VARCHAR(40) NOT NULL UNIQUE,
    signer_id       INTEGER NOT NULL REFERENCES pseudonymous_signers(id) ON DELETE CASCADE,
    environment     {{JSON}},
    notes           TEXT,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      {{TS}} NOT NULL
);

CREATE TABLE recordings (
    id                {{PK}},
    recording_code    VARCHAR(64) NOT NULL UNIQUE,
    sign_id           VARCHAR(16) NOT NULL REFERENCES signs(sign_id),
    session_id        INTEGER NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
    consent_id        INTEGER NOT NULL REFERENCES consent_records(id),
    source            VARCHAR(20) NOT NULL DEFAULT 'local',
    storage_key       TEXT,
    landmarks_key     TEXT,
    mime_type         VARCHAR(60),
    size_bytes        INTEGER,
    sha256            VARCHAR(64),
    duration_s        DOUBLE PRECISION,
    fps               DOUBLE PRECISION,
    width             INTEGER,
    height            INTEGER,
    quality           {{JSON}},
    status            VARCHAR(20) NOT NULL DEFAULT 'pending_review',
    uploaded_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at        {{TS}} NOT NULL,
    deleted_at        {{TS}},
    CHECK (status IN ('pending_review','approved','rejected','deleted','quarantined'))
);
CREATE INDEX ix_rec_sign ON recordings(sign_id);
CREATE INDEX ix_rec_status ON recordings(status);
CREATE INDEX ix_rec_session ON recordings(session_id);
CREATE INDEX ix_rec_sha ON recordings(sha256);

CREATE TABLE annotations (
    id            {{PK}},
    recording_id  INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    annotator_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    label_sign_id VARCHAR(16) REFERENCES signs(sign_id),
    start_ms      INTEGER,
    end_ms        INTEGER,
    notes         TEXT,
    decision      VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewer_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at   {{TS}},
    created_at    {{TS}} NOT NULL,
    CHECK (decision IN ('pending','approved','rejected','needs_changes'))
);
CREATE INDEX ix_ann_rec ON annotations(recording_id);

CREATE TABLE feature_contracts (
    name        VARCHAR(60) PRIMARY KEY,
    version     VARCHAR(20) NOT NULL,
    definition  {{JSON}} NOT NULL,
    created_at  {{TS}} NOT NULL
);

CREATE TABLE dataset_versions (
    id            {{PK}},
    version       VARCHAR(40) NOT NULL UNIQUE,
    description   TEXT,
    contract_name VARCHAR(60) REFERENCES feature_contracts(name),
    summary       {{JSON}},
    manifest_sha256 VARCHAR(64),
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    {{TS}} NOT NULL
);

CREATE TABLE manifest_entries (
    id                 {{PK}},
    dataset_version_id INTEGER NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    recording_id       INTEGER NOT NULL REFERENCES recordings(id),
    sign_id            VARCHAR(16) NOT NULL REFERENCES signs(sign_id),
    split              VARCHAR(10) NOT NULL,
    signer_code        VARCHAR(32) NOT NULL,
    session_code       VARCHAR(40) NOT NULL,
    UNIQUE (dataset_version_id, recording_id),
    CHECK (split IN ('train','val','test'))
);

CREATE TABLE experiments (
    id                 {{PK}},
    name               VARCHAR(120) NOT NULL,
    model_kind         VARCHAR(30) NOT NULL,
    config             {{JSON}} NOT NULL,
    dataset_version_id INTEGER REFERENCES dataset_versions(id),
    status             VARCHAR(20) NOT NULL DEFAULT 'created',
    log                TEXT,
    error              TEXT,
    model_id           VARCHAR(120),
    created_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at         {{TS}} NOT NULL,
    started_at         {{TS}},
    finished_at        {{TS}},
    CHECK (status IN ('created','queued','running','succeeded','failed','blocked'))
);

CREATE TABLE experiment_metrics (
    id            {{PK}},
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    split         VARCHAR(10) NOT NULL,
    name          VARCHAR(60) NOT NULL,
    value         DOUBLE PRECISION,
    epoch         INTEGER
);
CREATE INDEX ix_expm_exp ON experiment_metrics(experiment_id);

CREATE TABLE model_versions (
    model_id        VARCHAR(120) PRIMARY KEY,
    kind            VARCHAR(30) NOT NULL,
    experiment_id   INTEGER REFERENCES experiments(id) ON DELETE SET NULL,
    dataset_version VARCHAR(40),
    contract_name   VARCHAR(60),
    synthetic       {{BOOL}} NOT NULL DEFAULT {{FALSE}},
    status          VARCHAR(20) NOT NULL DEFAULT 'candidate',
    summary         {{JSON}},
    registered_at   {{TS}} NOT NULL
);

CREATE TABLE evaluation_results (
    id         {{PK}},
    model_id   VARCHAR(120) NOT NULL REFERENCES model_versions(model_id) ON DELETE CASCADE,
    split      VARCHAR(10) NOT NULL,
    report     {{JSON}} NOT NULL,
    created_at {{TS}} NOT NULL
);

CREATE TABLE recognition_history (
    id          {{PK}},
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_id    VARCHAR(120),
    state       VARCHAR(30) NOT NULL,
    top         {{JSON}},
    chosen_sign VARCHAR(16) REFERENCES signs(sign_id),
    corrected_sign VARCHAR(16) REFERENCES signs(sign_id),
    created_at  {{TS}} NOT NULL
);
CREATE INDEX ix_hist_user ON recognition_history(user_id);

CREATE TABLE learning_progress (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sign_id      VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    attempts     INTEGER NOT NULL DEFAULT 0,
    correct      INTEGER NOT NULL DEFAULT 0,
    last_seen_at {{TS}},
    PRIMARY KEY (user_id, sign_id)
);

CREATE TABLE learning_attempts (
    id         {{PK}},
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sign_id    VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    mode       VARCHAR(20) NOT NULL,
    correct    {{BOOL}} NOT NULL,
    answer     VARCHAR(120),
    created_at {{TS}} NOT NULL
);
CREATE INDEX ix_attempt_user ON learning_attempts(user_id);

CREATE TABLE feedback (
    id         {{PK}},
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    kind       VARCHAR(30) NOT NULL,
    sign_id    VARCHAR(16) REFERENCES signs(sign_id) ON DELETE SET NULL,
    message    TEXT NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'open',
    resolution TEXT,
    created_at {{TS}} NOT NULL,
    CHECK (kind IN ('prediction','correction','bug','content','accessibility','other')),
    CHECK (status IN ('open','resolved','dismissed'))
);

CREATE TABLE audit_logs (
    id         {{PK}},
    actor_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     VARCHAR(80) NOT NULL,
    target     VARCHAR(160),
    detail     {{JSON}},
    ip         VARCHAR(64),
    created_at {{TS}} NOT NULL
);
CREATE INDEX ix_audit_created ON audit_logs(created_at);

CREATE TABLE bookmarks (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sign_id    VARCHAR(16) NOT NULL REFERENCES signs(sign_id) ON DELETE CASCADE,
    created_at {{TS}} NOT NULL,
    PRIMARY KEY (user_id, sign_id)
);

CREATE TABLE notifications (
    id         {{PK}},
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(200) NOT NULL,
    body       TEXT,
    read_at    {{TS}},
    created_at {{TS}} NOT NULL
);

CREATE TABLE phrases (
    id         {{PK}},
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    sign_ids   {{JSON}} NOT NULL,
    text       TEXT NOT NULL,
    language   VARCHAR(8) NOT NULL DEFAULT 'en',
    is_quick   {{BOOL}} NOT NULL DEFAULT {{FALSE}},
    created_at {{TS}} NOT NULL
);

CREATE TABLE analysis_jobs (
    id           {{PK}},
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    storage_key  TEXT,
    filename     VARCHAR(200),
    mime_type    VARCHAR(60),
    size_bytes   INTEGER,
    status       VARCHAR(30) NOT NULL DEFAULT 'queued',
    result       {{JSON}},
    error        TEXT,
    expires_at   {{TS}} NOT NULL,
    created_at   {{TS}} NOT NULL,
    finished_at  {{TS}}
);
