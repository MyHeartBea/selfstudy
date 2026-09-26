"""FastAPI 应用入口：路由注册、中间件、异常处理与前端静态资源挂载。"""

import logging
import threading
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import metrics
from app.config import PROJECT_ROOT, settings
from app.database import init_database, maybe_daily_backup
from app.routers import (
    ai,
    essay,
    formulas,
    knowledge,
    mistakes,
    papers,
    reviews,
    sprint,
    stats,
    subjects,
    system,
    transfer,
    vocab,
)
from app.security import token_ok, token_configured, verify_api_token
from app.services.exam_paper_service import recover_stuck_papers


_log_file_handler: RotatingFileHandler | None = None


def _setup_logging() -> None:
    """应用与 uvicorn 日志统一落盘到轮转文件；控制台只留 WARNING 以上。

    start_backend.cmd 把 stdout/stderr 重定向进根目录 backend_out/err.log 且无法轮转，
    uvicorn 的逐请求 access 日志长期运行会把它们撑到无限大。改由 RotatingFileHandler
    收口（data/logs/backend.log，2MB×3），uvicorn.* 的 console handler 摘掉后，
    err.log 只剩启动崩溃现场，正常输出全部进轮转文件。
    """
    global _log_file_handler
    log_dir = PROJECT_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "backend.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8", delay=True
    )
    file_handler.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [file_handler, console]
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [file_handler, console]
        uv_logger.propagate = False
    # 重复调用（测试里会再 setup）时关掉旧 handler，避免文件句柄泄漏
    if _log_file_handler is not None and _log_file_handler is not file_handler:
        _log_file_handler.close()
    _log_file_handler = file_handler


_setup_logging()
logger = logging.getLogger("kaoyan")

_backup_stop = threading.Event()


def _daily_backup_loop(check_interval_seconds: int = 1800) -> None:
    """每半小时醒一次，距上一份 daily 快照超过 24h 就补一份（见 database.maybe_daily_backup）。

    生产是"开机自启后长期不重启"的形态：启动备份只覆盖重启那一刻，这条线程是常态备份线。
    """
    while not _backup_stop.wait(check_interval_seconds):
        try:
            maybe_daily_backup()
        except Exception:
            # 数据路径禁止静默失败：线程里的异常没人接，必须落日志
            logger.exception("每日自动备份失败")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    recovered = recover_stuck_papers()
    if recovered:
        logger.warning("真题导入队列恢复：%s 份卡在中间态的卷已重新排队", len(recovered))
    threading.Thread(target=_daily_backup_loop, daemon=True, name="km-daily-backup").start()
    yield
    _backup_stop.set()


app = FastAPI(
    title=settings.APP_NAME,
    description="考研错题本：错题管理、知识点库、统计与导入导出",
    version=settings.VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def log_http_errors(request: Request, call_next):
    # 未捕获异常由 unhandled_exception_handler 统一记录并返回约定 JSON，这里只记录 5xx 响应
    # 同时统计耗时：慢请求打 WARN 并进入 /api/health 的监控摘要（单用户应用够用了）
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        metrics.record(request.method, request.url.path, 500, duration_ms)
        logger.exception("请求异常：%s %s（%.0fms）", request.method, request.url.path, duration_ms)
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    metrics.record(request.method, request.url.path, response.status_code, duration_ms)

    if response.status_code >= 500:
        logger.error(
            "HTTP 错误：%s %s -> %s（%.0fms）",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    elif duration_ms >= settings.SLOW_REQUEST_MS:
        logger.warning(
            "慢请求：%s %s -> %s（%.0fms，阈值 %dms）",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            settings.SLOW_REQUEST_MS,
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8100",
        "http://127.0.0.1:8100",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """把参数校验错误统一包装为项目约定的 JSON 格式。"""
    messages = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        messages.append(f"{loc}: {err.get('msg', '参数错误')}")
    return JSONResponse(
        status_code=422,
        content={"code": 422, "data": None, "message": "；".join(messages)},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """把 FastAPI/Starlette 内建 HTTPException（404/405 等）统一为项目约定的 JSON 格式。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "data": None, "message": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底：记录堆栈，返回不泄露内部细节的统一 500。"""
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "message": "服务器内部错误，请稍后重试"},
    )


app.include_router(subjects.router, dependencies=[Depends(verify_api_token)])
app.include_router(system.router, dependencies=[Depends(verify_api_token)])
app.include_router(vocab.router, dependencies=[Depends(verify_api_token)])
app.include_router(formulas.router, dependencies=[Depends(verify_api_token)])
app.include_router(mistakes.router, dependencies=[Depends(verify_api_token)])
app.include_router(knowledge.router, dependencies=[Depends(verify_api_token)])
app.include_router(stats.router, dependencies=[Depends(verify_api_token)])
app.include_router(transfer.router, dependencies=[Depends(verify_api_token)])
app.include_router(reviews.router, dependencies=[Depends(verify_api_token)])
app.include_router(ai.router, dependencies=[Depends(verify_api_token)])
app.include_router(papers.router, dependencies=[Depends(verify_api_token)])
app.include_router(essay.router, dependencies=[Depends(verify_api_token)])
app.include_router(sprint.router, dependencies=[Depends(verify_api_token)])

# 错题题干配图静态访问（data/images/）
from app.services.mistake_service import _images_dir  # noqa: E402

_images_dir().mkdir(parents=True, exist_ok=True)


@app.middleware("http")
async def images_token_guard(request: Request, call_next):
    """`/images/**`（静态挂载 + 缩略图端点）的口令守门。

    StaticFiles mount 挂不了 router 依赖，只能用中间件；两者路径都以 /images 开头，
    一处判断全覆盖。token 来源含 cookie/query（<img> 发不了 header），见 security.py。
    """
    if token_configured() and request.url.path.startswith("/images"):
        if not token_ok(request):
            return JSONResponse(
                status_code=401,
                content={"code": 401, "data": None, "message": "未授权：API Token 无效或缺失"},
            )
    return await call_next(request)


@app.get("/images/thumb/{name}", include_in_schema=False)
def image_thumbnail(name: str):
    """列表缩略图：懒生成 WebP（长边 480px，存 data/images/_thumbs/），失败回退原图。

    生成失败不阻塞——直接返回原文件字节，前端无感。
    """
    from fastapi import HTTPException
    from pathlib import Path as _Path

    # 安全：只接受纯文件名，堵目录穿越
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(status_code=404)
    src = _images_dir() / name
    if not src.is_file():
        raise HTTPException(status_code=404)

    thumbs_dir = _images_dir() / "_thumbs"
    thumb = thumbs_dir / f"{_Path(name).stem}.webp"
    if not thumb.is_file():
        # Pillow 缺失也算"生成失败"（CI 环境就没装），照常回退原图
        try:
            from PIL import Image

            thumbs_dir.mkdir(exist_ok=True)
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((480, 480))
                im.save(thumb, "WEBP", quality=78, method=4)
        except Exception:
            return FileResponse(src)
    return FileResponse(thumb, media_type="image/webp")


app.mount("/images", StaticFiles(directory=str(_images_dir())), name="images")


if settings.FRONTEND_DIST.is_dir():
    assets_dir = settings.FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        """单页应用回退：未知地址一律返回 index.html，刷新/直达不白屏。"""
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                {"code": 404, "data": None, "message": "接口不存在"},
                status_code=404,
            )
        if not full_path:
            return FileResponse(
                settings.FRONTEND_DIST / "index.html",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        if ".." in full_path.replace("\\", "/").split("/"):
            return JSONResponse(
                {"code": 404, "data": None, "message": "静态资源不存在"},
                status_code=404,
            )
        dist_root = settings.FRONTEND_DIST.resolve()
        requested = (settings.FRONTEND_DIST / full_path).resolve()
        try:
            requested.relative_to(dist_root)
        except ValueError:
            return JSONResponse(
                {"code": 404, "data": None, "message": "静态资源不存在"},
                status_code=404,
            )
        if full_path.startswith("assets/") and not requested.is_file():
            return JSONResponse(
                {"code": 404, "data": None, "message": "静态资源不存在"},
                status_code=404,
            )
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(
            dist_root / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
else:

    @app.get("/")
    async def root():
        return {
            "message": settings.APP_NAME,
            "docs": "/docs",
            "frontend": "请先执行 cd frontend && npm install && npm run build，"
            "或运行 npm run dev 后访问 http://localhost:5173",
        }
