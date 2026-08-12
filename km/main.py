"""一键启动入口：在项目根目录运行 python main.py。"""

import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
