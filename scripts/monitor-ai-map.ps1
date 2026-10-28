param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$labOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
while (-not (Test-Path -LiteralPath (Join-Path $labOutput 'monitor.stop'))) {
    $labStats = docker stats codex-r01-db-20261028 --no-stream --format '{{json .}}' 2>$null
    if ($LASTEXITCODE -eq 0) {
        @{ at = [DateTime]::UtcNow.ToString('o'); db = ($labStats | ConvertFrom-Json) } |
            ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $labOutput 'resources.jsonl') -Encoding utf8
    }
    Start-Sleep -Seconds 5
}
