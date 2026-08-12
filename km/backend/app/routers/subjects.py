"""科目与二级科目接口。"""

import json
from typing import Optional

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok
from app.schemas import SubjectProfileUpdate

router = APIRouter(prefix="/api", tags=["基础数据"])


@router.get("/subjects")
def list_subjects():
    """返回全部科目。"""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM subjects ORDER BY id").fetchall()
        return ok([dict(row) for row in rows])
    except Exception as exc:
        return error(500, f"查询科目失败：{exc}")
    finally:
        conn.close()


@router.get("/sub_subjects")
def list_sub_subjects(subject_id: Optional[int] = Query(None)):
    """返回二级科目，可按科目筛选。"""
    conn = get_connection()
    try:
        if subject_id is None:
            rows = conn.execute("SELECT * FROM sub_subjects ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sub_subjects WHERE subject_id = ? ORDER BY id",
                (subject_id,),
            ).fetchall()
        return ok([dict(row) for row in rows])
    except Exception as exc:
        return error(500, f"查询二级科目失败：{exc}")
    finally:
        conn.close()


def _profile_to_dict(row) -> dict:
    data = dict(row)
    try:
        data["focus_areas"] = json.loads(data.get("focus_areas") or "[]")
    except (TypeError, ValueError):
        data["focus_areas"] = []
    return data


@router.get("/subjects/{subject_id}/profile")
def get_subject_profile(subject_id: int):
    """返回科目的复习重点与方法建议。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM subject_profiles WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        if row is None:
            return ok({"subject_id": subject_id, "focus_areas": [], "review_tips": ""})
        return ok(_profile_to_dict(row))
    except Exception as exc:
        return error(500, f"查询科目档案失败：{exc}")
    finally:
        conn.close()


@router.put("/subjects/{subject_id}/profile")
def update_subject_profile(subject_id: int, body: SubjectProfileUpdate):
    """更新科目的复习重点与方法建议。"""
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        if exists is None:
            return error(404, "科目不存在")
        focus_areas = [str(item).strip() for item in body.focus_areas if str(item).strip()]
        conn.execute(
            "INSERT INTO subject_profiles (subject_id, focus_areas, review_tips) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(subject_id) DO UPDATE SET "
            "focus_areas = excluded.focus_areas, "
            "review_tips = excluded.review_tips, "
            "updated_at = CURRENT_TIMESTAMP",
            (subject_id, json.dumps(focus_areas, ensure_ascii=False), body.review_tips.strip()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM subject_profiles WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()
        return ok(_profile_to_dict(row), "科目档案已更新")
    except Exception as exc:
        return error(500, f"更新科目档案失败：{exc}")
    finally:
        conn.close()
