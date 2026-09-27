"""真题库扫描：科目/年份/文件角色识别与目录扫描（自 exam_paper_service 拆出）。

只做"盘点"：`scan_folder` 把 PAPERS_DIR 里的文件整理成可导入候选；
文本提取在 `exam_paper_extract`，AI 拆题流水线在 `exam_paper_service`。
本模块不 import AI —— 纯文件系统与文件名解析。
"""

import re
from pathlib import Path
from typing import List

from app.config import PROJECT_ROOT, settings

# 科目识别：按 真题库内的路径/文件名 关键词（顺序敏感：408 先于数学）
# 数学要覆盖「数二/数一/数三」这类简写，否则 `2011年数二真题答案速查.pdf` 会识别为空
_SUBJECT_RULES = [
    ("英语二", ("英语二", "英语（二）", "英语")),
    ("计算机408", ("408", "计算机")),
    ("数学二", ("数学二", "数学（二）", "数学", "数二", "数一", "数三", "数学一", "数学三")),
    ("政治", ("政治",)),
]

# 数学一/二/三 不能混：命中「数学（一）/数学一」等就排除在数学二之外
# 注意要覆盖全角括号写法「数学（二）」，否则会一个规则都不命中
_MATH_ONE_KEYS = ("数学（一）", "数学(一)", "数学一", "数一", "数学 一")
_MATH_TWO_KEYS = ("数学（二）", "数学(二)", "数学二", "数二", "数学 二")
_MATH_THREE_KEYS = ("数学（三）", "数学(三)", "数学三", "数三", "数学 三")

# 文件角色判定关键词
# 「答案速查」是明确答案册；「解析/详解」可能是【题+答案合卷】，需要单独判定
_ANSWER_KEYS = ("答案速查", "参考答案", "答案", "解析", "详解")
# 「合卷」特征：文件名同时出现"真题"与"解析/详解"，说明题目和答案在同一份文件里
_MIXED_KEYS = ("解析", "详解")
_PAPER_STEMS = ("真题", "试题", "试卷", "统考")


def papers_root() -> Path:
    return Path(settings.PAPERS_DIR or str(PROJECT_ROOT / "真题"))


def _classify_math(text: str) -> str:
    """数学卷细分：数学一/二/三 互不混淆（原实现把「2024年数学（一）」当成数学二）。"""
    if any(k in text for k in _MATH_THREE_KEYS):
        return "数学三"
    if any(k in text for k in _MATH_ONE_KEYS):
        return "数学一"
    if any(k in text for k in _MATH_TWO_KEYS):
        return "数学二"
    # 只写了「数学」没写几：按数学二处理（本库主要用数二）
    return "数学二"


def guess_subject(text: str) -> str:
    for subject, keys in _SUBJECT_RULES:
        if any(k in text for k in keys):
            if subject == "数学二":
                return _classify_math(text)
            return subject
    return ""


def guess_year(text: str) -> str:
    """识别年份。优先 4 位年份；否则识别 `26考研`/`25数二` 这类两位年份缩写。"""
    text = str(text or "")
    m = re.search(r"(19|20)\d{2}", text)
    if m:
        return m.group(0)
    # 两位年份：26考研 / 25数二 / 24政治 / 23年
    m = re.search(r"(?<!\d)([0123]\d)\s*(?=考研|数[一二三]|英语|政治|年)", text)
    if m:
        two = int(m.group(1))
        return str(2000 + two) if two <= 40 else str(1900 + two)
    return ""


def _split_compact_year(text: str) -> str:
    """把 `2010-2024` / `2005-2021` 这种区间名里的年份取**开头那个**（用于整体资料文件名）。

    这类文件名通常属于合集，取区间起始年没有意义，故只在没有其它年份时兜底。
    """
    m = re.search(r"(19|20)\d{2}", text)
    return m.group(0) if m else ""


def classify_file(name: str) -> str:
    """判定文件角色：question / answer_key / mixed / other。

    - mixed：**题+答案合卷**（`真题解析`、`真题及参考答案`、`真题+详解`）。以前这类被
      `_ANSWER_KEYS` 一律当成"纯答卷"，于是既当不成试卷也配不到答案，150 份候选里
      52 份因此变成孤儿。
    - answer_key：只是答案/解析册（答案速查、参考答案、选择题解析），不含题面
    - question：纯试卷（真题/试题/试卷/统考，且不含答案解析字样）
    - other：无法判断（答题卡等）

    判定顺序（先具体后笼统，避免"真题答案速查"被当成合卷）：
    1. 含「答案速查」→ 速查答案册；
    2. 含真题/试题/试卷 且 含解析/详解/答案 → 合卷；
    3. 含「参考答案」→ 答案册；
    4. 含解析/详解/答案 → 答案册；
    5. 含真题/试题/试卷 → 纯试卷；
    6. 其它 → other。
    """
    has_stem = any(k in name for k in _PAPER_STEMS)
    has_solution = any(k in name for k in _MIXED_KEYS)
    has_answer = any(k in name for k in _ANSWER_KEYS)

    if "答案速查" in name:
        return "answer_key"
    if has_stem and (has_solution or has_answer):
        return "mixed"
    if "参考答案" in name:
        return "answer_key"
    if has_solution or has_answer:
        return "answer_key"
    if has_stem:
        return "question"
    return "other"


def scan_folder() -> List[dict]:
    """扫描真题根目录，返回**按科目+年份去重后**的候选试卷清单。

    相比旧实现的三处修正：
    1. **角色判定**：区分 纯试卷/答案册/**题+答案合卷**。合卷自己就带答案，
       不再被判成"纯答卷"而变成孤儿（实测 81 份未配对里 52 份是合卷）；
    2. **去重合并**：同一(科目,年份)的「真题」「真题解析」「答案速查」合并成一条候选，
       不再出现英语二某年 3~5 份重复候选、分不清该导哪个；
    3. **年份/科目识别**：补 `26考研→2026` 两位年，数学一/三 不再并入数学二。

    每条候选额外给出 `sources`（该年份涉及的文件与角色）与 `mixed`（是否合卷），
    供前端展示与人工挑选。
    """
    root = papers_root()
    if not root.is_dir():
        return []

    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".docx", ".pdf"):
            continue
        if path.name.startswith("~$"):
            continue
        rel = str(path.relative_to(root))
        subject = guess_subject(rel)
        year = guess_year(path.name) or guess_year(str(path.parent.name))
        files.append(
            {
                "rel_path": rel,
                "name": path.name,
                "subject": subject,
                "year": year,
                "kind": classify_file(path.name),
                "size_kb": max(1, round(path.stat().st_size / 1024)),
            }
        )

    # 按 (科目, 年份) 归组；年份/科目未识别的单独成组，避免互相污染
    groups: dict = {}
    for f in files:
        if f["kind"] == "other":
            continue
        key = (f["subject"], f["year"])
        groups.setdefault(key, []).append(f)

    results = []
    for (subject, year), items in groups.items():
        questions = [f for f in items if f["kind"] == "question"]
        mixed = [f for f in items if f["kind"] == "mixed"]
        answers = [f for f in items if f["kind"] == "answer_key"]

        # 试卷来源优先级：纯试卷（更像干净题干）> 合卷
        pool = questions or mixed
        if not pool:
            continue
        pool.sort(key=lambda f: (f["kind"] != "question", f["size_kb"]))
        primary = pool[0]

        # 答案来源：明确答案册优先（小文件速查版最干净），其次合卷（合卷里题面会干扰提取）
        answer_keys = answers
        mixed_only = [f for f in mixed if f["rel_path"] != primary["rel_path"]]
        ans_pool = answer_keys or mixed_only
        ans_pool = [f for f in ans_pool if f["rel_path"] != primary["rel_path"]]
        ans_pool.sort(
            key=lambda f: (
                f["kind"] != "answer_key",
                not f["name"].startswith("答案速查"),
                f["size_kb"],
            )
        )
        answer_path = ans_pool[0]["rel_path"] if ans_pool else ""

        results.append(
            {
                "rel_path": primary["rel_path"],
                "name": primary["name"],
                "subject": subject,
                "year": year,
                "kind": "paper",
                "mixed": primary["kind"] == "mixed",
                "size_kb": primary["size_kb"],
                "answer_path": answer_path,
                "answer_kind": ans_pool[0]["kind"] if ans_pool else "",
                "sources": [
                    {"rel_path": f["rel_path"], "kind": f["kind"], "size_kb": f["size_kb"]}
                    for f in sorted(items, key=lambda x: x["rel_path"])
                ],
            }
        )

    results.sort(key=lambda r: (r["subject"], r["year"] == "", r["year"]))
    return results
