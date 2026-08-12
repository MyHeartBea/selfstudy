"""导出与导入接口。"""

from datetime import datetime

from fastapi import APIRouter

from app.database import get_connection, mistake_field, mistake_to_dict
from app.models.tables import MISTAKE_COLUMNS
from app.responses import error, ok
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
        return ok(
            {
                "mistakes": mistakes,
                "knowledge": knowledge,
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    except Exception as exc:
        return error(500, f"导出失败：{exc}")
    finally:
        conn.close()


@router.post("/import")
def import_mistakes(body: ImportPayload):
    """批量导入错题，自动处理知识点词条。"""
    conn = get_connection()
    try:
        created = 0
        failed = []
        with conn:
            for index, item in enumerate(body.mistakes):
                payload = item.model_dump()
                fields, errors = mistake_service.build_mistake_fields(payload, conn)
                if errors:
                    failed.append({"index": index, "error": "；".join(errors)})
                    continue
                mistake_service.ensure_knowledge_tags(
                    conn,
                    fields["knowledge_tags"],
                    fields["subject_id"],
                    fields["sub_subject_id"],
                )
                conn.execute(
                    f"INSERT INTO mistakes ({', '.join(MISTAKE_COLUMNS)}) "
                    f"VALUES ({', '.join('?' for _ in MISTAKE_COLUMNS)})",
                    tuple(
                        mistake_field(fields, column)
                        for column in MISTAKE_COLUMNS
                    ),
                )
                created += 1
        return ok(
            {"created": created, "failed": failed},
            f"成功导入 {created} 条错题",
        )
    except Exception as exc:
        return error(500, f"导入失败：{exc}")
    finally:
        conn.close()
