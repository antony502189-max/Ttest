param([string]$Root, [string]$Mode, [string]$CommandText)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force "$root/output" | Out-Null
$global:statsCalls = 0
function Start-Sleep { }
if ($Mode -eq 'git_error') {
    function git { $global:LASTEXITCODE = 1 }
}
function docker {
    $a = @($args)
    Add-Content "$root/output/docker-calls.txt" $a[0]
    $global:LASTEXITCODE = 0
    switch ($a[0]) {
        'image' { 'sha256:' + ('a' * 64) }
        'network' { '{"Internal":true,"Labels":{"codex.task":"r01-synthetic"}}' }
        'inspect' {
            $name = if ($Mode -eq 'wrong_profile') { '/codex-r01-db-fanout-20261028' } else { '/codex-r01-db-20261028' }
            @{ Name=$name; Config=@{Labels=@{'codex.task'='r01-synthetic'}};
               HostConfig=@{PortBindings=@{}; NanoCpus=8000000000; Memory=8589934592};
               NetworkSettings=@{Networks=@{'codex-r01-20261028'=@{}}} } | ConvertTo-Json -Depth 6 -Compress
        }
        'run' {
            $mount = $a | Where-Object { $_ -like '*:/code:ro' } | Select-Object -First 1
            $snapshot = $mount.Substring(0, $mount.Length - ':/code:ro'.Length)
            $hash = $a | Where-Object { $_ -like 'R01_SOURCE_ARCHIVE_SHA256=*' } | Select-Object -First 1
            $clean = $a | Where-Object { $_ -like 'R01_CHECKOUT_CLEAN=*' } | Select-Object -First 1
            if ($hash.Split('=',2)[1] -ne (Get-FileHash (Join-Path (Split-Path $snapshot) 'source.tar')).Hash.ToLowerInvariant()) {
                throw 'Archive hash does not match metadata'
            }
            if ($Mode -eq 'concurrent_edit') { Set-Content "$root/tracked.py" '# changed after export' }
            @{ snapshot=$snapshot; content=(Get-Content -Raw "$snapshot/tracked.py");
               archive_hash=$hash.Split('=',2)[1]; checkout_clean=$clean.Split('=',2)[1] } |
                ConvertTo-Json | Set-Content "$root/output/mounted-source.json"
        }
        'stats' {
            $global:statsCalls++
            if ($Mode -eq 'error' -or ($Mode -eq 'recover' -and $global:statsCalls -eq 1)) {
                $global:LASTEXITCODE = 1; return
            }
            if ($Mode -eq 'malformed') { 'broken json'; return }
            if ($Mode -eq 'empty') { return }
            if ($Mode -eq 'missing_fields') { '{}'; return }
            New-Item -ItemType File -Force "$root/output/monitor/monitor.stop" | Out-Null
            '{"CPUPerc":"2%","MemPerc":"3%"}'
        }
        default { throw 'Unexpected fake Docker command' }
    }
}
Invoke-Expression $CommandText
