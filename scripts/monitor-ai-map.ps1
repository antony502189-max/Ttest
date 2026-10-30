param(
    [Parameter(Mandatory)][string]$OutputDirectory,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{32}$')][string]$RunId,
    [ValidateSet('baseline','fanout')][string]$Profile = 'baseline',
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,47}$')][string]$LabId,
    [ValidateRange(1,10)][int]$MaxConsecutiveFailures = 3,
    [ValidateRange(1,60)][int]$IntervalSeconds = 5
)
$ErrorActionPreference = 'Stop'
$labOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
$labSuffix = if ($LabId) { $LabId } elseif ($Profile -eq 'fanout') { 'fanout-20261028' } else { '20261028' }
$labDbName = "codex-r01-db-$labSuffix"
$labNetworkName = "codex-r01-$labSuffix"
$labMonitorId = [guid]::NewGuid().ToString('N')
$labExperiment = Get-Content -Raw -LiteralPath (Join-Path $labOutput 'experiment.json') | ConvertFrom-Json
$labDbId = $labExperiment.db_container_id
function Write-MonitorEvent($event) {
    $event.at = [DateTime]::UtcNow.ToString('o')
    $event.container = $labDbName
    $event.profile = $Profile
    $event.provenance = $labExperiment
    $event.run_id = $RunId
    $event.monitor_id = $labMonitorId
    $event.db_container_id = $labDbId
    $event | ConvertTo-Json -Depth 8 -Compress |
        Add-Content -LiteralPath (Join-Path $labOutput 'resources.jsonl') -Encoding utf8
}
if (Test-Path -LiteralPath (Join-Path $labOutput 'monitor.stop')) {
    Write-MonitorEvent @{kind='monitor-stop'; status='stopped'}
    return
}
try {
    $labRaw = docker inspect $labDbName 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'inspect failed' }
    $labDb = $labRaw | ConvertFrom-Json
    if ($labDb.Name -ne "/$labDbName" -or $labDb.Config.Labels.'codex.task' -ne 'r01-synthetic' -or
        $labDb.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $labNetworkName -or
        $labDb.Id -ne $labDbId -or $labDb.Image -ne $labExperiment.db_image_id -or
        $labExperiment.sources -ne $(if ($Profile -eq 'fanout') { 10 } else { 2 })) {
        throw 'container profile mismatch'
    }
    $labTemplatePath = Join-Path $labOutput 'template.json'
    if (Test-Path -LiteralPath $labTemplatePath) {
        $labTemplate = Get-Content -Raw -LiteralPath $labTemplatePath | ConvertFrom-Json
        $labSources = if ($Profile -eq 'fanout') { 10 } else { 2 }
        if ($labTemplate.sources -ne $labSources) { throw 'output profile mismatch' }
    }
} catch {
    Write-MonitorEvent @{kind='monitor-error'; category='profile-validation'; consecutive_failures=1}
    throw 'Cannot validate the synthetic monitor container/output profile'
}
Write-MonitorEvent @{kind='monitor-start'; interval_seconds=$IntervalSeconds}
$labFailures = 0
while (-not (Test-Path -LiteralPath (Join-Path $labOutput 'monitor.stop'))) {
    $labCategory = 'docker-stats-exit'
    try {
        $labRaw = docker stats $labDbId --no-stream --format '{{json .}}' 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'stats failed' }
        $labCategory = 'invalid-stats-json'
        if (-not $labRaw) { throw 'empty stats' }
        $labStats = $labRaw | ConvertFrom-Json
        foreach ($labField in @('CPUPerc','MemPerc')) {
            if ($labStats.$labField -notmatch '^\d+(\.\d+)?%$') { throw 'invalid percentage' }
        }
        if ([double]::Parse($labStats.MemPerc.TrimEnd('%'), [Globalization.CultureInfo]::InvariantCulture) -gt 100) {
            throw 'invalid memory percentage'
        }
        Write-MonitorEvent @{kind='sample'; db=$labStats}
        $labFailures = 0
    } catch {
        $labFailures++
        Write-MonitorEvent @{kind='monitor-error'; category=$labCategory; consecutive_failures=$labFailures}
        Write-Warning "Synthetic monitor failure: $labCategory ($labFailures/$MaxConsecutiveFailures)"
        if ($labFailures -ge $MaxConsecutiveFailures) {
            Write-MonitorEvent @{kind='monitor-stop'; status='failed'}
            throw 'Synthetic resource monitoring failed repeatedly'
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $labOutput 'monitor.stop'))) { Start-Sleep -Seconds $IntervalSeconds }
}
Write-MonitorEvent @{kind='monitor-stop'; status='stopped'}
