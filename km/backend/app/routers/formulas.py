"""公式库接口。"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import FormulaCreate, FormulaUpdate
from app.services import formula_service

router = APIRouter(prefix="/api/formulas", tags=["公式库"])


@router.get("")
def list_formulas(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """返回公式条目，可按分类和关键词筛选。"""
    conn = get_connection()
    try:
        return ok(formula_service.list_formulas(conn, category, search))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("")
def create_formula(body: FormulaCreate):
    """新增公式条目。"""
    conn = get_connection()
    try:
        created = formula_service.create_formula(
            conn,
            body.category,
            body.title,
            body.content,
        )
        return ok(created, "公式已添加")
    except sqlite3.IntegrityError:
        return error(400, "公式标题已存在")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.put("/{formula_id}")
def update_formula(formula_id: int, body: FormulaUpdate):
    """更新公式条目。"""
    conn = get_connection()
    try:
        updated = formula_service.update_formula(
            conn,
            formula_id,
            body.category,
            body.title,
            body.content,
        )
        if updated is None:
            return error(404, "公式不存在")
        return ok(updated, "公式已更新")
    except sqlite3.IntegrityError:
        return error(400, "公式标题已存在")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.delete("/{formula_id}")
def delete_formula(formula_id: int):
    """删除公式条目。"""
    conn = get_connection()
    try:
        if not formula_service.delete_formula(conn, formula_id):
            return error(404, "公式不存在")
        return ok({"id": formula_id}, "公式已删除")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
