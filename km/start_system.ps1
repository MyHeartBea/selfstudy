# Kaoyan mistakes launcher - idempotent (backend + frontend).
# Safe to run repeatedly: if a port is already listening, that service is skipped.

$ErrorActionPreference = 'SilentlyContinue'
# 相对化：脚本所在目录即项目根，仓库迁移无需改路径
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# 优先本机已知 Python，找不到时回退 PATH
$python = if (Test-Path 'D:\python\python.exe') { 'D:\python\python.exe' } else { 'python' }

function Test-PortListening([int]$port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# ---- backend FastAPI :8000 ----
if (-not (Test-PortListening 8000)) {
    Start-Process -FilePath $python -ArgumentList 'main.py' -WorkingDirectory "$root\backend" `
        -RedirectStandardOutput "$root\backend\server.log" `
        -RedirectStandardError "$root\backend\server.err.log" `
        -WindowStyle Hidden
    Write-Host "[ok] backend started (127.0.0.1:8000)"
} else {
    Write-Host "[ok] backend already running, skip"
}

# ---- frontend Vite :5173 ----
if (-not (Test-PortListening 5173)) {
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' -WorkingDirectory "$root\frontend" `
        -RedirectStandardOutput "$root\frontend\dev.out.log" `
        -RedirectStandardError "$root\frontend\dev.err.log" `
        -WindowStyle Hidden
    Write-Host "[ok] frontend started (localhost:5173)"
} else {
    Write-Host "[ok] frontend already running, skip"
}

Write-Host "[ok] done, open http://localhost:5173"
