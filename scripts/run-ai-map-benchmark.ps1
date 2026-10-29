param(
    [Parameter(Mandatory)][ValidateSet('initialize','seed','measure')][string]$Phase,
    [ValidateRange(1,1000000)][int]$Total = 100000,
    [ValidateRange(1,200)][int]$Samples = 200,
    [ValidateRange(0,1000000)][Nullable[int]]$Candidate = $null,
    [switch]$BaselineOnly,
    [ValidateSet('baseline','fanout')][string]$Profile = 'baseline'
)
$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($null -ne $Candidate -and $Candidate -gt $Total) { throw 'Candidate must not exceed Total' }
if (($null -ne $Candidate -or $BaselineOnly) -and $Phase -ne 'measure') { throw 'Candidate/BaselineOnly require measure' }
if ($null -ne $Candidate -and -not $BaselineOnly) { throw 'Candidate requires BaselineOnly' }
$labRevision = git -C $labRoot rev-parse --verify HEAD
if ($LASTEXITCODE -ne 0 -or $labRevision -notmatch '^[0-9a-f]{40}$') { throw 'Cannot resolve source revision' }
$labStatus = git -C $labRoot status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect source checkout' }
if ($labStatus) { throw 'Benchmark requires a clean checkout, including staged/unstaged/untracked files' }
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
$labNetworkRaw = docker network inspect $labNetworkName
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect lab network' }
$labNetwork = $labNetworkRaw | ConvertFrom-Json
if (-not $labNetwork.Internal -or $labNetwork.Labels.'codex.task' -ne 'r01-synthetic') {
    throw 'Expected the isolated synthetic-only network'
}
$labDbRaw = docker inspect $labDbName
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect lab container' }
$labDb = $labDbRaw | ConvertFrom-Json
if ($labDb.Config.Labels.'codex.task' -ne 'r01-synthetic' -or @($labDb.HostConfig.PortBindings.PSObject.Properties).Count -ne 0) {
    throw 'Expected disposable DB without published host ports'
}
if ($labDb.HostConfig.NanoCpus -ne 8000000000 -or $labDb.HostConfig.Memory -ne 8589934592) {
    throw 'Expected the recorded 8 CPU / 8 GiB DB lab limits'
}
$labExtra = @()
if ($Profile -eq 'fanout') { $labExtra += @('--sources','10') }
if ($null -ne $Candidate) { $labExtra += @('--candidate', "$Candidate") }
if ($BaselineOnly) { $labExtra += '--baseline-only' }
# Export committed bytes so ignored files and later checkout edits cannot
# change the runtime. Results stay outside the disposable source snapshot.
$labSnapshotParent = Join-Path ([IO.Path]::GetTempPath()) ('r01-source-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $labSnapshotParent | Out-Null
try {
    $labArchive = Join-Path $labSnapshotParent 'source.tar'
    $labSnapshot = Join-Path $labSnapshotParent 'code'
    New-Item -ItemType Directory -Path $labSnapshot | Out-Null
    git -C $labRoot archive --format=tar --output=$labArchive $labRevision
    if ($LASTEXITCODE -ne 0) { throw 'Cannot export committed source' }
    $labArchiveHash = (Get-FileHash -LiteralPath $labArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    tar -xf $labArchive -C $labSnapshot
    if ($LASTEXITCODE -ne 0) { throw 'Cannot extract committed source' }
docker run --rm --name "codex-r01-runner-$Profile" --network $labNetworkName `
    --label codex.task=r01-synthetic --memory 2g --cpus 2 --read-only --tmpfs /tmp `
    -v "${labSnapshot}:/code:ro" -v "${labOutput}:/results" -w /code/backend `
    -e PYTHONPATH=/code/backend -e PYTHONDONTWRITEBYTECODE=1 -e R01_DISPOSABLE_LAB=synthetic-only -e R01_CODE_REVISION=$labRevision -e R01_IMAGE_ID=$labImage `
    -e R01_SOURCE_MODE=git-archive -e R01_CHECKOUT_CLEAN=true -e R01_SOURCE_ARCHIVE_SHA256=$labArchiveHash `
    -e APP_ENV=test -e DATABASE_URL=postgresql+asyncpg://r01:r01-synthetic-only@r01-db:5432/r01_synthetic `
    -e JWT_SECRET=r01-synthetic-secret-at-least-32-characters `
    -e EMAIL_VERIFICATION_HMAC_SECRET=r01-email-synthetic-secret-at-least-32-characters `
    -e REDIS_URL= -e STORAGE_BACKEND=local -e MEDIA_ROOT=/tmp/media -e FRONTEND_ORIGINS=http://127.0.0.1 `
    --entrypoint python $labImage /code/scripts/benchmark-ai-map.py $Phase --total $Total --samples $Samples @labExtra
if ($LASTEXITCODE -ne 0) { throw "Benchmark failed with exit code $LASTEXITCODE" }
} finally {
    $labResolvedSnapshot = (Resolve-Path -LiteralPath $labSnapshotParent).Path
    $labTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $labResolvedSnapshot.StartsWith($labTempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $labResolvedSnapshot) -notmatch '^r01-source-[0-9a-f]{32}$') {
        throw 'Refusing cleanup outside the task snapshot directory'
    }
    Remove-Item -LiteralPath $labResolvedSnapshot -Recurse -Force
}
