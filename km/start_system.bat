@echo off
chcp 65001 >nul
cd /d %~dp0

start "考研错题本-后端" cmd /k "cd backend && python main.py"
timeout /t 2 /nobreak >nul
start "考研错题本-前端" cmd /k "cd frontend && npm run dev"
timeout /t 3 /nobreak >nul
start http://localhost:5173
