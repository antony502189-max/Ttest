param(
    [ValidateSet('initialize','seed','measure')][string]$Phase,
    [int]$Total = 100000,
    [int]$Samples = 200,
    [int]$Candidate = -1,
    [switch]$BaselineOnly
)
$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$labOutput = Join-Path $labRoot 'output/r01'
New-Item -ItemType Directory -Force -Path $labOutput | Out-Null
# This launcher deliberately supports only this task's private internal lab.
$labNetwork = docker network inspect codex-r01-20261028 | ConvertFrom-Json
if (-not $labNetwork.Internal -or $labNetwork.Labels.'codex.task' -ne 'r01-synthetic') {
    throw 'Expected the isolated synthetic-only network'
}
$labDb = docker inspect codex-r01-db-20261028 | ConvertFrom-Json
if ($labDb.Config.Labels.'codex.task' -ne 'r01-synthetic' -or @($labDb.HostConfig.PortBindings.PSObject.Properties).Count -ne 0) {
    throw 'Expected disposable DB without published host ports'
}
$labExtra = @()
$labRevision = git -C $labRoot rev-parse HEAD
if ($Candidate -ge 0) { $labExtra += @('--candidate', "$Candidate") }
if ($BaselineOnly) { $labExtra += '--baseline-only' }
docker run --rm --name codex-r01-runner --network codex-r01-20261028 `
    --label codex.task=r01-synthetic --memory 2g --cpus 2 --read-only --tmpfs /tmp `
    -v "${labRoot}:/code:ro" -v "${labOutput}:/results" -w /code/backend `
    -e PYTHONPATH=/code/backend -e PYTHONDONTWRITEBYTECODE=1 -e R01_DISPOSABLE_LAB=synthetic-only -e R01_CODE_REVISION=$labRevision `
    -e APP_ENV=test -e DATABASE_URL=postgresql+asyncpg://r01:r01-synthetic-only@r01-db:5432/r01_synthetic `
    -e JWT_SECRET=r01-synthetic-secret-at-least-32-characters `
    -e EMAIL_VERIFICATION_HMAC_SECRET=r01-email-synthetic-secret-at-least-32-characters `
    -e REDIS_URL= -e STORAGE_BACKEND=local -e MEDIA_ROOT=/tmp/media -e FRONTEND_ORIGINS=http://127.0.0.1 `
    --entrypoint python ttest-backend:latest /code/scripts/benchmark-ai-map.py $Phase --total $Total --samples $Samples @labExtra
if ($LASTEXITCODE -ne 0) { throw "Benchmark failed with exit code $LASTEXITCODE" }
