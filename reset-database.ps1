[CmdletBinding(SupportsShouldProcess)]
param()
$Root = (Resolve-Path -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$DataRoot = (Resolve-Path -LiteralPath (Join-Path $Root 'data')).Path
$Database = Join-Path $DataRoot 'trafficvision.db'
if (-not $Database.StartsWith($DataRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to remove a database outside the project data directory.' }
& (Join-Path $Root 'stop.ps1')
foreach ($Path in @($Database, "$Database-shm", "$Database-wal")) {
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
}
Write-Host 'Database reset. Uploaded videos and completed evidence were preserved.' -ForegroundColor Green

