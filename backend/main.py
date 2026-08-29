"""研错本（km-v2）生产启动入口：单端口 8000，前端构建产物由后端挂载。"""

import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    # 单机应用默认只监听本机；如需局域网访问改为 0.0.0.0（注意无鉴权）
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
