"""首次启动时的演示数据。"""

import sqlite3

from app.services.formula_defaults import DEFAULT_FORMULAS
from app.services.quadratic_form_defaults import QUADRATIC_FORM_NOTES


def seed_subject_profiles(conn: sqlite3.Connection) -> None:
    """写入四个科目的默认复习档案（已存在则不重复写入）。"""
    subject_profiles = [
        (
            1,
            '["知识点理解","概念辨析","总结归纳","背诵记忆","时政热点","真题考法"]',
            "政治复习以理解带背诵：先吃透概念与原理，再用关键词串联框架；"
            "辨析题要能说出易混概念的区别；时政常和知识点结合命题。",
        ),
        (
            2,
            '["单词积累","词汇辨析","长难句","阅读理解","翻译","语法","真题考法"]',
            "英语复习以真题为纲：阅读要复盘定位与同义替换，翻译要拆结构再组句，"
            "词汇在语境中记，语法围绕长难句展开。",
        ),
        (
            3,
            '["概念理解","公式推导","计算能力","证明方法","综合应用","真题考法"]',
            "数学按高等数学、线性代数分科整理：自己动手推导每一步，"
            "错题不仅要答案，更要写出卡住的步骤；一题多解能显著提升熟练度，"
            "计算错误要单独记录。",
        ),
        (
            4,
            '["数据结构","计算机组成原理","操作系统","计算机网络","跨科目联动","真题考法"]',
            "408 四门课知识点会互相联动，例如操作系统页表与组成原理的地址转换、"
            "网络分层与操作系统协议栈；复习时用知识图谱把跨科关系标出来。",
        ),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO subject_profiles (subject_id, focus_areas, review_tips) "
        "VALUES (?, ?, ?)",
        subject_profiles,
    )


def seed_formula_data(conn: sqlite3.Connection) -> None:
    """首次为公式库写入常用公式表。"""
    seeded = conn.execute(
        "SELECT 1 FROM app_meta WHERE key = 'formula_seeded'"
    ).fetchone()
    if seeded is not None:
        return

    formulas = DEFAULT_FORMULAS
    conn.executemany(
        "INSERT OR IGNORE INTO formula_items (category, title, content) "
        "VALUES (?, ?, ?)",
        formulas,
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('formula_seeded', '1')"
    )


def seed_database(conn: sqlite3.Connection) -> None:
    """写入科目、二级科目、知识点和演示错题。"""
    subjects = [
        (1, "政治"),
        (2, "英语二"),
        (3, "数学二"),
        (4, "408计算机基础综合"),
    ]
    conn.executemany("INSERT INTO subjects (id, name) VALUES (?, ?)", subjects)

    sub_subjects = [
        (1, 4, "数据结构"),
        (2, 4, "计算机组成原理"),
        (3, 4, "计算机网络"),
        (4, 4, "操作系统"),
        (5, 3, "高等数学"),
        (6, 3, "线性代数"),
        (7, 2, "完形填空"),
        (8, 2, "阅读理解"),
        (9, 2, "新题型"),
        (10, 2, "翻译"),
        (11, 2, "写作"),
        (12, 2, "词汇与语法"),
    ]
    conn.executemany(
        "INSERT INTO sub_subjects (id, subject_id, name) VALUES (?, ?, ?)",
        sub_subjects,
    )

    seed_subject_profiles(conn)
    seed_formula_data(conn)

    knowledge_rows = [
        (
            "二叉树遍历",
            4,
            1,
            "前序遍历：根左右；中序遍历：左根右；后序遍历：左右根。"
            "递归实现代码简洁，非递归遍历常用栈模拟，层次遍历使用队列。",
        ),
        (
            "虚拟内存",
            4,
            4,
            "虚拟内存将逻辑地址空间与物理内存分离，支持按需调页、页面置换"
            "（LRU、FIFO、Clock 等），并可通过页表完成地址转换。",
        ),
        (
            "定语从句",
            2,
            None,
            "定语从句由关系代词或关系副词引导，修饰名词或代词；"
            "关系词在从句中充当主语、宾语、状语等成分，需结合先行词判断。",
        ),
        (
            "马原辩证法",
            1,
            None,
            "唯物辩证法三大规律：对立统一规律、量变质变规律、否定之否定规律。"
            "注意区分辩证法与形而上学，以及联系、发展、矛盾等核心概念。",
        ),
    ]
    conn.executemany(
        "INSERT INTO knowledge_base (tag_name, subject_id, sub_subject_id, summary) "
        "VALUES (?, ?, ?, ?)",
        knowledge_rows,
    )

    # 数学二·线性代数：二次型细分知识点（tag_name 唯一，重复跳过）
    conn.executemany(
        "INSERT OR IGNORE INTO knowledge_base "
        "(tag_name, subject_id, sub_subject_id, summary, related_tags) "
        "VALUES (?, 3, 6, ?, ?)",
        [
            (note["tag"], note["summary"], note.get("related", ""))
            for note in QUADRATIC_FORM_NOTES
        ],
    )

    mistakes = [
        (
            4,
            1,
            "已知一棵二叉树的中序遍历序列为 D B E A F C，后序遍历序列为 D E B F C A，"
            "则该二叉树的先序遍历序列是？",
            "A B D E C F",
            "A B C D E F",
            "A B E D C F",
            "A D B E F C",
            "A",
            "后序遍历最后一个结点是根结点 A；再用中序遍历将左右子树分开，"
            "递归还原可得先序遍历为 A B D E C F。",
            3,
            "二叉树遍历,递归",
            "递归还原",
            "2025 年真题改编",
            "real_exam",
            "2025",
            "",
        ),
        (
            2,
            None,
            "The reason ______ he was late for the meeting is still unknown.",
            "why",
            "which",
            "that",
            "where",
            "A",
            "先行词 reason 后常用关系副词 why 引导定语从句，说明原因；"
            "which/that 在从句中作主语或宾语，此处不符合。",
            2,
            "定语从句",
            "语法辨析",
            "英语二真题",
            "real_exam",
            "",
            "",
        ),
        (
            1,
            None,
            "下列选项中，体现量变质变规律的是？",
            "千里之行，始于足下",
            "城门失火，殃及池鱼",
            "一把钥匙开一把锁",
            "牵一发而动全身",
            "A",
            "“千里之行，始于足下”强调量的积累达到一定程度会引起质变；"
            "B 体现联系，C 体现矛盾特殊性，D 体现整体与部分。",
            1,
            "马原辩证法",
            "概念辨析",
            "政治模拟题",
            "mock",
            "",
            "政治模拟题",
        ),
    ]
    conn.executemany(
        "INSERT INTO mistakes (subject_id, sub_subject_id, question, option_a, "
        "option_b, option_c, option_d, correct_answer, analysis, difficulty, "
        "knowledge_tags, approach, source, source_type, source_year, source_name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        mistakes,
    )
