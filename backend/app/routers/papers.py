"""真题库接口：扫描、导入、查询、删除。"""

from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import PaperAnswerPatch, PaperCreate
from app.services import exam_paper_service

router = APIRouter(prefix="/api", tags=["真题库"])


def _resolve_inside(value: str) -> Path | None:
    """把「真题根目录内的相对路径」解析成绝对路径；越界/绝对路径/.. 一律拒绝。

    Windows 上 `root / "C:/x/y.pdf"` 会被绝对路径整体替换 → 可读磁盘上任意
    PDF/DOCX（正文还能经 GET /api/papers/{id} 取回），所以入口必须先过这道门。
    盘符路径要单独用正则拒绝：Linux 上 `Path("C:/x/y.pdf").is_absolute()` 是
    False（CI 真踩过），它作为"相对路径"也永远不合法，在哪台主机上都得挡。
    """
    if not value:
        return None
    if Path(value).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        return None
    if ".." in value.replace("\\", "/").split("/"):
        return None
    root = exam_paper_service.papers_root().resolve()
    target = (root / value).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


@router.get("/papers/estimate")
def estimate_paper(source_path: str = Query(...), answer_path: str = Query("")):
    """导入前的账单：本地探针估算 AI 调用次数/耗时/风险，一次 AI 都不调。"""
    source = _resolve_inside(source_path)
    if source is None:
        return error(400, "非法路径：source_path 必须是真题目录内的相对路径")
    answer = _resolve_inside(answer_path) if answer_path else None
    if answer_path and answer is None:
        return error(400, "非法路径：answer_path 必须是真题目录内的相对路径")
    try:
        return ok(exam_paper_service.estimate_import(source_path, answer_path))
    except Exception as exc:
        return server_error(exc)


@router.get("/papers/scan")
def scan_papers():
    """扫描真题文件夹，返回候选试卷清单（含配对答案文件与导入状态）。"""
    try:
        candidates = exam_paper_service.scan_folder()
    except Exception as exc:
        return server_error(exc)
    conn = get_connection()
    try:
        existing = {
            (r["source_path"], r["year"])
            for r in conn.execute("SELECT source_path, year FROM exam_papers").fetchall()
        }
    finally:
        conn.close()
    for item in candidates:
        item["imported"] = (item["rel_path"], item["year"]) in existing
    return ok(candidates)


@router.get("/papers")
def list_papers(status: str = Query("", pattern="^(|pending|extracting|structuring|done|error)$")):
    """真题库列表（可按状态过滤），按年份倒序。"""
    conn = get_connection()
    try:
        sql = "SELECT * FROM exam_papers"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY year DESC, id DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        # 已配答案数一次分组查询取回（此前逐卷子查询，卷多了就是 N+1）
        answered = {
            r["paper_id"]: r["c"]
            for r in conn.execute(
                "SELECT paper_id, COUNT(*) AS c FROM exam_questions "
                "WHERE correct_answer != '' GROUP BY paper_id"
            ).fetchall()
        }
        for r in rows:
            r["answered_count"] = answered.get(r["id"], 0)
        return ok(rows)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/papers")
def create_paper(body: PaperCreate):
    """登记一份真题并启动后台拆题导入（同源文件幂等）。"""
    source = _resolve_inside(body.source_path)
    if source is None:
        return error(400, "非法路径：source_path 必须是真题目录内的相对路径")
    if source.suffix.lower() not in (".pdf", ".docx") or not source.is_file():
        return error(400, f"文件不存在或类型不支持：{body.source_path}")

    if body.answer_path:
        answer = _resolve_inside(body.answer_path)
        if answer is None:
            return error(400, "非法路径：answer_path 必须是真题目录内的相对路径")
        if answer.suffix.lower() not in (".pdf", ".docx") or not answer.is_file():
            return error(400, f"答案文件不存在或类型不支持：{body.answer_path}")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM exam_papers WHERE source_path = ? AND year = ?",
            (body.source_path, body.year),
        ).fetchone()
        if existing:
            paper = dict(existing)
            if paper["status"] in ("pending", "extracting", "structuring"):
                exam_paper_service.enqueue_import(paper["id"])
                return ok(paper)
            return ok(paper)
        cur = conn.execute(
            "INSERT INTO exam_papers (subject, year, title, source_path, answer_path, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (
                body.subject,
                body.year,
                body.title,
                body.source_path,
                body.answer_path,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        paper = dict(
            conn.execute("SELECT * FROM exam_papers WHERE id = ?", (cur.lastrowid,)).fetchone()
        )
        exam_paper_service.enqueue_import(cur.lastrowid)
        return ok(paper)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/papers/{paper_id}")
def paper_detail(paper_id: int):
    """真题详情：试卷信息 + 全部题目。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            return error(404, "真题不存在")
        paper = dict(row)
        paper["questions"] = [
            dict(q)
            for q in conn.execute(
                "SELECT * FROM exam_questions WHERE paper_id = ? ORDER BY id",
                (paper_id,),
            ).fetchall()
        ]
        return ok(paper)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/papers/{paper_id}/retry")
def retry_paper(paper_id: int):
    """失败的卷重新入队（配合拆题检查点：已成功拆出的段不会重烧 AI）。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            return error(404, "真题不存在")
        if dict(row)["status"] != "error":
            return error(400, "只有导入失败的卷才能重试")
        conn.execute(
            "UPDATE exam_papers SET status = 'pending', status_note = '等待重试' WHERE id = ?",
            (paper_id,),
        )
        conn.commit()
        exam_paper_service.enqueue_import(paper_id)
        return ok(
            dict(conn.execute("SELECT * FROM exam_papers WHERE id = ?", (paper_id,)).fetchone())
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.patch("/papers/{paper_id}/questions/{question_id}")
def patch_paper_question(paper_id: int, question_id: int, body: PaperAnswerPatch):
    """人工修正题目答案（正则没配上/配错了，卷面上直接改）。"""
    conn = get_connection()
    try:
        q, err = exam_paper_service.set_question_answer(
            conn, paper_id, question_id, body.correct_answer
        )
        if err:
            return error(404 if err == "题目不存在" else 400, err)
        return ok(q)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/papers/{paper_id}/questions/{question_id}/to-mistake")
def paper_question_to_mistake(paper_id: int, question_id: int):
    """把一道真题转入错题本（同卷同题干幂等）。"""
    conn = get_connection()
    try:
        mistake, err = exam_paper_service.question_to_mistake(conn, paper_id, question_id)
        if err:
            return error(404 if err in ("真题不存在", "题目不存在") else 400, err)
        return ok(mistake)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: int):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM exam_papers WHERE id = ?", (paper_id,))
        conn.commit()
        if cur.rowcount == 0:
            return error(404, "真题不存在")
        # 图示题的页面原图存在 data/images/exam_papers/<id>/（不在库里，级联删不掉）
        exam_paper_service.remove_paper_images(paper_id)
        return ok({"deleted": paper_id})
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
