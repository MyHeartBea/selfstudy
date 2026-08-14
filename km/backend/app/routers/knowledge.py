"""知识点库接口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import KnowledgeUpdate
from app.security import ai_rate_limit
from app.services import ai_service, knowledge_service
from app.services.ai_service import AiNotConfigured, AiRequestError

router = APIRouter(prefix="/api/knowledge", tags=["知识点"])


@router.get("")
def list_knowledge(
    subject_id: Optional[int] = Query(None),
    sub_subject_id: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=200),
):
    """按科目、二级科目、标签模糊搜索知识点；传 page 时返回分页结果。"""
    conn = get_connection()
    try:
        data = knowledge_service.list_knowledge(
            conn,
            subject_id,
            sub_subject_id,
            tag,
            page=page,
            page_size=page_size,
        )
        return ok(data)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/by-tag")
def get_knowledge_by_tag(tag: str = Query(..., min_length=1)):
    """按标签名精确获取知识点词条。"""
    conn = get_connection()
    try:
        data = knowledge_service.get_by_tag(conn, tag)
        if data is None:
            return error(404, "知识点不存在")
        return ok(data)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.patch("/{knowledge_id}")
def update_knowledge(knowledge_id: int, body: KnowledgeUpdate):
    """更新知识点摘要（PATCH 语义：None 字段保持不变）。"""
    conn = get_connection()
    try:
        updated = knowledge_service.update_knowledge(
            conn,
            knowledge_id,
            body.summary,
            subject_id=body.subject_id,
            sub_subject_id=body.sub_subject_id,
            related_tags=body.related_tags,
        )
        if updated is None:
            return error(404, "知识点不存在")
        return ok(updated, "知识点更新成功")
    except ValueError as exc:
        return error(400, str(exc))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.delete("/{knowledge_id}")
def delete_knowledge(knowledge_id: int):
    """删除知识点词条，不影响关联错题。"""
    conn = get_connection()
    try:
        if not knowledge_service.delete_knowledge(conn, knowledge_id):
            return error(404, "知识点不存在")
        return ok({"id": knowledge_id}, "知识点删除成功")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{knowledge_id}/auto-summarize", dependencies=[Depends(ai_rate_limit)])
def auto_summarize(knowledge_id: int):
    """根据关联错题自动生成并保存知识点总结。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)
        ).fetchone()
        if row is None:
            return error(404, "知识点不存在")
        tag_name = row["tag_name"]
        mistake_rows = conn.execute(
            "SELECT question, correct_answer, analysis FROM mistakes "
            "WHERE EXISTS (SELECT 1 FROM mistake_tag_map mt "
            "              WHERE mt.mistake_id = mistakes.id AND mt.tag = ?) LIMIT 8",
            (tag_name,),
        ).fetchall()
        if not mistake_rows:
            return error(400, "该知识点下暂无错题，无法自动总结")
        summary = ai_service.summarize_knowledge(tag_name, [dict(item) for item in mistake_rows])
        conn.execute(
            "UPDATE knowledge_base SET summary = ? WHERE id = ?",
            (summary, knowledge_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)
        ).fetchone()
        return ok(knowledge_service.knowledge_to_dict(updated), "知识点总结已生成")
    except AiNotConfigured:
        return error(400, "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY、AI_BASE_URL、AI_MODEL")
    except AiRequestError as exc:
        return error(502, str(exc))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
