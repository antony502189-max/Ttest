param(
    [ValidateSet('Prepare', 'Live')][string]$Action = 'Prepare',
    [string]$Approval = '',
    [string]$ApprovedCorpusSHA256 = '',
    [string]$TestKeyFile = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
if ((git branch --show-current) -ne 'codex/post-merge-remediation') { throw 'Use the existing audit branch' }
if (git status --porcelain --untracked-files=all) { throw 'Commit source first: evaluation uses exact clean HEAD' }
$source = git rev-parse HEAD
$image = 'ttest-ai-fact-population-tools:20261031'
$imageId = docker image inspect $image --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $imageId -ne 'sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902') {
    throw 'Pinned local dependency image is required; no image pull or package installation is performed'
}
$corpusSHA = (Get-FileHash -LiteralPath 'backend/lab/intent_cases.v1.json' -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Action -eq 'Live') {
    if ($Approval -ne 'deepseek-synthetic-intent-v1' -or $ApprovedCorpusSHA256 -ne $corpusSHA) {
        throw 'Live calls require explicit approval of this synthetic corpus, outbound payload and cost policy'
    }
    if (-not $TestKeyFile) { $TestKeyFile = Join-Path $repo '.env.ai-intent-eval.local' }
    $TestKeyFile = (Resolve-Path -LiteralPath $TestKeyFile).Path
    $keyLines = @(Get-Content -LiteralPath $TestKeyFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($keyLines.Count -ne 1 -or $keyLines[0] -notmatch '^AI_INTENT_EVAL_DEEPSEEK_KEY=\S+$') {
        throw 'Test key file must contain only AI_INTENT_EVAL_DEEPSEEK_KEY=<dedicated key>'
    }
    $keyLines = $null
}
$evidence = Join-Path $repo 'output/ai-intent-provider-v1'
$runId = 'run-' + [guid]::NewGuid().ToString('N')
$run = Join-Path $evidence $runId
$snapshot = Join-Path $run 'source'
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$archive = Join-Path $run 'source.tar'
git -c core.autocrlf=false archive --format=tar --output=$archive $source
if ($LASTEXITCODE -ne 0) { throw 'Source archive failed' }
tar -xf $archive -C $snapshot
if ($LASTEXITCODE -ne 0) { throw 'Source extraction failed' }
$snapshotCorpusSHA = (Get-FileHash -LiteralPath (Join-Path $snapshot 'backend/lab/intent_cases.v1.json') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($snapshotCorpusSHA -ne $corpusSHA) { throw 'Snapshot corpus mismatch' }
@{ source_sha = $source; image_id = $imageId; corpus_sha256 = $corpusSHA; action = $Action;
   source_tar_sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant();
   created_utc = [DateTime]::UtcNow.ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'source.json') -Encoding utf8
$dockerArgs = @('run', '--rm', '--name', "ttest-ai-intent-$runId", '--pull', 'never',
    '--label', 'es.ttest.purpose=ai-intent-provider-v1', '--label', "org.opencontainers.image.revision=$source",
    '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '64',
    '--memory', '512m', '--cpus', '1', '--tmpfs', '/tmp:rw,nosuid,size=64m',
    '--mount', "type=bind,source=$snapshot,target=/source,readonly",
    '--mount', "type=bind,source=$evidence,target=/evidence", '--workdir', '/source/backend',
    '--env', 'PYTHONPATH=/source/backend', '--env', 'PYTHONDONTWRITEBYTECODE=1')
if ($Action -eq 'Prepare') { $dockerArgs += @('--network', 'none') }
else { $dockerArgs += @('--network', 'bridge', '--env-file', $TestKeyFile) }
$dockerArgs += @($imageId, 'python', '-m', 'lab.intent_eval', '--output', "/evidence/$runId/result.json")
if ($Action -eq 'Live') {
    # Keep the SAME journal across runs/restarts. Creating/deleting it to reset
    # spending requires a new approval; no automatic reset/cleanup is provided.
    $dockerArgs += @('--live', '--approval', $Approval, '--approved-corpus-sha256', $ApprovedCorpusSHA256,
                     '--journal', '/evidence/budget.sqlite3')
}
& docker @dockerArgs
$resultCode = $LASTEXITCODE
Write-Output "Evidence: $run"
if ($resultCode -ne 0) { throw 'Evaluation failed or semantic acceptance did not pass; inspect sanitized result.json' }
