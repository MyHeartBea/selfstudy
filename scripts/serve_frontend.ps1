<#
  serve_frontend.ps1 -- switch the served frontend between v2 and v3 (about 10s, reversible any time).

  Why this works: backend/app/main.py has an SPA fallback route
  `GET /{full_path:path}` which serves whatever directory settings.FRONTEND_DIST points at,
  and that setting honours the FRONTEND_DIST entry in backend/.env.
  So switching frontends = edit one .env line + restart backend.
  No code change, no database change, data is shared by both versions.

  Usage:
    powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Target v3
    powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Target v2
    powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Status

  Safety:
  - refuses to switch to a target whose dist/index.html is missing (never serves an empty site)
  - backs up .env before editing, keeps every other line untouched
  - probes /api/health after restart; on failure it restores the backup and restarts again

  NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads .ps1 as ANSI
  when there is no BOM, which corrupts non-ASCII characters and breaks parsing.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [ValidateSet('v2', 'v3')]
  [string]$Target,

  [switch]$Status
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvFile = Join-Path $Root 'backend\.env'
$HealthUrl = 'http://127.0.0.1:8000/api/health'
$HomeUrl = 'http://127.0.0.1:8000/'

$Dists = @{
  v2 = (Join-Path $Root 'frontend\dist')
  v3 = (Join-Path $Root 'frontend-v3\dist')
}

function Get-EnvTarget {
  param([string]$Text)
  $re = [regex]'(?m)^\s*FRONTEND_DIST\s*=\s*"?([^"\r\n]+?)"?\s*$'
  if ($re.IsMatch($Text)) {
    $val = $re.Match($Text).Groups[1].Value.Replace('/', '\').Trim()
    foreach ($t in @('v2', 'v3')) {
      if ($val -eq $Dists[$t]) { return $t }
    }
    return 'custom'
  }
  return 'v2 (default: FRONTEND_DIST not set)'
}

function Restart-Backend {
  $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*main.py*' }
  foreach ($p in $procs) {
    Write-Host ("  stop backend pid " + $p.ProcessId) -ForegroundColor DarkGray
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 2
  $outLog = Join-Path $env:TEMP 'km-backend-out.log'
  $errLog = Join-Path $env:TEMP 'km-backend-err.log'
  Start-Process -FilePath 'python' -ArgumentList 'main.py' `
    -WorkingDirectory (Join-Path $Root 'backend') -WindowStyle Hidden `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
  Start-Sleep -Seconds 6
  return $errLog
}

if (-not (Test-Path $EnvFile)) { throw "backend/.env not found: $EnvFile" }
$envText = Get-Content $EnvFile -Raw -Encoding UTF8

if ($Status -or -not $Target) {
  Write-Host ("current frontend target: " + (Get-EnvTarget $envText)) -ForegroundColor Cyan
  foreach ($k in @('v2', 'v3')) {
    $ok = Test-Path (Join-Path $Dists[$k] 'index.html')
    $mark = '--'
    if ($ok) { $mark = 'OK' }
    Write-Host ("  [{0}] {1,-3} {2}" -f $mark, $k, $Dists[$k])
  }
  try {
    $h = Invoke-RestMethod $HealthUrl -TimeoutSec 8
    Write-Host ("  backend: " + $h.data.status + " v" + $h.data.version) -ForegroundColor Green
  } catch {
    Write-Host "  backend: no response" -ForegroundColor Yellow
  }
  return
}

$distPath = $Dists[$Target]
$indexFile = Join-Path $distPath 'index.html'
if (-not (Test-Path $indexFile)) {
  throw "refusing to switch: $Target build missing ($indexFile). Run: cd frontend-$Target && npm run build"
}

$backup = $EnvFile + '.bak-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item $EnvFile $backup
Write-Host ("backed up .env -> " + $backup) -ForegroundColor DarkGray

# Write forward slashes: dotenv style values are safer without backslash escapes.
$value = $distPath.Replace('\', '/')
if ([regex]::IsMatch($envText, '(?m)^\s*FRONTEND_DIST\s*=')) {
  $newText = [regex]::Replace($envText, '(?m)^\s*FRONTEND_DIST\s*=.*$', 'FRONTEND_DIST=' + $value)
} else {
  $newText = $envText.TrimEnd() + "`r`n`r`n# frontend dist (v2/v3 switch; see scripts/serve_frontend.ps1)`r`nFRONTEND_DIST=$value`r`n"
}
[System.IO.File]::WriteAllText($EnvFile, $newText, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ("FRONTEND_DIST -> " + $value) -ForegroundColor Cyan

$errLog = Restart-Backend

try {
  $h = Invoke-RestMethod $HealthUrl -TimeoutSec 15
  $home = Invoke-WebRequest $HomeUrl -TimeoutSec 15 -UseBasicParsing
  Write-Host ("switch OK: backend " + $h.data.status + " / home HTTP " + $home.StatusCode + " / now serving " + $Target) -ForegroundColor Green
  Write-Host "rollback: powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Target v2" -ForegroundColor DarkGray
} catch {
  Write-Host "health probe failed -- restoring .env and restarting" -ForegroundColor Red
  Copy-Item $backup $EnvFile -Force
  [void](Restart-Backend)
  Get-Content $errLog -Tail 15 -ErrorAction SilentlyContinue
  throw "switch failed, rolled back to previous config"
}
