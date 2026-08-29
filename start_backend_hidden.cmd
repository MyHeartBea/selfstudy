@echo off
rem 研错本后端无窗口启动（供自启动 vbs / WMI 调用）
cd /d "%~dp0backend"
start "km-backend" /min cmd /c "python main.py > ..\backend_out.log 2> ..\backend_err.log"
