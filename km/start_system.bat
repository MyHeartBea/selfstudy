@echo off
chcp 65001 >nul
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_system.ps1"
timeout /t 2 /nobreak >nul
start http://localhost:5173
