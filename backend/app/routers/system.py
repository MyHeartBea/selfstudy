"""系统级接口：健康检查与仪表盘聚合数据。"""

import logging
import platform
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app import metrics
from app.config import settings
from app.database import get_connection, list_snapshots, restore_snapshot, snapshot_database
from app.responses import error, ok, server_error
from app.schemas import SnapshotRestore
from app.services import integrity_service, review_service, search_service, stats_service
from app.services.mistake_service import _images_dir

logger = logging.getLogger("kaoyan")
router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
def health():
    """轻量健康检查：供前端状态灯与脚本探活使用。

    附带进程内监控摘要（请求数/错误数/慢端点/**按通道的 AI 调用账**），便于一眼看出
    哪里慢、有没有 5xx、以及识图是不是正在偷偷降级到兜底通道（`metrics.ai.by_model`）。
    """
    conn = get_connection()
    try:
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        conn.close()
    return ok(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "version": settings.VERSION,
            "app": settings.APP_NAME,
            "python": platform.python_version(),
            "host": settings.HOST,
            "reviewDailyLimit": settings.REVIEW_DAILY_LIMIT,
            "metrics": metrics.snapshot(),
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/exam-countdown")
def exam_countdown():
    """考研倒计时（纯日期计算，不查库）：供外壳在每个页面显示。"""
    return ok(stats_service.exam_countdown())


@router.get("/dashboard")
def dashboard():
    """仪表盘聚合：一次请求返回错题统计 + 复习统计，减少首屏往返。"""
    conn = get_connection()
    try:
        return ok(
            {
                "stats": stats_service.get_stats(conn),
                "reviews": review_service.get_review_stats(conn),
            }
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(5, ge=1, le=20),
):
    """全站统一搜索（命令面板用）：错题 / 知识点 / 公式 / 生词 / 作文一次问完。

    响应是 `{q,total,limit,groups:[{key,label,total,items:[{id,title,subtitle,meta}]}]}`，
    **空组不返回**；`items` 只给跳转与预览需要的字段，不给整条记录（面板不该拉解析全文）。
    """
    conn = get_connection()
    try:
        return ok(search_service.search_all(conn, q, limit))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/system/integrity")
def system_integrity(
    limit: int = Query(200, ge=1, le=1000, description="每个清单最多返回多少条"),
    keep_days: float = Query(1.0, ge=0, le=30, description="最近 N 天生成的文件不算孤儿"),
):
    """**只读**数据体检：图片文件与库里引用对不对得上。

    两类问题分开报：`orphans`（文件没人引用，内容仍可被 /images/<name> 直接访问）、
    `missing`（行指向一张不存在的图，页面上就是个破图）。判定口径与
    `scripts/clean_orphan_images.py` 共用 `integrity_service`，不会两边各说一套。
    **这个接口不删任何东西**，清理仍然是脚本的 `--apply`（默认 dry-run）。
    """
    conn = get_connection()
    try:
        return ok(integrity_service.scan(conn, _images_dir(), keep_days=keep_days, limit=limit))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/snapshots")
def get_snapshots(limit: int = Query(20, ge=1, le=100)):
    """最近的数据快照列表（启动自动备份 + 导入前快照）。"""
    try:
        return ok(list_snapshots(limit))
    except Exception as exc:
        return server_error(exc)


@router.post("/snapshots")
def create_snapshot(label: str = Query("manual", max_length=40)):
    """手动打一份数据快照（批量导入/删除前建议先点一下）。"""
    name = snapshot_database(label)
    if not name:
        return error(500, "快照创建失败")
    return ok({"name": name}, "快照已创建")


@router.post("/snapshots/restore")
def restore_snapshot_api(body: SnapshotRestore):
    """**整库回滚**到指定快照：会覆盖当前全部错题/复习/知识点等数据。

    - 必须 `confirm` 与 `name` 完全一致（服务端也要验，理由见 `SnapshotRestore`）；
    - 覆盖前会先给当前现场打一份 `before-restore` 快照，打不出来就直接中止 ——
      没有反悔点的回滚一旦选错，丢失的是"这一份快照之后干的所有活"；
    - **快照只含数据库，图片文件不在内**：回滚不会删图，也回不回已删的图。
    """
    if body.confirm.strip() != body.name:
        return error(400, "确认文本与快照名不一致，已取消（不会改动任何数据）")
    try:
        result = restore_snapshot(body.name)
    except ValueError as exc:
        return error(400, str(exc))
    except FileNotFoundError:
        return error(404, f"找不到快照：{body.name}")
    except sqlite3.Error as exc:
        logger.warning("快照回滚失败（%s）：%s", body.name, exc)
        return error(409, "快照读取失败，已中止，当前数据未改动")
    except RuntimeError as exc:
        return error(409, str(exc))
    except Exception as exc:
        return server_error(exc, "快照回滚")
    return ok(
        result,
        f"已回到 {result['name']}；回滚前的现场另存为 {result['safety_snapshot']}。"
        "图片文件不随快照回滚。",
    )
