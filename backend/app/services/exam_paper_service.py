"""真题库：扫描历年真题文件、提取文本、AI 拆题入库（后台流水线）。"""

import json
import queue
import re
import threading
from pathlib import Path
from typing import List

from app.config import PROJECT_ROOT, settings
from app.metrics import mask_secret
from app.services import ai_service
from app.services.ai_service import AiRequestError

PAPER_STATUSES = ("pending", "extracting", "structuring", "done", "error")

_IMAGE_ROOT = PROJECT_ROOT / "data" / "images" / "exam_papers"
_DIAGRAM_RE = re.compile(r"\[[^\]]*(?:图|示|表|树)[^\]]*\]")
_FIGURE_HINTS = (
    "页表",
    "如下表",
    "如表",
    "表格如下",
    "如图所示",
    "如下图",
    "示意图",
    "下图",
    "如右图",
)


# —— 扫描与文本提取已拆分到独立模块（2026-09-27），这里 re-export 保持
# `exam_paper_service.xxx` / `eps.xxx` 的既有调用面不变（routers 与 tests 都按旧名引用）。 ——

from app.services.exam_paper_extract import (  # noqa: E402,F401
    _CHUNK_CHARS,
    _is_math,
    _pdf_ocr,
    _pdf_ocr_pages,
    _pdf_page_vision,
    _pdf_pages,
    _pdf_pages_render,
    _pdf_text_layer,
    _pdf_text_usable,
    _probe_file,
    estimate_import,
    extract_text,
)
from app.services.exam_paper_scan import (  # noqa: E402,F401
    _classify_math,
    _split_compact_year,
    classify_file,
    guess_subject,
    guess_year,
    papers_root,
    scan_folder,
)


def _paper_img_dir(paper_id: int) -> Path:
    d = _IMAGE_ROOT / str(paper_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def remove_paper_images(paper_id: int) -> int:
    """删卷后清理该卷的图示页原图（整目录移除，文件不在库里、级联删不掉）。"""
    import shutil

    d = _IMAGE_ROOT / str(paper_id)
    if not d.is_dir():
        return 0
    shutil.rmtree(d, ignore_errors=True)
    return 1


# 真题科目 → 错题本科目（subjects 是用户数据，按关键词 LIKE 匹配，匹配不到就拒绝）
_SUBJECT_TO_MISTAKE = (
    ("408", "408"),
    ("计算机", "计算机"),
    ("数学", "数学"),
    ("英语", "英语"),
    ("政治", "政治"),
)


def set_question_answer(conn, paper_id: int, question_id: int, answer: str):
    """人工修正客观题答案（正则没配上/配错了，页面上直接改）。

    choice 只收 A-D 或空串；fill 收任意文本（数值/表达式答案）；solution 不存答案。
    返回 (question_dict, None) 或 (None, 错误消息)。
    """
    answer = str(answer or "").strip()
    row = conn.execute(
        "SELECT * FROM exam_questions WHERE id = ? AND paper_id = ?",
        (question_id, paper_id),
    ).fetchone()
    if row is None:
        return None, "题目不存在"
    q = dict(row)
    if q["question_type"] == "choice":
        answer = answer.upper()
        if answer and not re.fullmatch(r"[A-G]", answer):
            return None, "选择题答案只能是 A 到 G（含七选五的 E/F/G）或留空"
    elif q["question_type"] == "solution":
        return None, "解答题没有标准答案字段"
    else:
        answer = answer[:200]
    conn.execute(
        "UPDATE exam_questions SET correct_answer = ? WHERE id = ?",
        (answer, question_id),
    )
    conn.commit()
    q["correct_answer"] = answer
    return q, None


def question_to_mistake(conn, paper_id: int, question_id: int):
    """把一道真题转入错题本（单题手动入口；模考交卷的自动入库走前端）。

    同卷同题干只转一次：已存在（source_name + 题干相同）时直接返回那条，不重复入库。
    返回 (mistake_dict, None) 或 (None, 错误消息)。
    """
    from app.services import mistake_service

    paper = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
    if paper is None:
        return None, "真题不存在"
    paper = dict(paper)
    row = conn.execute(
        "SELECT * FROM exam_questions WHERE id = ? AND paper_id = ?",
        (question_id, paper_id),
    ).fetchone()
    if row is None:
        return None, "题目不存在"
    q = dict(row)
    qtype = q["question_type"] if q["question_type"] in ("choice", "fill", "solution") else "choice"

    subject_row = None
    for kw, _ in _SUBJECT_TO_MISTAKE:
        if kw in (paper["subject"] or ""):
            subject_row = conn.execute(
                "SELECT id FROM subjects WHERE name LIKE ? LIMIT 1", (f"%{kw}%",)
            ).fetchone()
            if subject_row:
                break
    if subject_row is None:
        return None, f"错题本科目里找不到「{paper['subject'] or '未知科目'}」对应的科目，请先建科目"

    if qtype == "choice" and not (q["correct_answer"] or "").strip():
        return None, "这题还没有答案，先「补答案」再转入错题本"

    existing = conn.execute(
        "SELECT * FROM mistakes WHERE source_name = ? AND question = ?",
        (paper["title"] or "", q["question"] or ""),
    ).fetchone()
    if existing:
        return mistake_service.mistake_to_dict(existing), None

    body = {
        "subject_id": subject_row["id"],
        "question_type": qtype,
        "question": q["question"] or "",
        "option_a": q["option_a"] or "",
        "option_b": q["option_b"] or "",
        "option_c": q["option_c"] or "",
        "option_d": q["option_d"] or "",
        "option_e": q.get("option_e") or "",
        "option_f": q.get("option_f") or "",
        "option_g": q.get("option_g") or "",
        "correct_answer": q["correct_answer"] or "",
        "analysis": q["analysis"] or f"来自真题《{paper['title']}》，解析待整理。",
        "difficulty_points": q["section"] or f"真题 · {paper['title']}",
        "difficulty": 3,
        "knowledge_tags": [],
        "source_type": "real_exam",
        "source_year": paper["year"] or "",
        "source_name": paper["title"] or "",
        "images": [],
    }
    created, errors = mistake_service.create_mistake(conn, body)
    if errors:
        return None, "；".join(errors)
    return created, None


def _has_diagram_option(q: dict) -> bool:
    """题目是否含图示/表格，需要保存该页原图。

    选项为 [图] 类占位，或题干/段落明确引用 页表/表格/如图所示 等，都判为有图。
    """
    opts = " ".join(q.get(k) or "" for k in ("option_a", "option_b", "option_c", "option_d"))
    if _DIAGRAM_RE.search(opts):
        return True
    qtext = (q.get("question") or "") + " " + (q.get("passage") or "")
    return any(h in qtext for h in _FIGURE_HINTS)


def _page_for_no(no: str, page_items: list) -> int:
    """按题号在逐页提取文本里定位该题所在页（可靠，供图示题存图）。

    匹配「行首 题号 + .（、．）」形式，例如 page 文本里 "46.（8 分）..."。
    **找不到返回 -1**（不是 0）：0 是第 1 页的合法页码，若用 0 表示「未找到」，
    图示题会把无关的第 1 页截图当作该题原图存进库（页面截图会骗人）。
    """
    n = str(no or "").strip()
    if not n.isdigit():
        return -1
    pat = re.compile(r"^[^\S\n]*" + re.escape(n) + r"[.．、]", re.M)
    for i, text, _pil in page_items:
        if pat.search(text or ""):
            return i
    return -1


def _page_diagram_image(paper_id: int, source: Path, page_idx: int, cache: dict, pil=None) -> str:
    """渲染第 page_idx 页为 WebP 图，存 data/images/exam_papers/<pid>/，返回 /images/... URL。

    用于「图示选项」题：把该页截图留存，前端模考/详情可查看原图（同页复用缓存）。
    扫描路径已渲染过该页时，传入 pil 避免重复渲染。
    **page_idx < 0（题号未定位到页）一律不出图**：宁可没有图，也不要拿别的页冒充。
    """
    try:
        key = int(page_idx)
        if key < 0:
            return ""
        if key in cache:
            return cache[key]
        if pil is None:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(source))
            try:
                if key >= len(pdf):
                    return ""
                pil = pdf[key].render(scale=2.4).to_pil()
            finally:
                try:
                    pdf.close()
                except Exception:
                    pass
        from PIL import Image

        pil = pil.convert("RGB")
        if pil.width > 900:
            pil = pil.resize((900, int(pil.height * 900 / pil.width)), Image.LANCZOS)
        out = _paper_img_dir(paper_id) / f"p{key}.webp"
        pil.save(out, format="WEBP", quality=86)
        url = f"/images/exam_papers/{paper_id}/p{key}.webp"
        cache[key] = url
        return url
    except Exception:
        return ""


def _chunk_text(text: str, size: int = _CHUNK_CHARS) -> List[str]:
    chunks = []
    buf = []
    length = 0
    for line in text.splitlines():
        buf.append(line)
        length += len(line) + 1
        if length >= size:
            chunks.append("\n".join(buf))
            buf = []
            length = 0
    if buf:
        chunks.append("\n".join(buf))
    return [c for c in chunks if c.strip()]


def _structure_prompt(subject: str, year: str, chunk: str) -> str:
    return (
        f"你是考研真题整理助手。下面是一份{subject} {year} 年真题试卷的部分文本（可能含考生须知等噪声）。"
        "请把其中的【试题】整理为严格 JSON（不要 Markdown）：\n"
        '{"questions": [{"no": "题号如 1 / 21", "section": "Section I Use of English 等原始节名", '
        '"type": "choice|fill|solution", '
        '"passage": "该题组共用原文（完形填空的文章、阅读理解的全文；只在该题组第一题填写，其他题留空串），无原文则空串", '
        '"question": "题干（选择题为问题句；完形填空为空格所在句；翻译/写作为题目要求全文）", '
        '"option_a": "A 选项", "option_b": "B 选项", "option_c": "C 选项", "option_d": "D 选项", '
        '"option_e": "E 选项（仅英语七选五才有，没有就填空串）", '
        '"option_f": "F 选项（同上）", "option_g": "G 选项（同上）", '
        '"analysis": "解析（若文本中带有）", "page": 0, "has_diagram": false}]}\n'
        "规则：\n"
        "1. type 判断：四选项的选 choice；英译汉/翻译与写作选 solution；其余选 fill。\n"
        "1b. 英语七选五（题干为挖空句、选项给 A-G 七个整句）选 choice，"
        "并把全部七句选项按原文照抄填进 option_a ~ option_g；非七选五的 E/F/G 一律留空串。\n"
        "2. 只整理试题，跳过考生须知、条形码说明、`[[PAGE:n]]` 页码标记等一切噪声。\n"
        "3. choice 必须带四个选项；选项文本保持原样。**任何数学公式/上下标一律用 `\\(...\\)` 包裹**（如 `\\(2^{8}\\)`、`\\(x^{2}\\)`、`\\(O(n)\\)`），禁止裸写 `^`/`_`。\n"
        "4. correct_answer 一律留空串（答案由系统从答案文件另行匹配）。\n"
        "5. 文本不完整（被截断）时，只整理能完整识别的题目，不要编造。\n"
        "6. 文本中的 `[[PAGE:n]]` 是页码标记：请把该题所在的页码 n 填入 `page` 字段（整数，无标记填 0）。\n"
        "7. 若某选项是图示（树、二叉树、流程图、表格、示意图等，无文字内容），该选项字段填 `[图]`，并置 `has_diagram:true`；"
        "选项有真实文字则如实填写，不要用占位符。\n"
        "8. 请紧凑输出：**每个题目对象单独一行**（不要展开成多行美化），务必是合法 JSON。\n\n"
        f"试卷文本：\n{chunk}"
    )


def _answer_letter(segment: str) -> str:
    """从一段答案文本里取选择题答案字母（A-G，含七选五），取不到返回空串。"""
    seg = segment[:60]
    for pat in (
        r"^\s*[（(]\s*([A-Ga-g])\s*[)）]",  # (A) / （A）
        r"^\s*([A-Ga-g])\s*[.、．)）]",  # A. / A、
        r"^\s*([A-Ga-g])(?![A-Za-z])",  # 裸 A
    ):
        m = re.match(pat, seg)
        if m:
            return m.group(1).upper()
    return ""


# 一、选择题:1～10 小题 …（用题干里的题号区间关联答案，而不是答案文件自己的序号）
# 注意分隔符里 `-` 必须放最后或转义，否则会被当成范围（`[～~\-—至]` 里 `~-—` 是范围
# 且不含 `-`，曾导致 "17-22题" 匹配失败）
_QUESTION_RANGE_RE = re.compile(
    r"([一二三四五六七八九十]+)\s*[、.．]?\s*(选择题|填空题|解答题|单项选择|多项选择)"
    r"[^\n\d]{0,30}?(\d{1,2})\s*[～~—至\-–]\s*(\d{1,2})"
)
# 题型关键字 → 统一题型
_SECTION_TYPE = {
    "选择题": "choice",
    "单项选择": "choice",
    "填空题": "fill",
    "多项选择": "choice",
    "解答题": "solution",
}


def _answer_section_map(exam_text: str) -> dict:
    """从**试卷**文本里解析「题号 → 题型」映射。

    答案文件里的 `1～10` 是答案册自己的序号，而卷面题号可能是连续的
    （如选择题 1-10，解答题 17-22），不能按序号硬套；用它来校正题型。
    """
    mapping: dict = {}
    for m in _QUESTION_RANGE_RE.finditer(exam_text or ""):
        qtype = _SECTION_TYPE.get(m.group(2))
        if not qtype:
            continue
        try:
            start, end = int(m.group(3)), int(m.group(4))
        except ValueError:
            continue
        if end < start or end - start > 60:
            continue
        for n in range(start, end + 1):
            mapping.setdefault(str(n), qtype)
    return mapping


def _normalize_answer_text(text: str) -> str:
    """把各种"答案册"写法归一成 `题号:答案` 行，大幅提高答案匹配成功率。

    实测过会失败的两种写法（此前 10 道选择题只配到 1 道，而且配错）：
      1) 连排速查式：`(1)C. (2)B. (3)C. …`        → 1:C 2:B 3:C …
      2) 逐题式：    `1【答案】（A）$a=\\frac{1}{3}$ 考点：泰勒公式`
                    → 1:A（选择题只取字母，后面的解析不参与匹配）
    已经是 `1.A` / `1:A` 这类写法的则原样保留。
    """
    if not text or not text.strip():
        return text

    out_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue

        # 1) 连排速查：(1)C. (2)B. → 拆成多行
        # 阈值取 2：只有两组（如 "(1)C. (2)B."）的小速查段同样要能拆出来；
        # 原实现要求 >=3，导致这类短速查行完全抽不到答案。
        pairs = re.findall(
            r"[（(]?\s*(\d{1,2})\s*[)）.、．:：]\s*[（(]?\s*([A-Ga-g])\s*[)）.、．]?",
            stripped,
        )
        if len(pairs) >= 2 and len(pairs) >= stripped.count("\n") + 2:
            for no, letter in pairs:
                out_lines.append(f"{int(no)}:{letter.upper()}")
            continue

        # 2) 逐题式：1【答案】（A）/ 1.【答案】A / 11【答案】$0<p<2$
        m = re.match(r"^\s*(\d{1,2})\s*[.、．]?\s*[【\[]\s*答案\s*[】\]]\s*(.+)$", stripped)
        if m:
            no, rest = m.group(1), m.group(2).strip()
            letter = _answer_letter(rest)
            # 判断"这是选择题字母答案还是数学表达式"：
            # 只看开头 —— `（A）$a=\frac{1}{3}$` 里的 `$` 出现在字母之后，
            # 不能因此否认它是选择题答案（这是之前 1:A 提取不到的根因）
            is_expression = re.match(r"^\s*(\\|\$\$|[a-zA-Z]\s*[=<>])", rest)
            if letter and not is_expression:
                out_lines.append(f"{int(no)}:{letter}")
            else:
                out_lines.append(f"{int(no)}:{rest}")
            continue

        out_lines.append(line)

    return "\n".join(out_lines)


def _answer_pairs_from_text(text: str, expected: int = 1) -> dict:
    """从答案文本里**确定性地**抽出 {题号: 答案字母}。

    先归一化（连排速查 `(1)C. (2)B.`、逐题 `1【答案】（A）…` 都会变成 `1:A` 行），
    再只取形如 `1:A` / `1:A-` 的行，并按**首次出现**保留。

    返回空 dict 表示"这份材料里取不到成对答案"——调用方据此判定文本层是否真的可用
    （扫描版详解 PDF 的乱码文本层会被 `_pdf_text_usable` 误判为可用，必须靠这个信号兜住）。
    """
    normalized = _normalize_answer_text(text or "")
    pairs: dict = {}
    for m in re.finditer(r"^\s*(\d{1,3})\s*[:：]\s*([A-Ga-g])\b", normalized, re.M):
        pairs.setdefault(str(int(m.group(1))), m.group(2).upper())
    if expected > 0 and len(pairs) < expected:
        return {}
    return pairs


def _answers_prompt(subject: str, year: str, nos: List[str], answer_text: str) -> str:
    return (
        f"以下是{subject} {year} 年真题的答案材料。\n"
        "材料可能已经过预处理，形如 `题号:答案`（如 `3:C`）；也可能格式凌乱。\n\n"
        "任务：为下面列出的每个题号给出正确答案，输出严格 JSON："
        '{"answers": {"题号": "A/B/C/D/E/F/G"}}\n\n'
        "**准确优先，宁缺勿错**（重要）：\n"
        "1. 逐条核对材料里的题号，只填你能在材料中找到明确依据的题；\n"
        "2. 材料里找不到的题号**必须省略**，绝对不要靠推理、经验或“看起来像”来猜；\n"
        "3. 材料里若出现题号重复或互相矛盾，以第一次出现为准，仍不确定就省略；\n"
        "4. value 只填单个大写字母 A-G（英语七选五可能是 E/F/G），"
        "不要带括号、句点或中文解释。\n\n"
        f"需要匹配的题号：{json.dumps(nos, ensure_ascii=False)}\n\n"
        f"答案材料：\n{answer_text[:12000]}"
    )


# —— 后台导入流水线：单工作线程串行消费，避免并发 AI 互相踩 ——
# 队列条目是 (paper_id, db_path)：id 只在"它所属的那份库"里有意义，入队时把库路径
# 一起钉进去，出队时不再解析全局 settings.DB_PATH（否则库路径中途变更时线程会串库）。
_import_queue: "queue.Queue[tuple]" = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def enqueue_import(paper_id: int, db_path=None) -> None:
    global _worker_started
    if db_path is None:
        db_path = settings.DB_PATH
    _import_queue.put((paper_id, db_path))
    with _worker_lock:
        if not _worker_started:
            _worker_started = True
            t = threading.Thread(target=_worker_loop, daemon=True, name="km-paper-import")
            t.start()


def recover_stuck_papers() -> List[int]:
    """服务重启后把卡在中间态的卷重新排入导入队列，返回重新排队的卷 id。

    导入队列是进程内 `queue.Queue`（单工作线程），进程一死队列就没了——不重新入队，
    卡在 pending/extracting/structuring 的卷永远没人消费，页面上表现为"一直在导入中"。
    error 状态的卷不自动重烧（仍走显式 /retry）：重启自动烧失败卷等于没人批准就烧 AI 额度。
    """
    from app.database import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM exam_papers "
            "WHERE status IN ('pending', 'extracting', 'structuring') ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    conn = get_connection()
    try:
        conn.executemany(
            "UPDATE exam_papers SET status = 'pending', status_note = '服务重启，已自动重新排队' "
            "WHERE id = ?",
            [(i,) for i in ids],
        )
        conn.commit()
    finally:
        conn.close()
    for paper_id in ids:
        enqueue_import(paper_id)
    return ids


def _set_status(conn, paper_id: int, status: str, note: str = "") -> None:
    conn.execute(
        "UPDATE exam_papers SET status = ?, status_note = ? WHERE id = ?",
        (status, note[:300], paper_id),
    )
    conn.commit()


# ---- 拆题检查点（app_meta，免迁移）：断点续跑的实现 -------------------------
# 每成功拆完一段就保存「已完成段数 + 至今拆出的题」；重试时若段数一致就跳过
# 已完成段。段数不一致（源文件被换过/提取结果变了）则整体作废从头来——宁可重烧，
# 不拼出半旧半新的题面。


def _resume_key(paper_id: int) -> str:
    return f"paper_resume_{paper_id}"


def _save_checkpoint(conn, paper_id: int, done: int, questions: list, chunks_total: int) -> None:
    payload = json.dumps(
        {"done": done, "chunks_total": chunks_total, "questions": questions},
        ensure_ascii=False,
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (_resume_key(paper_id), payload),
    )
    conn.commit()


def _load_checkpoint(conn, paper_id: int):
    try:
        row = conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (_resume_key(paper_id),)
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["value"])
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _clear_checkpoint(conn, paper_id: int) -> None:
    conn.execute("DELETE FROM app_meta WHERE key = ?", (_resume_key(paper_id),))
    conn.commit()


def _apply_checkpoint(conn, paper_id: int, chunks: list, questions: list, seen_nos: set) -> int:
    """有可用检查点就把已拆的题灌回并返回起始段下标；否则返回 0（从头拆）。"""
    cp = _load_checkpoint(conn, paper_id)
    if not cp:
        return 0
    done = int(cp.get("done") or 0)
    total = int(cp.get("chunks_total") or 0)
    saved = cp.get("questions") or []
    if done <= 0 or done > len(chunks) or total != len(chunks) or not saved:
        return 0
    for q in saved:
        key = f"{q.get('no')}|{q.get('type')}"
        if key not in seen_nos:
            seen_nos.add(key)
            questions.append(q)
    return done


def _worker_loop() -> None:
    from app.database import get_connection

    while True:
        paper_id, db_path = _import_queue.get()
        try:
            _run_import(paper_id, db_path)
        except Exception as exc:  # 兜底：任何异常都落为 error 状态
            conn = get_connection(db_path)
            try:
                # status_note 会显示在 /papers 页面上，AI 通道的报错先脱敏
                _set_status(conn, paper_id, "error", mask_secret(str(exc)))
            finally:
                conn.close()


def _run_import(paper_id: int, db_path=None) -> None:
    from app.database import get_connection

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            return
        paper = dict(row)
        root = papers_root()
        source = root / paper["source_path"]
        if not source.is_file():
            _set_status(conn, paper_id, "error", f"源文件不存在：{paper['source_path']}")
            return

        _set_status(conn, paper_id, "extracting", "正在提取试卷文本")
        page_pils: dict = {}
        if source.suffix.lower() == ".docx":
            # docx 没有"文本层/扫描版"之分：直接抽全文。
            # 原实现无条件调用 _pdf_text_layer（只认 PDF），docx 会得到空串 →
            # 被误判成"扫描版" → 白跑一轮视觉/OCR → 失败时还报出错误的
            # "扫描版且 OCR/视觉均失败"（实测 25考研政治真题.docx、2024考研英语二真题.docx 都栽在这）。
            pages = []
            scanned = False
            try:
                text_layer = extract_text(source, paper["subject"])
            except Exception as exc:
                _set_status(conn, paper_id, "error", f"docx 读取失败：{exc}")
                return
        else:
            text_layer = _pdf_text_layer(source)
            scanned = not _pdf_text_usable(text_layer)
            pages = _pdf_pages(source, paper["subject"]) if scanned else []
        if scanned and not pages:
            _set_status(conn, paper_id, "error", "未能从文件提取到文本（扫描版且 OCR/视觉均失败）")
            return
        exam_text = text_layer if not scanned else ("\n".join(t for _, t, _ in pages) or text_layer)
        if not exam_text.strip():
            _set_status(
                conn,
                paper_id,
                "error",
                "未能从文件提取到文本（可能是扫描版 PDF，请换 Word/文本版）",
            )
            return

        answer_text = ""
        if paper["answer_path"]:
            answer_path = root / paper["answer_path"]
            if answer_path.is_file():
                try:
                    answer_text = extract_text(answer_path)
                except Exception:
                    answer_text = ""
                # 文本层"看着能读"不等于"能取到答案"：扫描版详解 PDF 的乱码文本层
                # CJK 占比很高，会被 _pdf_text_usable 判为可用，于是 OCR/视觉兜底
                # 永不触发，12000 字乱码被当答案材料送进 AI → 客观题答案基本配不上。
                # 这里对答案文件加一道结构化判据：归一化后拿不到成对答案就强制 OCR。
                if answer_path.suffix.lower() == ".pdf" and not _answer_pairs_from_text(
                    answer_text, expected=8
                ):
                    try:
                        ocr_text = _pdf_ocr(answer_path, paper["subject"])
                    except Exception:
                        ocr_text = ""
                    if _answer_pairs_from_text(ocr_text, expected=8) or not answer_text.strip():
                        answer_text = ocr_text or answer_text
        # 答案册写法五花八门（连排速查 `(1)C. (2)B.`、逐题 `1【答案】（A）…考点：…`），
        # 先归一成 `题号:答案` 行再交给 AI，否则匹配率极低（实测 10 题只配到 1 题且配错）
        if answer_text:
            answer_text = _normalize_answer_text(answer_text)
        # 从卷面解析题号→题型，用于校正答案册序号与卷面题号不一致的情况
        answer_section_map = _answer_section_map(exam_text)

        _set_status(conn, paper_id, "structuring", "AI 正在拆题")
        questions: List[dict] = []
        seen_nos = set()

        def _collect(raw_questions, page_idx: int | None = None) -> None:
            for q in raw_questions:
                no = str(q.get("no") or "").strip()
                qtype = str(q.get("type") or "choice")
                if qtype not in ("choice", "fill", "solution"):
                    qtype = "choice"
                if not no or not str(q.get("question") or "").strip():
                    continue
                key = f"{no}|{qtype}"
                if key in seen_nos:
                    continue
                seen_nos.add(key)
                # page 由模型生成，可能是 "第3页"/"3页" 这类非数字。原来直接 int()，
                # 异常会穿到 _worker_loop 把整份试卷标记为 error —— 已花的 AI 费用白付。
                if page_idx is not None:
                    q_page = page_idx
                else:
                    raw_page = str(q.get("page") or "").strip()
                    try:
                        q_page = max(0, int(raw_page or 0))
                    except (TypeError, ValueError):
                        digits = re.findall(r"\d+", raw_page)
                        q_page = int(digits[0]) if digits else 0
                questions.append(
                    {
                        "no": no,
                        "section": str(q.get("section") or "")[:80],
                        "type": qtype,
                        "passage": str(q.get("passage") or ""),
                        "question": str(q.get("question") or ""),
                        "option_a": str(q.get("option_a") or ""),
                        "option_b": str(q.get("option_b") or ""),
                        "option_c": str(q.get("option_c") or ""),
                        "option_d": str(q.get("option_d") or ""),
                        "option_e": str(q.get("option_e") or ""),
                        "option_f": str(q.get("option_f") or ""),
                        "option_g": str(q.get("option_g") or ""),
                        "correct_answer": "",
                        "analysis": str(q.get("analysis") or ""),
                        "page_idx": q_page,
                        "diagram_image": "",
                    }
                )

        # 统一扁平分块拆题（扫描/公式卷更完整，避免逐页漏掉同页多个综合题）。
        # 每成功一段就落一次检查点（app_meta）：中途失败重试时已拆好的段直接复用，
        # 已花的 AI 费用不白付（此前一块失败整卷作废重烧）。
        if scanned:
            for i, _page_text, pil in pages:
                page_pils[i] = pil
        chunks = _chunk_text(exam_text)
        start_idx = _apply_checkpoint(conn, paper_id, chunks, questions, seen_nos)
        if start_idx:
            _set_status(
                conn,
                paper_id,
                "structuring",
                f"检测到上次进度，从第 {start_idx + 1}/{len(chunks)} 段继续",
            )
        for idx in range(start_idx, len(chunks)):
            parsed = ai_service._chat_json(
                [
                    {
                        "role": "user",
                        "content": _structure_prompt(paper["subject"], paper["year"], chunks[idx]),
                    }
                ],
                max_tokens=12000,
            )
            _collect(parsed.get("questions", []) or [])
            _save_checkpoint(conn, paper_id, idx + 1, questions, len(chunks))
            _set_status(conn, paper_id, "structuring", f"AI 拆题中 {idx + 1}/{len(chunks)} 段")

        if scanned:
            # 拆完再按题号在逐页文本里定位页码（可靠，供图示题存该页原图）。
            for q in questions:
                # 只在文本定位成功时覆盖模型给的页码；定位失败(-1)保留模型自报值，
                # 否则会把原本可用的页码清成 -1。
                located = _page_for_no(q["no"], pages)
                if located >= 0:
                    q["page_idx"] = located

        if not questions:
            _set_status(conn, paper_id, "error", "AI 未能从文本中整理出试题")
            return

        # 用卷面的「题型-题号区间」校正题型：AI 有时把解答题也标成 choice，
        # 那会让答案匹配去问根本不存在的选项答案（也影响模考只取客观题）。
        if answer_section_map:
            fixed = 0
            for q in questions:
                expect = answer_section_map.get(str(q["no"]))
                if expect and q["type"] != expect:
                    q["type"] = expect
                    fixed += 1
                    if expect != "choice":
                        q["correct_answer"] = ""  # 主观题不留选择题式答案
            if fixed:
                _set_status(conn, paper_id, "structuring", f"已按卷面校正 {fixed} 道题的题型")

        # 合卷（mixed）被选作主文件时 answer_path 恒为空（scan_folder 会把它从答案池里
        # 排除掉，避免自己配自己），但同一份文件里就带着答案 —— 直接用卷面文本兜底，
        # 否则这类年份（实测 政治2023 / 数学一2024 / 数学三2024）永远配不到答案。
        if not answer_text and classify_file(source.name) == "mixed":
            answer_text = exam_text

        # 答案匹配：仅客观题，从配对答案文件文本推断
        if answer_text:
            need = [q["no"] for q in questions if q["type"] == "choice" and not q["correct_answer"]]
            if need:
                _set_status(conn, paper_id, "structuring", "正在匹配参考答案")

                # 先用确定性归一化抽出的紧凑答案行：`英语二真题答案速查2010-2024.pdf`
                # 这类多年份合集可长达 12 万字，直接截前 12000 字会让后段题目拿不到答案；
                # 归一化后的 `1:A` 行体积小一两个数量级，且不含解析噪音，更适合交给 AI。
                pairs = _answer_pairs_from_text(answer_text, expected=1)
                material = (
                    "\n".join(
                        f"{no}:{ans}"
                        for no, ans in sorted(pairs.items(), key=lambda kv: int(kv[0]))
                    )
                    if pairs
                    else answer_text
                )

                try:
                    parsed = ai_service._chat_json(
                        [
                            {
                                "role": "user",
                                "content": _answers_prompt(
                                    paper["subject"], paper["year"], need, material
                                ),
                            }
                        ],
                        max_tokens=4000,
                    )
                    answers = parsed.get("answers") or {}
                    for q in questions:
                        if q["type"] == "choice" and q["no"] in answers:
                            ans = str(answers[q["no"]] or "").strip().upper()
                            if re.fullmatch(r"[A-G]", ans):
                                q["correct_answer"] = ans
                except (AiRequestError, Exception):
                    pass  # 答案匹配失败不阻塞入库，答案可后续补

        # 图示选项题：保存该页题图（树/图/流程等原图），供模考/详情查看
        if any(_has_diagram_option(q) for q in questions):
            _img_cache: dict = {}
            for q in questions:
                if not (scanned and _has_diagram_option(q)):
                    continue
                page = q.get("page_idx", -1)
                if not isinstance(page, int) or page < 0:
                    # 题号没能在逐页文本里定位（-1）→ 不给图，绝不用第 1 页冒充
                    q["diagram_image"] = ""
                    continue
                q["diagram_image"] = _page_diagram_image(
                    paper_id, source, page, _img_cache, page_pils.get(page)
                )

        conn.execute("DELETE FROM exam_questions WHERE paper_id = ?", (paper_id,))
        for q in questions:
            conn.execute(
                "INSERT INTO exam_questions (paper_id, no, section, question_type, passage, "
                "question, option_a, option_b, option_c, option_d, option_e, option_f, option_g, "
                "correct_answer, analysis, page_idx, diagram_image) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    paper_id,
                    q["no"],
                    q["section"],
                    q["type"],
                    q["passage"],
                    q["question"],
                    q["option_a"],
                    q["option_b"],
                    q["option_c"],
                    q["option_d"],
                    q.get("option_e", ""),
                    q.get("option_f", ""),
                    q.get("option_g", ""),
                    q["correct_answer"],
                    q["analysis"],
                    q.get("page_idx", 0),
                    q.get("diagram_image", ""),
                ),
            )
        answered = sum(1 for q in questions if q["type"] == "choice" and q["correct_answer"])
        conn.execute(
            "UPDATE exam_papers SET status = 'done', status_note = ?, question_count = ? WHERE id = ?",
            (
                f"客观题已配答案 {answered}/{sum(1 for q in questions if q['type'] == 'choice')}",
                len(questions),
                paper_id,
            ),
        )
        conn.commit()
        _clear_checkpoint(conn, paper_id)
    finally:
        conn.close()
