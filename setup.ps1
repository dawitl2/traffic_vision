[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "TrafficVision setup: $Root" -ForegroundColor Cyan

function Require-Command([string]$Name, [string]$Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw $Message }
}

Require-Command 'py' 'Python 3.12 is required. Install it with: winget install Python.Python.3.12'
Require-Command 'node' 'Node.js 20 LTS or newer is required. Install it with: winget install OpenJS.NodeJS.LTS'
Require-Command 'npm' 'npm was not found with Node.js.'
$NodeMajor = [int]((node --version).TrimStart('v').Split('.')[0])
if ($NodeMajor -lt 20) { throw 'Node.js 20 or newer is required for the pinned frontend toolchain.' }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host 'Installing FFmpeg for the current user...'
        winget install --id Gyan.FFmpeg --exact --scope user --silent --accept-package-agreements --accept-source-agreements
        Write-Warning 'If FFmpeg is still missing, close and reopen the terminal so PATH refreshes.'
    } else {
        Write-Warning 'FFmpeg is missing and winget is unavailable. Video probing will use the OpenCV fallback.'
    }
}

$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { py -3.12 -m venv (Join-Path $Root 'backend\.venv') }
& $Python -m pip install --upgrade pip
$Requirements = if (Test-Path -LiteralPath (Join-Path $Root 'backend\requirements.txt')) { 'requirements.txt' } else { 'requirements.in' }
Push-Location (Join-Path $Root 'backend')
try { & $Python -m pip install -r $Requirements } finally { Pop-Location }

Push-Location (Join-Path $Root 'frontend')
try { npm install } finally { Pop-Location }

if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) { Copy-Item -LiteralPath (Join-Path $Root '.env.example') -Destination (Join-Path $Root '.env') }
Write-Host 'Setup complete. Run .\start.ps1' -ForegroundColor Green
