[CmdletBinding()]
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$PidFile = Join-Path $Root 'data\trafficvision-processes.json'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Run .\setup.ps1 first.' }
if (Test-Path -LiteralPath $PidFile) {
    Write-Warning 'A previous process record exists. Running stop.ps1 before starting cleanly.'
    & (Join-Path $Root 'stop.ps1')
}
$BackendLog = Join-Path $Root 'data\backend.log'
$FrontendLog = Join-Path $Root 'data\frontend.log'
$BackendErr = Join-Path $Root 'data\backend-error.log'
$FrontendErr = Join-Path $Root 'data\frontend-error.log'

$Backend = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $Root 'backend') -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErr -WindowStyle Hidden -PassThru
$Node = (Get-Command node.exe -ErrorAction Stop).Source
$Vite = Join-Path $Root 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $Vite)) { throw 'Frontend dependencies are missing. Run .\setup.ps1 first.' }
# Start Vite directly so the recorded PID is the actual long-running process,
# not npm.cmd (which can exit while leaving an orphaned node.exe on Windows).
$Frontend = Start-Process -FilePath $Node -ArgumentList @($Vite,'--host','127.0.0.1','--port','5173') -WorkingDirectory (Join-Path $Root 'frontend') -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErr -WindowStyle Hidden -PassThru
@{ backend = $Backend.Id; frontend = $Frontend.Id; started = (Get-Date).ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding utf8

$Ready = $false
for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
    try {
        $Response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        if ($Response.status -eq 'healthy') { $Ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $Ready) { throw "Backend did not become ready. Inspect $BackendErr" }
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
Write-Host 'TrafficVision is running:' -ForegroundColor Green
Write-Host '  Frontend http://127.0.0.1:5173'
Write-Host '  Backend  http://127.0.0.1:8000/docs'
Write-Host 'Use .\stop.ps1 to stop both services.'
