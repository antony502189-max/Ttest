param(
    [Parameter(Mandatory)][ValidateSet('initialize','seed','measure')][string]$Phase,
    [ValidateRange(1,1000000)][int]$Total = 100000,
    [ValidateRange(1,200)][int]$Samples = 200,
    [ValidateRange(0,1000000)][Nullable[int]]$Candidate = $null,
    [switch]$BaselineOnly,
    [ValidateSet('baseline','fanout')][string]$Profile = 'baseline',
    [ValidatePattern('^[0-9a-f]{32}$')][string]$ExperimentId,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,47}$')][string]$LabId,
    [string]$DependencyImage = 'ttest-backend:latest',
    [ValidatePattern('^[0-9a-f]{32}$')][string]$RunId = ([guid]::NewGuid().ToString('N'))
)
$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($null -ne $Candidate -and $Candidate -gt $Total) { throw 'Candidate must not exceed Total' }
if (($null -ne $Candidate -or $BaselineOnly) -and $Phase -ne 'measure') { throw 'Candidate/BaselineOnly require measure' }
if ($null -ne $Candidate -and -not $BaselineOnly) { throw 'Candidate requires BaselineOnly' }
if (-not $ExperimentId) {
    if ($Phase -ne 'initialize') { throw 'Seed/measure require the initialized ExperimentId' }
    $ExperimentId = [guid]::NewGuid().ToString('N')
}
$labRevision = git -C $labRoot rev-parse --verify HEAD
if ($LASTEXITCODE -ne 0 -or $labRevision -notmatch '^[0-9a-f]{40}$') { throw 'Cannot resolve source revision' }
$labStatus = git -C $labRoot status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect source checkout' }
if ($labStatus) { throw 'Benchmark requires a clean checkout, including staged/unstaged/untracked files' }
$labProfileOutput = Join-Path $labRoot $(if ($Profile -eq 'fanout') { 'output/r01-fanout' } else { 'output/r01' })
$labOutput = Join-Path $labProfileOutput $ExperimentId
New-Item -ItemType Directory -Force -Path $labOutput | Out-Null
$labImage = docker image inspect $DependencyImage --format '{{.Id}}'
if ($LASTEXITCODE -ne 0) { throw 'Missing local backend dependency image' }
if ($labImage -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Expected immutable local runner image ID' }
# This launcher deliberately supports only this task's private internal lab.
$labSuffix = if ($LabId) { $LabId } elseif ($Profile -eq 'fanout') { 'fanout-20261028' } else { '20261028' }
$labRunnerSuffix = if ($LabId) { "-$LabId" } else { '' }
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
$labExpectedDbImage = docker image inspect 'mirror.gcr.io/postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5' --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $labExpectedDbImage -notmatch '^sha256:[0-9a-f]{64}$' -or $labDb.Image -ne $labExpectedDbImage) {
    throw 'Expected the pinned PostgreSQL 16 / PostGIS 3.4 image'
}
$labAttachment = $labDb.NetworkSettings.Networks.$labNetworkName
if ($labDb.Id -notmatch '^[0-9a-f]{64}$' -or -not $labDb.State.Running -or
    @($labDb.NetworkSettings.Networks.PSObject.Properties).Count -ne 1 -or
    -not $labAttachment -or $labAttachment.NetworkID -ne $labNetwork.Id -or
    $labAttachment.IPAddress -notmatch '^\d+\.\d+\.\d+\.\d+$' -or
    $labAttachment.Aliases -notcontains 'r01-db') {
    throw 'Expected DB attached exclusively to the exact internal network with r01-db alias'
}
# Resolve the DB's role/database/version inside this exact container before DDL.
$labIdentity = docker exec $labDb.Id psql -X -U r01 -d r01_synthetic -At -c "SELECT current_database() || '|' || current_user || '|' || current_setting('server_version_num') || '|' || postgis_lib_version()"
if ($LASTEXITCODE -ne 0 -or $labIdentity -notmatch '^r01_synthetic\|r01\|16[0-9]{4}\|3\.4\.[0-9]+$') {
    throw 'Unexpected synthetic database identity'
}
$labExtra = @()
if ($Phase -eq 'initialize') { $labExtra += @('--sources', $(if ($Profile -eq 'fanout') { '10' } else { '2' })) }
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
    git -C $labRoot -c core.autocrlf=false archive --format=tar --output=$labArchive $labRevision
    if ($LASTEXITCODE -ne 0) { throw 'Cannot export committed source' }
    $labArchiveHash = (Get-FileHash -LiteralPath $labArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $labExperimentPath = Join-Path $labOutput 'experiment.json'
    if (Test-Path -LiteralPath $labExperimentPath) {
        $labExperiment = Get-Content -Raw -LiteralPath $labExperimentPath | ConvertFrom-Json
        if ($labExperiment.experiment_id -ne $ExperimentId -or $labExperiment.code_revision -ne $labRevision -or
            $labExperiment.runner_image_id -ne $labImage -or $labExperiment.archive_sha256 -ne $labArchiveHash -or
            $labExperiment.db_container_id -ne $labDb.Id -or $labExperiment.db_image_id -ne $labDb.Image -or
            $labExperiment.sources -ne $(if ($Profile -eq 'fanout') { 10 } else { 2 })) {
            throw 'Immutable experiment provenance mismatch; create a new experiment and seed'
        }
    } elseif ($Phase -ne 'initialize') { throw 'Initialize the experiment before seed/measure' }
    tar -xf $labArchive -C $labSnapshot
    if ($LASTEXITCODE -ne 0) { throw 'Cannot extract committed source' }
Write-Output "ExperimentId=$ExperimentId RunId=$RunId Output=$labOutput"
docker run --rm --name "codex-r01-runner-$Profile$labRunnerSuffix" --network $labNetwork.Id --add-host "r01-db:$($labAttachment.IPAddress)" `
    --label codex.task=r01-synthetic --memory 2g --cpus 2 --read-only --tmpfs /tmp `
    -v "${labSnapshot}:/code:ro" -v "${labOutput}:/results" -w /code/backend `
    -e PYTHONPATH=/code/backend -e PYTHONDONTWRITEBYTECODE=1 -e R01_DISPOSABLE_LAB=synthetic-only -e R01_CODE_REVISION=$labRevision -e R01_IMAGE_ID=$labImage `
    -e R01_SOURCE_MODE=git-archive -e R01_CHECKOUT_CLEAN=true -e R01_SOURCE_ARCHIVE_SHA256=$labArchiveHash `
    -e R01_EXPERIMENT_ID=$ExperimentId -e R01_RUN_ID=$RunId -e R01_DB_ID=$($labDb.Id) -e R01_DB_IMAGE_ID=$($labDb.Image) `
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
