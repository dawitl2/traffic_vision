[CmdletBinding()]
param()
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root 'data\trafficvision-processes.json'
if (-not (Test-Path -LiteralPath $PidFile)) { Write-Host 'TrafficVision is not recorded as running.'; exit 0 }
$Record = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json

function Stop-TrafficVisionProcessTree {
    param([int]$ProcessId)
    $Children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($Child in $Children) { Stop-TrafficVisionProcessTree -ProcessId $Child.ProcessId }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $ProcessId -Force
        Write-Host "Stopped process $ProcessId"
    }
}

foreach ($Id in @($Record.backend, $Record.frontend)) {
    if ($Id) { Stop-TrafficVisionProcessTree -ProcessId $Id }
}
Remove-Item -LiteralPath $PidFile -Force
