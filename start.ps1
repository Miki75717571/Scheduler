<#
.SYNOPSIS
    One-command dev startup for the Cafeteria Scheduler.

    Installs dependencies if needed, runs migrations, seeds a bootstrap admin
    account, starts the backend and frontend (each in their own window), and
    opens the app in your browser. No .env file, database server, or
    connection string required - see backend/app/core/config.py.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start.ps1

    (The -ExecutionPolicy Bypass is needed because Windows blocks running
    local .ps1 scripts by default; it only affects this one process, not your
    system-wide policy.)
#>

$ErrorActionPreference = "Stop"

# Resolve every path from this script's own location, not the current
# working directory - a relative path resolves differently depending on
# where you happen to run this from, which is exactly the class of bug this
# whole script exists to eliminate.
$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-LanIPAddress {
    # Best-effort LAN IPv4 for phone testing (see CLAUDE.md's "test it on a
    # real phone" requirement): the first non-loopback, non-link-local
    # (169.254.x.x) IPv4 address with a real gateway, i.e. an actual
    # Wi-Fi/Ethernet adapter rather than a virtual/host-only one.
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            -not $_.IPAddress.StartsWith("169.254.") -and
            (Get-NetRoute -InterfaceIndex $_.InterfaceIndex -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue)
        } |
        Select-Object -First 1
    if ($candidate) { return $candidate.IPAddress }
    return $null
}

function Test-PortOpen {
    # Queries the OS listener table directly rather than opening a probe
    # connection: uvicorn binds 127.0.0.1, but Vite's default `localhost`
    # resolves to the IPv6 loopback (::1) here, and a manual TcpClient
    # connect to "::1" was unreliable (silent false negatives) - this isn't.
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Start-DevWindow {
    # Launches PowerShell with -EncodedCommand (Base64) rather than -Command
    # with a hand-quoted string: Start-Process's -ArgumentList mangles
    # embedded quotes when building the child process's command line, which
    # silently corrupted `Set-Location -LiteralPath "<path with a space>"`
    # here - it parsed as several unquoted words instead of one path and
    # failed. Encoding sidesteps quoting entirely; there's nothing to mangle.
    param(
        [string]$WorkingDirectory,
        [string]$Command
    )
    $script = "Set-Location -LiteralPath `"$WorkingDirectory`"; $Command"
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($script))
    Start-Process -FilePath "powershell" -ArgumentList `
        "-ExecutionPolicy", "Bypass", "-NoExit", "-EncodedCommand", $encoded
}

# --- Prerequisites -----------------------------------------------------

Write-Step "Checking prerequisites"

if (-not (Test-CommandExists "python")) {
    Write-Host "Python was not found on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.12+ from https://www.python.org/downloads/ (tick 'Add python.exe to PATH' during install), then re-run this script." -ForegroundColor Red
    exit 1
}
if (-not (Test-CommandExists "node") -or -not (Test-CommandExists "npm")) {
    Write-Host "Node.js/npm was not found on PATH." -ForegroundColor Red
    Write-Host "Install Node.js 20+ from https://nodejs.org/, then re-run this script." -ForegroundColor Red
    exit 1
}

python -m uv --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing uv (Python package manager), for your user account only - no admin rights needed"
    python -m pip install --user --quiet uv
}

# --- Install + migrate + seed -------------------------------------------

Write-Step "Installing backend dependencies (uv sync)"
Push-Location -LiteralPath $BackendDir
python -m uv sync
Pop-Location

Write-Step "Installing frontend dependencies (npm install)"
Push-Location -LiteralPath $FrontendDir
npm install
Pop-Location

Write-Step "Running database migrations"
Push-Location -LiteralPath $BackendDir
python -m uv run alembic upgrade head
Pop-Location

Write-Step "Seeding admin account"
Push-Location -LiteralPath $BackendDir
python -m uv run python -m app.seed 2>&1 | Tee-Object -Variable seedOutput
Pop-Location

# --- Start backend + frontend --------------------------------------------

# Note on these child windows: `npm` on Windows resolves to npm.ps1, and a
# freshly spawned powershell.exe does NOT inherit the parent's execution
# policy - on a machine where the default policy is Restricted, that window
# would sit there silently refusing to run npm, with no process and no
# visible error. Start-DevWindow always passes -ExecutionPolicy Bypass itself.

Write-Step "Starting backend (http://localhost:8000)"
if (Test-PortOpen -Port 8000) {
    Write-Host "Something is already listening on port 8000 - assuming the backend is already running." -ForegroundColor Yellow
} else {
    Start-DevWindow -WorkingDirectory $BackendDir -Command "python -m uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"
}

Write-Step "Starting frontend (http://localhost:5173)"
if (Test-PortOpen -Port 5173) {
    Write-Host "Something is already listening on port 5173 - assuming the frontend is already running." -ForegroundColor Yellow
} else {
    Start-DevWindow -WorkingDirectory $FrontendDir -Command "npm run dev"
}

Write-Step "Waiting for the backend to respond"
$backendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $backendReady = $true; break }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($backendReady) {
    Write-Host "Backend is up." -ForegroundColor Green
} else {
    Write-Host "Backend did not respond within 30s - check the backend window for errors." -ForegroundColor Red
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

$lanIp = Get-LanIPAddress

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " Cafeteria Scheduler is running"
Write-Host ""
Write-Host " Frontend: http://localhost:5173"
Write-Host " Backend:  http://localhost:8000  (API docs at /docs)"
if ($lanIp) {
    Write-Host ""
    Write-Host " On your phone (same Wi-Fi as this PC): http://${lanIp}:5173" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host " Could not detect a LAN IP for phone testing - find yours with 'ipconfig'" -ForegroundColor Yellow
    Write-Host " (look for the IPv4 Address of your Wi-Fi/Ethernet adapter) and open" -ForegroundColor Yellow
    Write-Host " http://<that IP>:5173 on your phone." -ForegroundColor Yellow
}
Write-Host ""
foreach ($line in $seedOutput) {
    if ($line -match "Admin login") {
        Write-Host " $line"
    }
}
Write-Host ""
Write-Host " Backend and frontend are each running in their own window - close"
Write-Host " those windows (or Ctrl+C inside them) to stop the servers."
Write-Host " Re-run this script any time; it's safe to run repeatedly."
Write-Host "==================================================================" -ForegroundColor Green
