"""FastAPI 应用入口：路由注册、中间件、异常处理与前端静态资源挂载。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_database
from app.routers import ai, formulas, knowledge, mistakes, reviews, stats, subjects, transfer


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


app.include_router(subjects.router)
app.include_router(formulas.router)
app.include_router(mistakes.router)
app.include_router(knowledge.router)
app.include_router(stats.router)
app.include_router(transfer.router)
app.include_router(reviews.router)
app.include_router(ai.router)


if settings.FRONTEND_DIST.is_dir():
    assets_dir = settings.FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        """单页应用回退：未知地址一律返回 index.html，刷新/直达不白屏。"""
        if full_path.startswith("api/"):
            return JSONResponse(
                {"code": 404, "data": None, "message": "接口不存在"},
                status_code=404,
            )
        requested = settings.FRONTEND_DIST / full_path
        if full_path.startswith("assets/") and not requested.is_file():
            return JSONResponse(
                {"code": 404, "data": None, "message": "静态资源不存在"},
                status_code=404,
            )
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(
            settings.FRONTEND_DIST / "index.html",
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
