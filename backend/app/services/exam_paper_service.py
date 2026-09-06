"""真题库：扫描历年真题文件、提取文本、AI 拆题入库（后台流水线）。"""

import json
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.config import PROJECT_ROOT, settings
from app.services import ai_service
from app.services.ai_service import AiRequestError

PAPER_STATUSES = ("pending", "extracting", "structuring", "done", "error")

# 科目识别：按 真题库内的路径/文件名 关键词（顺序敏感：408 先于数学）
_SUBJECT_RULES = [
    ("英语二", ("英语二", "英语（二）", "英语")),
    ("计算机408", ("408", "计算机")),
    ("数学二", ("数学二", "数学")),
    ("政治", ("政治",)),
]

_ANSWER_KEYS = ("答案速查", "答案", "解析", "详解")
_CHUNK_CHARS = 9000


def papers_root() -> Path:
    return Path(settings.PAPERS_DIR or str(PROJECT_ROOT / "真题"))


def guess_subject(text: str) -> str:
    for subject, keys in _SUBJECT_RULES:
        if any(k in text for k in keys):
            return subject
    return ""


def guess_year(text: str) -> str:
    m = re.search(r"(19|20)\d{2}", text or "")
    return m.group(0) if m else ""


def scan_folder() -> List[dict]:
    """扫描真题根目录，返回候选试卷清单（含配对答案文件）。"""
    root = papers_root()
    if not root.is_dir():
        return []
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".docx", ".pdf"):
            continue
        name = path.name
        if name.startswith("~$"):
            continue
        rel = str(path.relative_to(root))
        text = rel
        subject = guess_subject(text)
        year = guess_year(name)
        is_answer = any(k in name for k in _ANSWER_KEYS)
        found.append(
            {
                "rel_path": rel,
                "name": name,
                "subject": subject,
                "year": year,
                "kind": "answer" if is_answer else "paper",
                "size_kb": max(1, round(path.stat().st_size / 1024)),
            }
        )

    # 试卷与答案配对：同科目同年份，优先「答案速查/答案」类小文件
    for item in found:
        if item["kind"] != "paper":
            item["answer_path"] = ""
            continue
        candidates = [
            f
            for f in found
            if f["kind"] == "answer"
            and f["subject"] == item["subject"]
            and f["year"] == item["year"]
            and f["year"]
        ]
        candidates.sort(key=lambda f: (not f["name"].startswith("答案速查"), f["size_kb"]))
        item["answer_path"] = candidates[0]["rel_path"] if candidates else ""
    return found


def extract_text(path: Path) -> str:
    """提取 docx / pdf（文本层）的全文文本。"""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        import docx

        d = docx.Document(str(path))
        parts = [p.text.strip() for p in d.paragraphs if p.text and p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages[:80]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    raise ValueError(f"不支持的文件类型：{suffix}")


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
        '"analysis": "解析（若文本中带有）"}]}\n'
        "规则：\n"
        "1. type 判断：四选项的选 choice；英译汉/翻译与写作选 solution；其余选 fill。\n"
        "2. 只整理试题，跳过考生须知、条形码说明等一切噪声。\n"
        "3. choice 必须带四个选项；选项文本保持原样（LaTeX/公式原样保留）。\n"
        "4. correct_answer 一律留空串（答案由系统从答案文件另行匹配）。\n"
        "5. 文本不完整（被截断）时，只整理能完整识别的题目，不要编造。\n\n"
        f"试卷文本：\n{chunk}"
    )


def _answers_prompt(subject: str, year: str, nos: List[str], answer_text: str) -> str:
    return (
        f"以下是{subject} {year} 年真题的答案材料（可能格式凌乱）。"
        "请为每道题匹配正确答案，输出严格 JSON："
        '{"answers": {"题号": "A/B/C/D 或答案文本"}}。'
        "只填能从材料中确定的题；确定不了不要输出该题。\n\n"
        f"需要匹配的题号：{json.dumps(nos, ensure_ascii=False)}\n\n"
        f"答案材料：\n{answer_text[:12000]}"
    )


# —— 后台导入流水线：单工作线程串行消费，避免并发 AI 互相踩 ——
_import_queue: "queue.Queue[int]" = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def enqueue_import(paper_id: int) -> None:
    global _worker_started
    _import_queue.put(paper_id)
    with _worker_lock:
        if not _worker_started:
            _worker_started = True
            t = threading.Thread(target=_worker_loop, daemon=True, name="km-paper-import")
            t.start()


def _set_status(conn, paper_id: int, status: str, note: str = "") -> None:
    conn.execute(
        "UPDATE exam_papers SET status = ?, status_note = ? WHERE id = ?",
        (status, note[:300], paper_id),
    )
    conn.commit()


def _worker_loop() -> None:
    from app.database import get_connection

    while True:
        paper_id = _import_queue.get()
        try:
            _run_import(paper_id)
        except Exception as exc:  # 兜底：任何异常都落为 error 状态
            conn = get_connection()
            try:
                _set_status(conn, paper_id, "error", str(exc))
            finally:
                conn.close()


def _run_import(paper_id: int) -> None:
    from app.database import get_connection

    conn = get_connection()
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
        exam_text = extract_text(source)
        if not exam_text.strip():
            _set_status(conn, paper_id, "error", "未能从文件提取到文本（可能是扫描版 PDF，请换 Word/文本版）")
            return

        answer_text = ""
        if paper["answer_path"]:
            answer_path = root / paper["answer_path"]
            if answer_path.is_file():
                try:
                    answer_text = extract_text(answer_path)
                except Exception:
                    answer_text = ""

        _set_status(conn, paper_id, "structuring", "AI 正在拆题")
        chunks = _chunk_text(exam_text)
        questions: List[dict] = []
        seen_nos = set()
        for idx, chunk in enumerate(chunks):
            parsed = ai_service._chat_json(
                [{"role": "user", "content": _structure_prompt(paper["subject"], paper["year"], chunk)}],
                max_tokens=8000,
            )
            for q in parsed.get("questions", []) or []:
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
                        "correct_answer": "",
                        "analysis": str(q.get("analysis") or ""),
                    }
                )
            _set_status(conn, paper_id, "structuring", f"AI 拆题中 {idx + 1}/{len(chunks)} 段")

        if not questions:
            _set_status(conn, paper_id, "error", "AI 未能从文本中整理出试题")
            return

        # 答案匹配：仅客观题，从配对答案文件文本推断
        if answer_text:
            need = [q["no"] for q in questions if q["type"] == "choice" and not q["correct_answer"]]
            if need:
                _set_status(conn, paper_id, "structuring", "正在匹配参考答案")
                try:
                    parsed = ai_service._chat_json(
                        [
                            {
                                "role": "user",
                                "content": _answers_prompt(
                                    paper["subject"], paper["year"], need, answer_text
                                ),
                            }
                        ],
                        max_tokens=4000,
                    )
                    answers = parsed.get("answers") or {}
                    for q in questions:
                        if q["type"] == "choice" and q["no"] in answers:
                            ans = str(answers[q["no"]] or "").strip().upper()
                            if re.fullmatch(r"[A-D]", ans):
                                q["correct_answer"] = ans
                except (AiRequestError, Exception):
                    pass  # 答案匹配失败不阻塞入库，答案可后续补

        conn.execute("DELETE FROM exam_questions WHERE paper_id = ?", (paper_id,))
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for q in questions:
            conn.execute(
                "INSERT INTO exam_questions (paper_id, no, section, question_type, passage, "
                "question, option_a, option_b, option_c, option_d, correct_answer, analysis) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    q["correct_answer"],
                    q["analysis"],
                ),
            )
        answered = sum(1 for q in questions if q["type"] == "choice" and q["correct_answer"])
        conn.execute(
            "UPDATE exam_papers SET status = 'done', status_note = ?, question_count = ? WHERE id = ?",
            (f"客观题已配答案 {answered}/{sum(1 for q in questions if q['type'] == 'choice')}", len(questions), paper_id),
        )
        conn.commit()
    finally:
        conn.close()
