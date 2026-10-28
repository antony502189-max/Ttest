param(
    [ValidateSet('initialize','seed','measure')][string]$Phase,
    [int]$Total = 100000,
    [int]$Samples = 200,
    [int]$Candidate = -1,
    [switch]$BaselineOnly,
    [ValidateSet('baseline','fanout')][string]$Profile = 'baseline'
)
$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$labOutput = Join-Path $labRoot $(if ($Profile -eq 'fanout') { 'output/r01-fanout' } else { 'output/r01' })
New-Item -ItemType Directory -Force -Path $labOutput | Out-Null
$labImageFile = Join-Path $labOutput 'runner-image-id.txt'
if (Test-Path -LiteralPath $labImageFile) {
    $labImage = (Get-Content -Raw -LiteralPath $labImageFile).Trim()
} else {
    $labImage = docker image inspect ttest-backend:latest --format '{{.Id}}'
    if ($LASTEXITCODE -ne 0) { throw 'Missing local backend dependency image' }
    Set-Content -LiteralPath $labImageFile -Value $labImage -Encoding utf8
}
if ($labImage -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Expected immutable local runner image ID' }
# This launcher deliberately supports only this task's private internal lab.
$labSuffix = if ($Profile -eq 'fanout') { 'fanout-20261028' } else { '20261028' }
$labNetworkName = "codex-r01-$labSuffix"
$labDbName = "codex-r01-db-$labSuffix"
$labNetwork = docker network inspect $labNetworkName | ConvertFrom-Json
if (-not $labNetwork.Internal -or $labNetwork.Labels.'codex.task' -ne 'r01-synthetic') {
    throw 'Expected the isolated synthetic-only network'
}
$labDb = docker inspect $labDbName | ConvertFrom-Json
if ($labDb.Config.Labels.'codex.task' -ne 'r01-synthetic' -or @($labDb.HostConfig.PortBindings.PSObject.Properties).Count -ne 0) {
    throw 'Expected disposable DB without published host ports'
}
$labExtra = @()
if ($Profile -eq 'fanout') { $labExtra += @('--sources','10') }
$labRevision = git -C $labRoot rev-parse HEAD
if ($Candidate -ge 0) { $labExtra += @('--candidate', "$Candidate") }
if ($BaselineOnly) { $labExtra += '--baseline-only' }
docker run --rm --name "codex-r01-runner-$Profile" --network $labNetworkName `
    --label codex.task=r01-synthetic --memory 2g --cpus 2 --read-only --tmpfs /tmp `
    -v "${labRoot}:/code:ro" -v "${labOutput}:/results" -w /code/backend `
    -e PYTHONPATH=/code/backend -e PYTHONDONTWRITEBYTECODE=1 -e R01_DISPOSABLE_LAB=synthetic-only -e R01_CODE_REVISION=$labRevision -e R01_IMAGE_ID=$labImage `
    -e APP_ENV=test -e DATABASE_URL=postgresql+asyncpg://r01:r01-synthetic-only@r01-db:5432/r01_synthetic `
    -e JWT_SECRET=r01-synthetic-secret-at-least-32-characters `
    -e EMAIL_VERIFICATION_HMAC_SECRET=r01-email-synthetic-secret-at-least-32-characters `
    -e REDIS_URL= -e STORAGE_BACKEND=local -e MEDIA_ROOT=/tmp/media -e FRONTEND_ORIGINS=http://127.0.0.1 `
    --entrypoint python $labImage /code/scripts/benchmark-ai-map.py $Phase --total $Total --samples $Samples @labExtra
if ($LASTEXITCODE -ne 0) { throw "Benchmark failed with exit code $LASTEXITCODE" }
