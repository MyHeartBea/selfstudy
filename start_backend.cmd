@echo off
rem 研错本（km-v2）后端一键启动：生产模式单端口 8000
cd /d "%~dp0backend"
start "km-v2-backend" /min cmd /c "python main.py > ..\backend_out.log 2> ..\backend_err.log"
echo km-v2 backend starting on http://127.0.0.1:8000 ...
