"""后端启动入口：python main.py 或 python -m uvicorn app.main:app --port 8000。"""

import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
