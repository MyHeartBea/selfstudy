"""SQLite 表结构 DDL 与错题字段常量。"""

TABLES_DDL = """
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sub_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    sub_subject_id INTEGER REFERENCES sub_subjects(id),
    question_type TEXT DEFAULT 'choice',
    question TEXT NOT NULL,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_answer TEXT,
    answer_aliases TEXT,
    analysis TEXT,
    difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 5),
    difficulty_points TEXT,
    knowledge_tags TEXT,
    approach TEXT,
    source TEXT,
    source_type TEXT DEFAULT '',
    source_year TEXT DEFAULT '',
    source_name TEXT DEFAULT '',
    review_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    mastery_level INTEGER DEFAULT 0,
    last_reviewed_at DATETIME,
    next_review_at DATETIME,
    review_paused INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id),
    result TEXT NOT NULL,
    note TEXT,
    user_answer TEXT,
    reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT UNIQUE COLLATE NOCASE NOT NULL,
    subject_id INTEGER REFERENCES subjects(id),
    sub_subject_id INTEGER REFERENCES sub_subjects(id),
    summary TEXT,
    related_tags TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subject_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL UNIQUE REFERENCES subjects(id),
    focus_areas TEXT,
    review_tips TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS solution_grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id),
    user_answer TEXT,
    score INTEGER,
    verdict TEXT,
    feedback TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formula_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL DEFAULT '高等数学',
    title TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_mistakes_subject_id ON mistakes(subject_id);
CREATE INDEX IF NOT EXISTS idx_mistakes_sub_subject_id ON mistakes(sub_subject_id);
CREATE INDEX IF NOT EXISTS idx_mistakes_source_type ON mistakes(source_type);
CREATE INDEX IF NOT EXISTS idx_mistakes_next_review_at ON mistakes(next_review_at);
CREATE INDEX IF NOT EXISTS idx_review_records_mistake_id ON review_records(mistake_id);
CREATE INDEX IF NOT EXISTS idx_review_records_reviewed_at ON review_records(reviewed_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_subject_id ON knowledge_base(subject_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_subject_subject ON knowledge_base(subject_id, sub_subject_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_created_at ON knowledge_base(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_formula_items_category ON formula_items(category);
"""

MISTAKE_COLUMNS = (
    "subject_id",
    "sub_subject_id",
    "question_type",
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "answer_aliases",
    "analysis",
    "difficulty",
    "difficulty_points",
    "knowledge_tags",
    "approach",
    "source",
    "source_type",
    "source_year",
    "source_name",
)

MISTAKE_FIELD_KEYS = {
    "knowledge_tags": "knowledge_tags_text",
    "answer_aliases": "answer_aliases_text",
}
