"""FastAPI 应用入口：路由注册、中间件、异常处理与前端静态资源挂载。"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_database
from app.routers import (
    ai,
    formulas,
    knowledge,
    mistakes,
    reviews,
    stats,
    subjects,
    system,
    transfer,
    vocab,
)
from app.security import verify_api_token

logger = logging.getLogger("kaoyan")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="考研错题本：错题管理、知识点库、统计与导入导出",
    version=settings.VERSION,
    lifespan=lifespan,
)

@app.middleware("http")
async def log_http_errors(request: Request, call_next):
    # 未捕获异常由 unhandled_exception_handler 统一记录并返回约定 JSON，这里只记录 5xx 响应
    response = await call_next(request)
    if response.status_code >= 500:
        logger.error(
            "HTTP 错误：%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
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

# 错题题干配图静态访问（data/images/）
from app.services.mistake_service import _images_dir  # noqa: E402

_images_dir().mkdir(parents=True, exist_ok=True)
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
