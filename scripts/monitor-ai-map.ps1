param([string]$OutputDirectory, [ValidateSet('baseline','fanout')][string]$Profile = 'baseline')
$ErrorActionPreference = 'Stop'
$labOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
$labDbName = if ($Profile -eq 'fanout') { 'codex-r01-db-fanout-20261028' } else { 'codex-r01-db-20261028' }
while (-not (Test-Path -LiteralPath (Join-Path $labOutput 'monitor.stop'))) {
    $labStats = docker stats $labDbName --no-stream --format '{{json .}}' 2>$null
    if ($LASTEXITCODE -eq 0) {
        @{ at = [DateTime]::UtcNow.ToString('o'); db = ($labStats | ConvertFrom-Json) } |
            ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $labOutput 'resources.jsonl') -Encoding utf8
    }
    Start-Sleep -Seconds 5
}
