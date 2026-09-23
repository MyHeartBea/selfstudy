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
    -- 收藏标星：只影响筛选展示，不参与复习调度
    starred INTEGER DEFAULT 0,
    -- SM-2 简化版自适应调度（v6）：难度系数与上次间隔天数
    ease_factor REAL DEFAULT 2.5,
    last_interval INTEGER DEFAULT 0,
    images TEXT,
    -- 英语整篇精读（可选）：解析后挂在一条错题上，供详情/复习回看
    passage_text TEXT,
    passage_translation TEXT,
    english_sentences TEXT,
    english_phrases TEXT,
    english_words TEXT,
    english_questions TEXT,
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
    errors TEXT,
    strengths TEXT,
    solution TEXT,
    alternate_methods TEXT,
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

-- 英语生词本：单词即闪卡，独立于错题的间隔重复
CREATE TABLE IF NOT EXISTS vocab_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE COLLATE NOCASE,
    meaning TEXT NOT NULL DEFAULT '',
    phonetic TEXT DEFAULT '',
    example TEXT DEFAULT '',
    note TEXT DEFAULT '',
    source TEXT DEFAULT '',
    kind TEXT DEFAULT 'word',
    mastery_level INTEGER DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    last_result TEXT DEFAULT '',
    last_reviewed_at DATETIME,
    next_review_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vocab_next_review_at ON vocab_items(next_review_at);
CREATE INDEX IF NOT EXISTS idx_vocab_mastery ON vocab_items(mastery_level);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 真题模考成绩存档（v7）：供统计页绘制模考分数趋势
CREATE TABLE IF NOT EXISTS mock_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_year TEXT DEFAULT '',
    total INTEGER DEFAULT 0,
    correct INTEGER DEFAULT 0,
    score INTEGER DEFAULT 0,
    duration_min INTEGER DEFAULT 60,
    used_seconds INTEGER DEFAULT 0,
    created_at DATETIME
);

-- 真题库（v8）：历年真题套卷与题目
CREATE TABLE IF NOT EXISTS exam_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT DEFAULT '',
    year TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source_path TEXT DEFAULT '',
    answer_path TEXT DEFAULT '',
    question_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    status_note TEXT DEFAULT '',
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS exam_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
    no TEXT DEFAULT '',
    section TEXT DEFAULT '',
    question_type TEXT DEFAULT 'choice',
    passage TEXT DEFAULT '',
    question TEXT DEFAULT '',
    option_a TEXT DEFAULT '',
    option_b TEXT DEFAULT '',
    option_c TEXT DEFAULT '',
    option_d TEXT DEFAULT '',
    correct_answer TEXT DEFAULT '',
    analysis TEXT DEFAULT '',
    knowledge_tags TEXT DEFAULT ''
);

-- 错题-知识点标签关联表：让"按标签检索"走索引，替代 instr(',tags,', ?) 全表扫描。
-- knowledge_tags 逗号串仍保留（展示用），此表只负责高效检索，由 service 层同步维护。
CREATE TABLE IF NOT EXISTS mistake_tag_map (
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (mistake_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_mistakes_subject_id ON mistakes(subject_id);
CREATE INDEX IF NOT EXISTS idx_mistakes_sub_subject_id ON mistakes(sub_subject_id);
CREATE INDEX IF NOT EXISTS idx_mistakes_source_type ON mistakes(source_type);
CREATE INDEX IF NOT EXISTS idx_mistakes_next_review_at ON mistakes(next_review_at);
CREATE INDEX IF NOT EXISTS idx_mistakes_question_type ON mistakes(question_type);
CREATE INDEX IF NOT EXISTS idx_mistakes_difficulty ON mistakes(difficulty);
CREATE INDEX IF NOT EXISTS idx_mistakes_source_year ON mistakes(source_year);
CREATE INDEX IF NOT EXISTS idx_mistakes_created_at ON mistakes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_records_mistake_id ON review_records(mistake_id);
CREATE INDEX IF NOT EXISTS idx_review_records_reviewed_at ON review_records(reviewed_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_subject_id ON knowledge_base(subject_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_subject_subject ON knowledge_base(subject_id, sub_subject_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_created_at ON knowledge_base(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_formula_items_category ON formula_items(category);
CREATE INDEX IF NOT EXISTS idx_mistake_tag_map_tag ON mistake_tag_map(tag);

-- v11 补齐：以下索引都按**真实查询形状**建，不给没人查的列建索引。
-- mistake_tag_map 的 (mistake_id, tag) 主键已覆盖 WHERE mistake_id=?，所以那里不需要新索引。
-- 1) AI 批改记录：错题详情每次取 last_grade 都是 "WHERE mistake_id=? ORDER BY id DESC LIMIT 1"，
--    删错题/批量删也要按 mistake_id 删，此前整表无索引（全表扫描）。
CREATE INDEX IF NOT EXISTS idx_solution_grades_mistake ON solution_grades(mistake_id, id DESC);
-- 2) 生词本是增长最快的表（一篇精读就能进几十条），列表默认排序 created_at DESC, id DESC。
CREATE INDEX IF NOT EXISTS idx_vocab_created ON vocab_items(created_at DESC, id DESC);
-- 3) 模考成绩存档：GET /api/mocks 固定 ORDER BY created_at DESC, id DESC LIMIT n。
CREATE INDEX IF NOT EXISTS idx_mock_records_created ON mock_records(created_at DESC, id DESC);
-- 4) 真题登记按 (source_path, year) 做幂等查重。
CREATE INDEX IF NOT EXISTS idx_exam_papers_source_year ON exam_papers(source_path, year);

-- 英语作文批改存档（v10）：AI 按考研评分档批改的记录（转录文本 + 完整批改 JSON）
CREATE TABLE IF NOT EXISTS essay_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT DEFAULT 'e2_long',
    prompt_text TEXT DEFAULT '',
    essay_text TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    max_score INTEGER DEFAULT 15,
    result_json TEXT DEFAULT '{}',
    created_at DATETIME
);
-- 作文档案列表是 "WHERE kind = ? ORDER BY id DESC"：单列 kind 索引命中后还要再排一次，
-- 换成 (kind, id DESC) 让过滤与排序走同一条索引。旧名先删，免得两套索引长期并存互相追平。
DROP INDEX IF EXISTS idx_essay_records_kind;
CREATE INDEX IF NOT EXISTS idx_essay_records_kind_id ON essay_records(kind, id DESC);
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
    "images",
    "passage_text",
    "passage_translation",
    "english_sentences",
    "english_phrases",
    "english_words",
    "english_questions",
)

MISTAKE_FIELD_KEYS = {
    "knowledge_tags": "knowledge_tags_text",
    "answer_aliases": "answer_aliases_text",
    "images": "images_text",
    "english_sentences": "english_sentences_text",
    "english_phrases": "english_phrases_text",
    "english_words": "english_words_text",
    "english_questions": "english_questions_text",
}
