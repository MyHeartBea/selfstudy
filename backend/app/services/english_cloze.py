"""完形/七选五本地结构化：答案键解析、题型检测、按空拆题、选项解析。

为什么本地做（2026-10 完形录入翻车的直接教训）：答案表（`1. B 2. B 3. A …`）
与空位编号是纯格式化文本，正则即可 100% 稳定解析；交给 AI 反而会把答案序列
编成一道"题"的题干（实测生成"1. B 2. B 3. A…"题干的垃圾错题）。七选五同理
（实测 AI 把一整道七选五出成 1 道题、选项还被截断）。所以：
- 答案键、空位、每空的题干/选项与答案 —— 本地解析（保证不编造、不截断）；
- 逐句翻译、词汇短语、逐题解析 —— 仍走 AI（内容不减）。

本模块全部为纯函数，不发任何网络请求、不依赖 DB，可独立单测。
"""

import re
from typing import Dict, List, Tuple

# 题号.字母 对：`1. B` / `2、D` / `3) A` / `(4) C` / `5．B`。
# 两个防误判护栏：数字前不能紧邻字母/数字（排除 "2016. B" 里吃出 "16. B"）；
# 字母后不能紧跟字母（排除 "1. Bad" 把 B 吃走）。
_PAIR_RE = re.compile(r"(?<![\w])(\d{1,2})\s*[.、．:：)）]\s*\(?([A-Ga-g])\)?(?![A-Za-z])")

# 完形标题特征（英语试卷 Section I Use of English / 完形填空）
_CLOZE_TITLE_RE = re.compile(r"use\s+of\s+english|cloze|完形", re.I)

# 空位标记（带编号）：__1__ / _1_ / (1)____ / ____(1) / 1____ / ____1
_BLANK_PATTERNS = tuple(
    re.compile(p)
    for p in (
        r"_{2,}\s*(\d{1,2})\s*_{2,}",  # __1__
        r"\(\s*(\d{1,2})\s*\)\s*_{2,}",  # (1)____
        r"_{2,}\s*\(\s*(\d{1,2})\s*\)",  # ____(1)
        r"(?<![\w])(\d{1,2})_{2,}",  # 1____
        r"_{2,}(\d{1,2})(?![\w_])",  # ____1
    )
)
_PLAIN_BLANK_RE = re.compile(r"_{3,}")  # 无编号空位 ____

MIN_NUMBERED_BLANKS = 8  # ≥8 个编号空位直接判完形（七选五只有 5 空，走 detect_gapped）
MIN_PLAIN_BLANKS = 12  # 提字丢了编号时，靠无编号空位密度兜底
MAX_BLANK_NO = 60  # 题号上限（完形 1-20；七选五英语二 36-40、英语一 41-45）
GAPPED_MIN_BLANKS = 3  # 七选五编号空位下限（标准 5 空，容错 3-7）
GAPPED_MAX_BLANKS = 7  # 七选五编号空位上限（≥8 是完形）


def _find_pairs(text: str) -> List[Tuple[int, int, int, str]]:
    """返回 [(题号, 字母(大写), 起始, 结束)]，按出现顺序。"""
    out: List[Tuple[int, int, int, str]] = []
    for m in _PAIR_RE.finditer(str(text or "")):
        no = int(m.group(1))
        if 1 <= no <= MAX_BLANK_NO:
            out.append((no, m.group(2).upper(), m.start(), m.end()))
    return out


def parse_answer_key(text: str) -> Dict[int, str]:
    """从文本解析答案键 {题号: 字母}。

    至少要凑够 3 对才算答案键（避免正文里偶然的 "Chapter 3. A" 被误判）；
    同题号重复出现时取先出现的（答案表不会重复，重复说明解析有噪声）。
    """
    key: Dict[int, str] = {}
    for no, letter, _, _ in _find_pairs(text):
        if no not in key:
            key[no] = letter
    return key if len(key) >= 3 else {}


def looks_like_answer_key(text: str, min_pairs: int = 5) -> bool:
    """整段文本是否"只是答案序列"（防呆判据）。

    判据：≥ min_pairs 对题号.字母，且剔除这些对之后剩余正文极短（答案表
    可能带页眉/年份等少量噪声）。阅读原文混着答案不会命中（剩余正文长）。
    """
    raw = str(text or "")
    pairs = _find_pairs(raw)
    if len(pairs) < min_pairs:
        return False
    remainder = _PAIR_RE.sub(" ", raw)
    remainder = re.sub(r"[\s\d.、．:：)）(\[\]-]+", "", remainder)
    return len(remainder) <= 60


def is_answer_sequence_text(text: str) -> bool:
    """单条"题干"是否其实是答案序列（逐题结果的末端防呆）。"""
    raw = str(text or "").strip()
    if not raw:
        return False
    pairs = _find_pairs(raw)
    if len(pairs) < 3:
        return False
    remainder = _PAIR_RE.sub(" ", raw)
    remainder = re.sub(r"[\s\d.、．:：)）(\[\]-]+", "", remainder)
    return len(remainder) <= max(30, int(len(raw) * 0.2))


def detect_cloze(text: str) -> bool:
    """完形篇章检测：标题特征、或编号空位足够多、或无编号空位密度高。

    阈值刻意高：3-7 个编号空位是七选五（detect_gapped），阅读原文
    没有空位 —— 只有真正的完形（1-20 空）才进本地拆题。
    """
    raw = str(text or "")
    if _CLOZE_TITLE_RE.search(raw[:600]):
        return True
    numbered = find_numbered_blanks(raw)
    if len(numbered) >= MIN_NUMBERED_BLANKS:
        return True
    plain = len(_PLAIN_BLANK_RE.findall(raw))
    if len(numbered) >= 5 and plain >= len(numbered):
        return True
    return plain >= MIN_PLAIN_BLANKS


def detect_gapped(text: str) -> bool:
    """七选五检测：正文含 3-7 个编号空位（≥8 归完形，阅读原文没有空位）。

    只认**编号**空位：七选五的空位编号（36-40 / 41-45）是与答案键对齐的唯一锚点。
    """
    raw = str(text or "")
    if _CLOZE_TITLE_RE.search(raw[:600]):
        return False  # 标题判完形，别按七选五拆
    numbered = find_numbered_blanks(raw)
    return GAPPED_MIN_BLANKS <= len(numbered) <= GAPPED_MAX_BLANKS


def find_numbered_blanks(text: str) -> List[dict]:
    """找带编号的空位，返回 [{no, start, end}] 按出现顺序。

    五种写法各自扫一遍后按位置去重（同一空位可能同时命中两个模式）。
    编号 < 3 个时不返回（编号不可信，调用方退回无编号顺序拆题）。
    """
    raw = str(text or "")
    hits: List[Tuple[int, int, int]] = []  # (start, end, no)
    for pat in _BLANK_PATTERNS:
        for m in pat.finditer(raw):
            no = int(m.group(1))
            if 1 <= no <= MAX_BLANK_NO:
                hits.append((m.start(), m.end(), no))
    hits.sort()
    merged: List[Tuple[int, int, int]] = []
    for start, end, no in hits:
        if merged and start < merged[-1][1]:
            continue  # 与前一个命中重叠（同一空位的另一种写法）
        merged.append((start, end, no))
    if len(merged) < 3:
        return []
    return [{"no": no, "start": s, "end": e} for s, e, no in merged]


def _sentence_spans(text: str) -> List[Tuple[int, int]]:
    """按句末标点/换行切分的句子区间（空位标记本身不含句末标点，不会跨句）。"""
    spans: List[Tuple[int, int]] = []
    bounds = [0]
    for m in re.finditer(r"(?<=[.!?])\s+|\n+", text):
        bounds.append(m.end())
    bounds.append(len(text))
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        piece = text[start:end]
        if piece.strip():
            # 收紧到非空白内容
            lead = len(piece) - len(piece.lstrip())
            trail = len(piece) - len(piece.rstrip())
            spans.append((start + lead, end - trail))
    return spans


def build_cloze_questions(passage_text: str, answer_key: Dict[int, str]) -> List[dict]:
    """按空拆题：每空一道题（题干=空位所在完整句子，空位写成 ____）。

    - 空位带编号 → 按编号对答案；编号不可用 → 按出现顺序编号（1,2,3…）。
    - 同句含多个空位：目标空写 ____，其余空保留原编号标记（作答语境不丢）。
    - 选项来自图片里逐空的候选词（parse_cloze_options），没有就留空 —— 严禁编造。
    """
    raw = str(passage_text or "")
    blanks = find_numbered_blanks(raw)
    if not blanks:
        plain = list(_PLAIN_BLANK_RE.finditer(raw))
        if len(plain) < 5:
            return []
        blanks = [{"no": i + 1, "start": m.start(), "end": m.end()} for i, m in enumerate(plain)]
    spans = _sentence_spans(raw)
    questions: List[dict] = []
    for idx, b in enumerate(blanks):
        sent = next(
            (s for s in spans if s[0] <= b["start"] and b["end"] <= s[1]),
            None,
        )
        if sent is None:
            # 空位落在切句盲区（如整段无句末标点）：以空位前后各 60 字符兜底
            sent = (max(0, b["start"] - 60), min(len(raw), b["end"] + 60))
        stem = raw[sent[0] : sent[1]]
        rel = b["start"] - sent[0]
        stem = stem[:rel] + "____" + stem[rel + (b["end"] - b["start"]) :]
        stem = re.sub(r"\s*\n\s*", " ", stem).strip()
        answer = answer_key.get(b["no"]) or answer_key.get(idx + 1, "")
        questions.append(
            {
                "question": stem,
                "question_type": "choice",
                "option_a": "",
                "option_b": "",
                "option_c": "",
                "option_d": "",
                "option_e": "",
                "option_f": "",
                "option_g": "",
                "correct_answer": answer,
                "difficulty": 3,
            }
        )
    return questions


# 逐空选项行：`1. [A] however [B] though [C] although [D] while`
# 或 `1) A) idea B) ...`；字母标记支持 [A] / (A) / A) 三种写法。
_OPTION_MARK_RE = re.compile(
    r"(?:\[\s*([A-Da-d])\s*\]|\(\s*([A-Da-d])\s*\)|(?<![A-Za-z])([A-Da-d])\s*[)）])"
)
_OPTION_LINE_RE = re.compile(r"^\s*(\d{1,2})\s*[.、．:：)）]?\s*(.+)$")


def parse_cloze_options(quiz_text: str) -> Dict[int, Dict[str, str]]:
    """从题目区解析逐空选项 {题号: {A: 文本, B: …}}。尽力而为，失败返回空。"""
    result: Dict[int, Dict[str, str]] = {}
    for line in str(quiz_text or "").split("\n"):
        lm = _OPTION_LINE_RE.match(line.strip())
        if not lm:
            continue
        no = int(lm.group(1))
        if not 1 <= no <= MAX_BLANK_NO:
            continue
        rest = lm.group(2)
        marks = [
            (m.start(), m.end(), (m.group(1) or m.group(2) or m.group(3)).upper())
            for m in _OPTION_MARK_RE.finditer(rest)
        ]
        # 至少 3 个标记且字母严格递增（A<B<C…）才认，防止正文里零散括号字母干扰
        if len(marks) < 3:
            continue
        letters = [letter for _, _, letter in marks]
        if letters != sorted(set(letters)):
            continue
        opts: Dict[str, str] = {}
        for i, (_, end, letter) in enumerate(marks):
            seg_end = marks[i + 1][0] if i + 1 < len(marks) else len(rest)
            text = re.sub(r"\s+", " ", rest[end:seg_end]).strip(" \t,;，；")
            if text:
                opts[letter] = text
        if len(opts) >= 3 and no not in result:
            result[no] = opts
    return result


def attach_options(questions: List[dict], options: Dict[int, Dict[str, str]]) -> List[dict]:
    """把本地解析的逐空选项填进按空拆出的题目（按题号对齐，尽力而为）。"""
    if not options:
        return questions
    for idx, q in enumerate(questions):
        opts = options.get(idx + 1)
        if not opts:
            continue
        for letter in "ABCDEFG":
            q["option_" + letter.lower()] = opts.get(letter, "")
    return questions


# ---- 七选五（新题型）：共享 A-G 七个完整句子选项 ----

# 选项行：`A. You are not alone` / `[A] You are not alone` / `(A) You are not alone`。
# 字母后必须有分隔符（闭括号或句读），防止把以 "A "/"B " 开头的普通正文句子吃进来。
_SENT_OPTION_LINE_RE = re.compile(
    r"^\s*(?:[\[（(]\s*)?([A-Ga-g])\s*(?:[\]）)]|[.、．:：)）])\s*(.+)$"
)


def parse_sentence_options(quiz_text: str) -> Dict[str, str]:
    """解析七选五的共享选项区 {字母: 完整句子}（选项区通常 5-7 行，每行一个字母）。

    句子必须**原样照抄**（完整不截断）——AI 逐题转写实测会把长选项截断
    （"Don't fear responsibility for your l"），所以选项走本地解析。
    文本至少要含两个连续字母（排除 "A. 2023" 这类页码噪声）；解析不足
    3 个选项返回空 dict（调用方按缺料降级，不硬凑）。
    """
    opts: Dict[str, str] = {}
    for line in str(quiz_text or "").split("\n"):
        m = _SENT_OPTION_LINE_RE.match(line.strip())
        if not m:
            continue
        text = re.sub(r"\s+", " ", m.group(2)).strip()
        if not re.search(r"[A-Za-z]{2}", text):
            continue
        letter = m.group(1).upper()
        if letter not in opts:
            opts[letter] = text
    return opts if len(opts) >= 3 else {}


def build_gapped_questions(
    passage_text: str,
    answer_key: Dict[int, str],
    options: Dict[str, str],
) -> List[dict]:
    """按空拆七选五：每空一道题，A-G 七个完整句子选项原样共享。

    题干 = 该空所在句 + 前后各一句（上下文定位，与 AGENTS 拆题规则一致），
    目标空写成 ____，其余空保留原编号标记。答案按空位编号对答案键
    （英语二 36-40 / 英语一 41-45 都直接命中）。
    """
    raw = str(passage_text or "")
    blanks = find_numbered_blanks(raw)
    if not (GAPPED_MIN_BLANKS <= len(blanks) <= GAPPED_MAX_BLANKS):
        return []
    spans = _sentence_spans(raw)
    questions: List[dict] = []
    for idx, b in enumerate(blanks):
        cur_i = next(
            (i for i, s in enumerate(spans) if s[0] <= b["start"] and b["end"] <= s[1]),
            None,
        )
        if cur_i is None:
            # 空位落在切句盲区（整段无句末标点）：只取空位前后各 60 字符
            window = (max(0, b["start"] - 60), min(len(raw), b["end"] + 60))
        else:
            # 题干 = 该空所在句 + 前后各一句（AGENTS 七选五拆题规则）
            lo = cur_i - 1 if cur_i > 0 else cur_i
            hi = cur_i + 2 if cur_i + 1 < len(spans) else cur_i + 1
            window = (spans[lo][0], spans[hi - 1][1])
        stem = raw[window[0] : window[1]]
        rel = b["start"] - window[0]
        stem = stem[:rel] + "____" + stem[rel + (b["end"] - b["start"]) :]
        stem = re.sub(r"\s*\n\s*", " ", stem).strip()
        # 空位编号直接对答案键；键写成 1-5 紧凑序号时按出现顺序兜底
        answer = answer_key.get(b["no"]) or answer_key.get(idx + 1, "")
        q = {
            "question": stem,
            "question_type": "choice",
            "correct_answer": answer or "",
            "difficulty": 3,
        }
        for letter in "ABCDEFG":
            q["option_" + letter.lower()] = options.get(letter, "")
        questions.append(q)
    return questions
