"""导出与导入接口。"""

from datetime import datetime

from fastapi import APIRouter

from app.database import get_connection, mistake_field, mistake_to_dict, sync_mistake_tags
from app.models.tables import MISTAKE_COLUMNS
from app.responses import error, ok, server_error
from app.schemas import ImportPayload
from app.services import mistake_service

router = APIRouter(prefix="/api", tags=["导入导出"])


@router.get("/export")
def export_data():
    """导出全部错题与知识点，便于备份和迁移。"""
    conn = get_connection()
    try:
        mistakes = [
            mistake_to_dict(row)
            for row in conn.execute("SELECT * FROM mistakes ORDER BY id").fetchall()
        ]
        knowledge = [
            dict(row)
            for row in conn.execute("SELECT * FROM knowledge_base ORDER BY id").fetchall()
        ]
        subjects = [
            dict(row)
            for row in conn.execute("SELECT * FROM subjects ORDER BY id").fetchall()
        ]
        sub_subjects = [
            dict(row)
            for row in conn.execute("SELECT * FROM sub_subjects ORDER BY id").fetchall()
        ]
        return ok(
            {
                "mistakes": mistakes,
                "knowledge": knowledge,
                "subjects": subjects,
                "sub_subjects": sub_subjects,
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/import")
def import_mistakes(body: ImportPayload):
    """批量导入错题，自动处理知识点词条。"""
    conn = get_connection()
    try:
        created = 0
        failed = []
        # 预加载科目/二级科目集合，避免逐条 build_mistake_fields 时 N+1 查询
        valid_subjects = {
            row["id"]
            for row in conn.execute("SELECT id FROM subjects").fetchall()
        }
        valid_sub_subjects = {
            (row["subject_id"], row["id"])
            for row in conn.execute("SELECT subject_id, id FROM sub_subjects").fetchall()
        }
        with conn:
            for index, item in enumerate(body.mistakes):
                payload = item.model_dump()
                errors = _validate_mistake_payload(
                    payload, valid_subjects, valid_sub_subjects
                )
                if errors:
                    failed.append({"index": index, "error": "；".join(errors)})
                    continue
                fields, build_errors = mistake_service.build_mistake_fields(
                    payload, conn, skip_subject_check=True
                )
                if build_errors:
                    failed.append({"index": index, "error": "；".join(build_errors)})
                    continue
                mistake_service.ensure_knowledge_tags(
                    conn,
                    fields["knowledge_tags"],
                    fields["subject_id"],
                    fields["sub_subject_id"],
                )
                cur = conn.execute(
                    f"INSERT INTO mistakes ({', '.join(MISTAKE_COLUMNS)}) "
                    f"VALUES ({', '.join('?' for _ in MISTAKE_COLUMNS)})",
                    tuple(
                        mistake_field(fields, column)
                        for column in MISTAKE_COLUMNS
                    ),
                )
                sync_mistake_tags(conn, cur.lastrowid, fields["knowledge_tags"])
                created += 1
        return ok(
            {"created": created, "failed": failed},
            f"成功导入 {created} 条错题",
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


def _validate_mistake_payload(
    payload: dict,
    valid_subjects: set,
    valid_sub_subjects: set,
) -> list:
    """导入前快速校验科目存在性，避免 build_mistake_fields 内逐条 SELECT 1。"""
    errors = []
    subject_id = payload.get("subject_id")
    sub_subject_id = payload.get("sub_subject_id")
    try:
        subject_id = int(subject_id) if subject_id not in (None, "") else None
    except (TypeError, ValueError):
        return ["科目参数无效"]
    if subject_id is None:
        errors.append("科目不能为空")
    elif subject_id not in valid_subjects:
        errors.append("所选科目不存在")
    if sub_subject_id not in (None, ""):
        try:
            sub_subject_id = int(sub_subject_id)
        except (TypeError, ValueError):
            return ["二级科目参数无效"]
        if (subject_id, sub_subject_id) not in valid_sub_subjects:
            errors.append("二级科目不存在或与科目不匹配")
    return errors
