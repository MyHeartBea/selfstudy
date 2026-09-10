"""导出与导入接口。"""

import base64
import html
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.database import (
    get_connection,
    mistake_field,
    mistake_to_dict,
    snapshot_database,
    sync_mistake_tags,
)
from app.models.tables import MISTAKE_COLUMNS
from app.responses import error, ok, server_error
from app.schemas import ImportPayload
from app.services import mistake_service
from app.services.mistake_service import _images_dir

router = APIRouter(prefix="/api", tags=["导入导出"])

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _export_images(paths) -> list:
    """把图片相对路径转成 base64 data URL，保证导出文件携带图片内容。"""
    out = []
    for path in paths or []:
        rel = str(path)
        try:
            if not rel.startswith("images/"):
                continue
            name = rel.split("/", 1)[1]
            data = (_images_dir() / name).read_bytes()
        except OSError:
            continue
        ext = "." + (name.rsplit(".", 1)[-1].lower() if "." in name else "png")
        mime = _MIME_BY_EXT.get(ext, "image/png")
        out.append(f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}")
    return out


@router.get("/export")
def export_data():
    """导出全部错题与知识点，便于备份和迁移。"""
    conn = get_connection()
    try:
        mistakes = []
        for row in conn.execute("SELECT * FROM mistakes ORDER BY id").fetchall():
            item = mistake_to_dict(row)
            item["images"] = _export_images(item.get("images"))
            mistakes.append(item)
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


def _anki_escape(text) -> str:
    """TSV 字段转义：HTML 转义 + 换行转 <br> + 制表符转空格（Anki 字段支持 HTML）。"""
    return (
        html.escape(str(text or ""), quote=False)
        .replace("\n", "<br>")
        .replace("\t", " ")
    )


@router.get("/export/anki")
def export_anki(type: str = Query("mistakes", pattern="^(mistakes|vocab)$")):
    """导出 Anki 可导入的 TSV（正面 TAB 背面 TAB 标签，字段为 HTML）。

    Anki 导入：文件 → 导入，字段映射默认即可，标签列自动归档。
    """
    conn = get_connection()
    try:
        lines = []
        if type == "vocab":
            rows = conn.execute(
                "SELECT word, meaning, example, kind FROM vocab_items ORDER BY id"
            ).fetchall()
            for r in rows:
                back = _anki_escape(r["meaning"] or "")
                if r["example"]:
                    back += "<br><br>" + _anki_escape(r["example"])
                tag = "短语" if (r["kind"] or "word") == "phrase" else "词汇"
                lines.append(f"{_anki_escape(r['word'])}\t{back}\t{tag}")
            filename = "anki_vocab.tsv"
        else:
            rows = conn.execute(
                "SELECT question, correct_answer, analysis, knowledge_tags "
                "FROM mistakes ORDER BY id"
            ).fetchall()
            for r in rows:
                back_parts = [_anki_escape(r["correct_answer"] or "（无答案）")]
                if r["analysis"]:
                    back_parts.append(_anki_escape(r["analysis"]))
                tags = " ".join(
                    t.strip().replace(" ", "_")
                    for t in (r["knowledge_tags"] or "").split(",")
                    if t.strip()
                )
                front = _anki_escape(r["question"] or "")
                lines.append(f"{front}\t{'<br><br>'.join(back_parts)}\t考研错题 {tags}".rstrip())
            filename = "anki_mistakes.tsv"
    finally:
        conn.close()
    if not lines:
        return error(400, "没有可导出的数据")
    # BOM 让 Anki/Excel 正确识别 UTF-8
    return Response(
        content="\ufeff" + "\n".join(lines),
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_mistakes(body: ImportPayload):
    """批量导入错题，自动处理知识点词条。

    导入是批量写操作：先打一份数据快照，出问题可以回滚（快照见 /api/snapshots）。
    """
    snapshot = snapshot_database(f"before-import-{len(body.mistakes)}")
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
            {"created": created, "failed": failed, "snapshot": snapshot},
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
