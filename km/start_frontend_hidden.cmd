@echo off
rem Start frontend fully detached and hidden. Pure ASCII.
cd /d "C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\frontend"
start "" /b cmd /c "npm run dev > dev.out.log 2> dev.err.log"
