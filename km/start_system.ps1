# Kaoyan mistakes launcher - idempotent (backend + frontend).
# Safe to run repeatedly: if a port is already listening, that service is skipped.
# Uses wmic to create fully detached processes (survive this script's exit).
# NOTE: keep ASCII only - cmd reads this file in the system codepage.

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if (Test-Path 'D:\python\python.exe') { 'D:\python\python.exe' } else { 'python' }

function Test-PortListening([int]$port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Start-Detached([string]$workDir, [string]$command) {
    $cmdline = 'cmd /c cd /d "' + $workDir + '" && ' + $command
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmdline))
    wmic process call create $cmdline | Out-Null
}

# ---- backend FastAPI :8000 ----
if (-not (Test-PortListening 8000)) {
    wmic process call create "cmd /c cd /d $root\backend && $python main.py > server.log 2> server.err.log" | Out-Null
    Write-Host "[ok] backend started (127.0.0.1:8000)"
} else {
    Write-Host "[ok] backend already running, skip"
}

# ---- frontend Vite :5173 ----
if (-not (Test-PortListening 5173)) {
    wmic process call create "cmd /c cd /d $root\frontend && npm run dev > dev.out.log 2> dev.err.log" | Out-Null
    Write-Host "[ok] frontend started (localhost:5173)"
} else {
    Write-Host "[ok] frontend already running, skip"
}

Write-Host "[ok] done, open http://localhost:5173"
