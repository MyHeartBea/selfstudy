' Kaoyan mistakes launcher (backend + frontend), hidden window, idempotent.
Set shell = CreateObject("WScript.Shell")
ps1 = "C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\start_system.ps1"
shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """", 0, False
