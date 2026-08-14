"""错题 CRUD 与筛选接口。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.database import get_connection, mistake_to_dict
from app.responses import error, ok, server_error
from app.schemas import BatchMistakeRequest, GradeRequest, JudgeRequest, MistakeCreate, MistakeUpdate, SourceTypeUpdate
from app.security import ai_rate_limit
from app.services import ai_service, answer_service, mistake_service, review_service
from app.services.ai_service import AiNotConfigured, AiRequestError

router = APIRouter(prefix="/api/mistakes", tags=["错题"])


@router.get("")
def list_mistakes(
    subject_id: Optional[int] = Query(None),
    sub_subject_id: Optional[int] = Query(None),
    question_type: Optional[str] = Query(None),
    difficulty: Optional[List[int]] = Query(None),
    tag: Optional[str] = Query(None),
    approach: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    source_year: Optional[str] = Query(None),
    sort: str = Query("created_desc"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=1000),
):
    """按条件筛选错题，默认按创建时间倒序。"""
    if difficulty:
        for value in difficulty:
            if value < 1 or value > 5:
                return error(400, "难度必须是 1-5")
    conn = get_connection()
    try:
        data = mistake_service.list_mistakes(
            conn,
            {
                "subject_id": subject_id,
                "sub_subject_id": sub_subject_id,
                "question_type": question_type,
                "difficulty": difficulty,
                "tag": tag,
                "approach": approach,
                "search": search,
                "source_type": source_type,
                "source_year": source_year,
                "sort": sort,
            },
            page=page,
            page_size=page_size,
        )
        return ok(data)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/approaches")
def list_approaches(limit: int = Query(200, ge=1, le=1000)):
    """返回已有解题思路，供录入表单联想。"""
    conn = get_connection()
    try:
        return ok(mistake_service.list_approaches(conn, limit))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/{mistake_id}")
def get_mistake(mistake_id: int):
    """返回错题详情，附带知识点补充与同知识点错题。"""
    conn = get_connection()
    try:
        data = mistake_service.get_mistake_detail(conn, mistake_id)
        if data is None:
            return error(404, "错题不存在")
        return ok(data)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/{mistake_id}/reviews")
def list_mistake_reviews(mistake_id: int):
    """返回单道错题的复习记录，按时间倒序。"""
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if exists is None:
            return error(404, "错题不存在")
        return ok(review_service.get_review_history(conn, mistake_id))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{mistake_id}/judge")
def judge_mistake(mistake_id: int, body: JudgeRequest):
    """自动判断答案：选择题比对选项，填空题规范化比对。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if row is None:
            return error(404, "错题不存在")
        mistake = mistake_to_dict(row)
        question_type = mistake.get("question_type") or "choice"
        if question_type == "choice":
            # 与填空题同一套归一化口径：全角/空白/大小写变体都能正确判对
            from app.services.answer_service import normalize_answer

            correct = (
                normalize_answer(body.user_answer)
                == normalize_answer(mistake.get("correct_answer") or "")
                and normalize_answer(body.user_answer) != ""
            )
            return ok(
                {
                    "correct": correct,
                    "user_answer": body.user_answer,
                    "expected": mistake.get("correct_answer"),
                }
            )
        if question_type == "fill":
            result = answer_service.judge_fill(
                body.user_answer,
                mistake.get("correct_answer") or "",
                mistake.get("answer_aliases") or [],
            )
            return ok(result)
        return error(400, "解答题请使用 AI 批改接口")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{mistake_id}/grade", dependencies=[Depends(ai_rate_limit)])
def grade_mistake(mistake_id: int, body: GradeRequest):
    """AI 批改解答题：按过程给分并返回详细解析。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if row is None:
            return error(404, "错题不存在")
        mistake = mistake_to_dict(row)
        if (mistake.get("question_type") or "choice") != "solution":
            return error(400, "只有解答题支持 AI 批改")
        grade = ai_service.grade_solution(
            mistake.get("question") or "",
            mistake.get("correct_answer") or "",
            mistake.get("analysis") or "",
            body.user_answer,
        )
        import json as _json

        cur = conn.execute(
            "INSERT INTO solution_grades "
            "(mistake_id, user_answer, score, verdict, feedback, "
            " errors, strengths, solution, alternate_methods) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mistake_id,
                body.user_answer,
                grade["score"],
                grade["verdict"],
                grade["feedback"],
                _json.dumps(grade["errors"], ensure_ascii=False),
                _json.dumps(grade["strengths"], ensure_ascii=False),
                grade["solution"],
                _json.dumps(grade["alternate_methods"], ensure_ascii=False),
            ),
        )
        conn.commit()
        grade["grade_id"] = cur.lastrowid
        return ok(grade, "AI 批改完成")
    except AiNotConfigured:
        return error(400, "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY、AI_BASE_URL、AI_MODEL")
    except AiRequestError as exc:
        return error(502, str(exc))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("")
def create_mistake(body: MistakeCreate):
    """新建错题，并自动创建缺失的知识点词条。"""
    conn = get_connection()
    try:
        created, errors = mistake_service.create_mistake(conn, body.model_dump())
        if errors:
            return error(400, "；".join(errors))
        return ok(created, "错题创建成功")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/batch")
def batch_mistakes(body: BatchMistakeRequest):
    """批量暂停、恢复、删除错题或修改来源分类。"""
    conn = get_connection()
    try:
        count = mistake_service.batch_mistakes(
            conn,
            body.ids,
            body.action,
            source_type=body.source_type,
            source_year=body.source_year,
            source_name=body.source_name,
        )
        return ok({"count": count}, "批量操作完成")
    except ValueError as exc:
        return error(400, str(exc))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.put("/{mistake_id}")
def update_mistake(mistake_id: int, body: MistakeUpdate):
    """更新指定错题，同时补全缺失的知识点词条。"""
    conn = get_connection()
    try:
        updated, errors = mistake_service.update_mistake(conn, mistake_id, body.model_dump())
        if errors:
            message = errors[0]
            return error(404 if message == "NOT_FOUND" else 400, "；".join(errors))
        return ok(updated, "错题更新成功")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{mistake_id}/pause")
def pause_mistake(mistake_id: int):
    """暂停该错题的复习推送。"""
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if exists is None:
            return error(404, "错题不存在")
        conn.execute(
            "UPDATE mistakes SET review_paused = 1 WHERE id = ?",
            (mistake_id,),
        )
        conn.commit()
        return ok({"id": mistake_id, "review_paused": True}, "已暂停复习")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{mistake_id}/resume")
def resume_mistake(mistake_id: int):
    """恢复该错题的复习推送。"""
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if exists is None:
            return error(404, "错题不存在")
        conn.execute(
            "UPDATE mistakes SET review_paused = 0 WHERE id = ?",
            (mistake_id,),
        )
        conn.commit()
        return ok({"id": mistake_id, "review_paused": False}, "已恢复复习")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{mistake_id}/source-type")
def update_source_type(mistake_id: int, body: SourceTypeUpdate):
    """快速修改错题的来源分类（真题/模拟题/自编/其他）。"""
    try:
        source_type = mistake_service.validate_source_type(body.source_type)
    except ValueError as exc:
        return error(400, str(exc))
    source_year = (body.source_year or "").strip()
    source_name = (body.source_name or "").strip()
    source_issue = mistake_service.validate_source_requirements(
        source_type,
        source_year,
        source_name,
    )
    if source_issue:
        return error(400, source_issue)
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if exists is None:
            return error(404, "错题不存在")
        conn.execute(
            "UPDATE mistakes SET source_type = ?, source_year = ?, source_name = ? "
            "WHERE id = ?",
            (
                source_type,
                source_year,
                source_name,
                mistake_id,
            ),
        )
        conn.commit()
        return ok(
            {
                "id": mistake_id,
                "source_type": source_type,
                "source_year": source_year,
                "source_name": source_name,
            },
            "来源分类已更新",
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.delete("/{mistake_id}")
def delete_mistake(mistake_id: int):
    """删除指定错题。"""
    conn = get_connection()
    try:
        if not mistake_service.delete_mistake(conn, mistake_id):
            return error(404, "错题不存在")
        return ok({"id": mistake_id}, "错题删除成功")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
