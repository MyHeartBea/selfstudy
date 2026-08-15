@echo off
rem Start backend fully detached and hidden. Pure ASCII.
cd /d "C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\backend"
start "" /b "D:\python\python.exe" main.py > server.log 2> server.err.log
