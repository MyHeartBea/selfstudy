' Kaoyan mistakes launcher (backend + frontend), hidden window, idempotent.
Set shell = CreateObject("WScript.Shell")
' 相对化：vbs 所在目录即项目根
ps1 = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\start_system.ps1"
shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """", 0, False
