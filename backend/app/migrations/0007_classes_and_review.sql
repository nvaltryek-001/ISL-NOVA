-- Teacher classes (learners join with a code and can leave at any time) and
-- spaced-repetition review state per learner and sign.
CREATE TABLE classes (
    id          {{PK}},
    name        VARCHAR(120) NOT NULL,
    teacher_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    join_code   VARCHAR(16) NOT NULL UNIQUE,
    created_at  {{TS}} NOT NULL
);
CREATE INDEX ix_classes_teacher ON classes(teacher_id);

CREATE TABLE class_members (
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at  {{TS}} NOT NULL,
    PRIMARY KEY (class_id, user_id)
);
CREATE INDEX ix_class_members_user ON class_members(user_id);

ALTER TABLE learning_progress ADD COLUMN review_box INTEGER NOT NULL DEFAULT 0;
ALTER TABLE learning_progress ADD COLUMN due_at {{TS}};
