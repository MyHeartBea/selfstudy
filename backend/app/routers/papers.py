"""真题库接口：扫描、导入、查询、删除。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import PaperCreate
from app.services import exam_paper_service

router = APIRouter(prefix="/api", tags=["真题库"])


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
            for r in conn.execute(
                "SELECT source_path, year FROM exam_papers"
            ).fetchall()
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
        for r in rows:
            r["answered_count"] = conn.execute(
                "SELECT COUNT(*) AS c FROM exam_questions WHERE paper_id = ? AND correct_answer != ''",
                (r["id"],),
            ).fetchone()["c"]
        return ok(rows)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/papers")
def create_paper(body: PaperCreate):
    """登记一份真题并启动后台拆题导入（同源文件幂等）。"""
    root = exam_paper_service.papers_root()
    source = root / body.source_path
    if not source.is_file():
        return error(400, f"文件不存在：{body.source_path}")
    if ".." in body.source_path.replace("\\", "/").split("/"):
        return error(400, "非法路径")
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


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: int):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM exam_papers WHERE id = ?", (paper_id,))
        conn.commit()
        if cur.rowcount == 0:
            return error(404, "真题不存在")
        return ok({"deleted": paper_id})
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
