"""应用配置：路径、服务端口、数据库位置与 AI 服务参数。"""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _load_env_file(path: Path) -> None:
    """轻量读取 .env 文件，不引入额外依赖。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BACKEND_DIR / ".env")


class Settings:
    APP_NAME = "考研错题本 API"
    VERSION = "2.1.0"
    HOST = "0.0.0.0"
    PORT = 8000
    DB_PATH = PROJECT_ROOT / "data" / "kaoyan_mistakes.db"
    BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
    MAX_BACKUPS = 20
    FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

    # AI 服务（OpenAI 兼容接口，可在 backend/.env 中配置）
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    # 可选：支持图片的视觉模型，例如 gpt-4o-mini、qwen-vl-max、豆包视觉模型。
    # 配置后，截图识别会优先直接交给视觉模型，比本地 OCR 更准。
    AI_VISION_MODEL = os.environ.get("AI_VISION_MODEL", "")
    AI_VISION_MODEL_FALLBACK = os.environ.get("AI_VISION_MODEL_FALLBACK", "")
    AI_VISION_BASE_URL = os.environ.get("AI_VISION_BASE_URL", "")
    AI_VISION_API_KEY = os.environ.get("AI_VISION_API_KEY", "")
    # 第二视觉模型（可选，OpenAI 兼容），智谱失败后自动尝试。
    AI_VISION_2_MODEL = os.environ.get("AI_VISION_2_MODEL", "")
    AI_VISION_2_MODEL_FALLBACK = os.environ.get("AI_VISION_2_MODEL_FALLBACK", "")
    AI_VISION_2_BASE_URL = os.environ.get("AI_VISION_2_BASE_URL", "")
    AI_VISION_2_API_KEY = os.environ.get("AI_VISION_2_API_KEY", "")
    # 第三视觉模型（可选，OpenAI 兼容），用于多模型轮询。
    AI_VISION_3_MODEL = os.environ.get("AI_VISION_3_MODEL", "")
    AI_VISION_3_BASE_URL = os.environ.get("AI_VISION_3_BASE_URL", "")
    AI_VISION_3_API_KEY = os.environ.get("AI_VISION_3_API_KEY", "")
    AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "90"))


settings = Settings()
