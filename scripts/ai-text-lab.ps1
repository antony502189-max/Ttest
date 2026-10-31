param(
    [ValidateSet('start', 'seed', 'status', 'stop')][string]$Action = 'status',
    [string]$BackendBase = 'ttest-main-audit-backend:7d4c1255',
    [string]$FrontendBase = 'ttest-main-audit-frontend:7d4c1255'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$labMutex = [System.Threading.Mutex]::new($false, 'ttest-ai-text-lab-launcher-v1')
if (-not $labMutex.WaitOne(0)) { throw 'Another lab launcher is still running; wait for its completion.' }
try {
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed ($LASTEXITCODE)" }
}
$purpose = 'ai-text-synthetic-lab-v1'
# Check ownership BEFORE any Compose mutation, including volume initialization.
foreach ($name in @('postgres', 'redis', 'backend', 'frontend')) {
    $full = "ttest-ai-text-lab-$name"
    $raw = & docker container inspect $full 2>$null
    if ($LASTEXITCODE -eq 0) {
        $item = ($raw | ConvertFrom-Json)[0]
        if ($item.Config.Labels.'es.ttest.purpose' -ne $purpose) { throw "Foreign container: $full" }
    }
}
foreach ($name in @('pg', 'redis', 'tls', 'media')) {
    $version = if ($name -eq 'pg') { 'v2' } else { 'v1' }
    $full = "ttest-ai-text-lab-$name-$version"
    $raw = & docker volume inspect $full 2>$null
    if ($LASTEXITCODE -eq 0 -and ($raw | ConvertFrom-Json)[0].Labels.'es.ttest.purpose' -ne $purpose) {
        throw "Foreign volume: $full"
    }
}
foreach ($network in @('ttest-ai-text-lab-network', 'ttest-ai-text-lab-loopback')) {
    $raw = & docker network inspect $network 2>$null
    if ($LASTEXITCODE -eq 0 -and ($raw | ConvertFrom-Json)[0].Labels.'es.ttest.purpose' -ne $purpose) {
        throw "Foreign lab network: $network"
    }
}
$stateDir = Join-Path $root 'output/ai-text-lab'
$stateFile = Join-Path $stateDir 'source.json'
if ($Action -eq 'start') {
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit all changes first: lab starts from an immutable git archive HEAD.' }
    $sha = (& git rev-parse HEAD).Trim()
    $snapshot = Join-Path $stateDir $sha
    New-Item -ItemType Directory -Force -Path $snapshot | Out-Null
    $archive = Join-Path $stateDir "$sha.tar"
    Invoke-Checked git @('archive', '--format=tar', '-o', $archive, $sha)
    Invoke-Checked tar @('-xf', $archive, '-C', $snapshot)
    # Dependencies are reused, application inputs come from the frozen archive.
    if (-not (Test-Path (Join-Path $snapshot 'node_modules'))) {
        New-Item -ItemType Junction -Path (Join-Path $snapshot 'node_modules') -Target (Join-Path $root 'node_modules') | Out-Null
    }
    $env:VITE_API_BASE_URL = '/api/v1'
    $env:VITE_ENABLE_MOCK_MODE = '0'
    $env:VITE_BASE_PATH = '/'
    $env:VITE_GOOGLE_MAPS_API_KEY = ''
    $env:VITE_GOOGLE_MAPS_MAP_ID = ''
    $env:VITE_GOOGLE_MAPS_TEST_SDK = '0'
    $env:VITE_GOOGLE_CLIENT_ID = ''
    Push-Location -LiteralPath $snapshot
    try {
        Invoke-Checked node @('node_modules/typescript/bin/tsc', '-b')
        Invoke-Checked node @('node_modules/vite/bin/vite.js', 'build', '--mode', 'ai-synthetic-lab', '--outDir', 'output/lab-dist')
    }
    finally { Pop-Location }
    @{ source = $sha; parser = 'synthetic-exact-phrases-v1'; mockApi = $false } | ConvertTo-Json |
        Set-Content -Encoding utf8 -LiteralPath (Join-Path $snapshot 'output/lab-dist/build-info.json')
    @{ source = $sha; snapshot = $snapshot; backendBase = $BackendBase; frontendBase = $FrontendBase } |
        ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $stateFile
}
if (-not (Test-Path -LiteralPath $stateFile)) { throw 'No lab source record; run start first.' }
$state = Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
$env:LAB_SOURCE_SHA = $state.source
$env:LAB_BACKEND_BASE = $state.backendBase
$env:LAB_FRONTEND_BASE = $state.frontendBase
$compose = @('compose', '--project-name', 'ttest-ai-text-lab', '-f', (Join-Path $state.snapshot 'deploy/ai-text-lab/compose.yml'))
switch ($Action) {
    'start' {
        Invoke-Checked docker ($compose + @('build'))
        # Stable labels: Compose must never recreate persistent synthetic data
        # because a source SHA changed. The launcher owns their lifecycle.
        foreach ($name in @('pg', 'redis', 'tls', 'media')) {
            $version = if ($name -eq 'pg') { 'v2' } else { 'v1' }
            $volume = "ttest-ai-text-lab-$name-$version"
            & docker volume inspect $volume *> $null
            if ($LASTEXITCODE -ne 0) {
                Invoke-Checked docker @('volume', 'create', '--label', "es.ttest.purpose=$purpose", $volume)
            }
        }
        foreach ($network in @('ttest-ai-text-lab-network', 'ttest-ai-text-lab-loopback')) {
            & docker network inspect $network *> $null
            if ($LASTEXITCODE -ne 0) {
                $options = @('network', 'create', '--label', "es.ttest.purpose=$purpose")
                if ($network -eq 'ttest-ai-text-lab-network') { $options += '--internal' }
                Invoke-Checked docker ($options + $network)
            }
        }
        Invoke-Checked docker ($compose + @('up', '-d', '--wait', '--wait-timeout', '60', 'postgres', 'redis'))
        Invoke-Checked docker ($compose + @('run', '--rm', '--no-deps', '--user', 'root', 'backend', 'python', '-c',
            "import os,pwd; u=pwd.getpwnam('app'); os.chown('/app/var/lab-media',u.pw_uid,u.pw_gid)"))
        Invoke-Checked docker ($compose + @('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'lab.certificate'))
        Invoke-Checked docker ($compose + @('run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', 'head'))
        Invoke-Checked docker ($compose + @('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'lab.seed_ai_text'))
        Invoke-Checked docker ($compose + @('up', '-d', '--wait', '--wait-timeout', '60', 'backend', 'frontend'))
        Write-Output "Synthetic lab: https://localhost:9443 ; source $($state.source)"
    }
    'seed' { Invoke-Checked docker ($compose + @('run', '--rm', '--no-deps', 'backend', 'python', '-m', 'lab.seed_ai_text')) }
    'status' {
        Get-Content -LiteralPath $stateFile
        Invoke-Checked docker ($compose + @('ps', '--all'))
        Invoke-Checked docker ($compose + @('exec', '-T', 'postgres', 'psql', '-U', 'ai_lab', '-d', 'ai_text_lab', '-c',
            'SELECT version_num FROM alembic_version; SELECT count(*) AS listings FROM listings; SELECT count(*) AS proofs FROM ai_query_proofs;'))
    }
    'stop' { Invoke-Checked docker ($compose + @('stop')) }
}
} finally {
    $labMutex.ReleaseMutex()
    $labMutex.Dispose()
}
