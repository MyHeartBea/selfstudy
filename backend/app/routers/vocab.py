"""生词本接口：CRUD、到期队列、闪卡复习与批量导入。"""

import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import VocabCreate, VocabReview, VocabUpdate
from app.services import vocab_service

router = APIRouter(prefix="/api/vocab", tags=["生词本"])


@router.get("")
def list_vocab(
    search: Optional[str] = Query(None),
    mastery: Optional[int] = Query(None, ge=0, le=8),
    sort: str = Query("created_desc"),
    page: Optional[int] = Query(None, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """生词列表：可搜索、按掌握度筛选，传 page 返回分页结果。"""
    conn = get_connection()
    try:
        return ok(
            vocab_service.list_vocab(
                conn,
                search=search,
                mastery=mastery,
                page=page,
                page_size=page_size,
                sort=sort,
            )
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/stats")
def vocab_stats():
    """生词总览：总数、今日到期、已掌握、掌握度分布。"""
    conn = get_connection()
    try:
        return ok(vocab_service.vocab_stats(conn))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/due")
def due_vocab(limit: int = Query(30, ge=1, le=100)):
    """今日到期生词（闪卡队列）。"""
    conn = get_connection()
    try:
        return ok(vocab_service.get_due_vocab(conn, limit))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("")
def create_vocab(body: VocabCreate):
    """新增生词；单词已存在时返回已有条目（幂等）。"""
    conn = get_connection()
    try:
        row = vocab_service.create_vocab(
            conn,
            word=body.word,
            meaning=body.meaning,
            phonetic=body.phonetic,
            example=body.example,
            note=body.note,
            source=body.source,
        )
        return ok(vocab_service.vocab_to_dict(row))
    except sqlite3.IntegrityError:
        return error(409, "单词已存在")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/import")
def import_vocab(body: dict):
    """批量导入：body 为 {"lines": ["abandon 抛弃", ...], "source": "来源"}。"""
    lines = body.get("lines") or []
    source = str(body.get("source") or "")
    if not isinstance(lines, list) or not lines:
        return error(400, "请提供要导入的生词行")
    if len(lines) > 2000:
        return error(400, "单次最多导入 2000 行")
    conn = get_connection()
    try:
        result = vocab_service.import_vocab(conn, [str(item) for item in lines], source)
        return ok(result)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.put("/{vocab_id}")
def update_vocab(vocab_id: int, body: VocabUpdate):
    """更新生词（PATCH 语义：None 字段保持不变）。"""
    conn = get_connection()
    try:
        row = vocab_service.update_vocab(
            conn,
            vocab_id,
            {
                "word": body.word,
                "meaning": body.meaning,
                "phonetic": body.phonetic,
                "example": body.example,
                "note": body.note,
                "source": body.source,
            },
        )
        if row is None:
            return error(404, "生词不存在")
        return ok(vocab_service.vocab_to_dict(row))
    except sqlite3.IntegrityError:
        return error(409, "单词已存在")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.delete("/{vocab_id}")
def delete_vocab(vocab_id: int):
    conn = get_connection()
    try:
        if not vocab_service.delete_vocab(conn, vocab_id):
            return error(404, "生词不存在")
        return ok(None, "已删除")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/{vocab_id}/review")
def review_vocab(vocab_id: int, body: VocabReview):
    """闪卡复习：result = known | fuzzy | unknown，自动排期。"""
    if body.result not in ("known", "fuzzy", "unknown"):
        return error(400, "result 必须是 known / fuzzy / unknown")
    conn = get_connection()
    try:
        row = vocab_service.review_vocab(conn, vocab_id, body.result)
        if row is None:
            return error(404, "生词不存在")
        return ok(row)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
