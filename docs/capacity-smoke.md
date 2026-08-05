# Bounded production capacity smoke

`scripts/capacity_smoke.py` provides a deliberately small, read-only check of an already deployed release. It is not a benchmark and does not establish the VPS's maximum capacity. Use it only after the normal production smoke and the scheduled backup/restore verification are green.

The tool fails closed unless all of the following are true:

- the target is the hard-coded production origin `https://app.112233.es`;
- HTTPS is used;
- the production hostname is resolved before the release lock, every resolved address is public, and requests are pinned to that address while preserving TLS SNI and the HTTP Host header;
- the shared production release lock is acquired, preventing overlap with deploy, rollback, backup or restore;
- `/srv/112233.es/current` resolves to a clean Git worktree at `/srv/112233.es/releases/<expected-sha>`, with the same HEAD and the expected `/srv/112233.es/repo/.git` common repository;
- the private `<sha>.deploy-info` file records the same SHA, a successful deployment, the final migration revision and application image IDs;
- the expected SHA is repeated explicitly as confirmation;
- only the fixed GET endpoints for live health, ready health and public listings are requested;
- redirects, environment proxies, cache reuse, non-JSON responses and responses above 64 KiB are rejected;
- requests, concurrency, start rate and timeout remain inside hard-coded limits.

Run it on the VPS against the public production origin after deploying a merged `main` SHA:

```bash
sha="$(basename "$(readlink -f /srv/112233.es/current)")"
python3 /srv/112233.es/current/scripts/capacity_smoke.py \
  --base-url "https://app.112233.es" \
  --allow-host "app.112233.es" \
  --expected-sha "$sha" \
  --confirm-sha "$sha" \
  --requests 120 \
  --concurrency 4 \
  --rate 8 \
  --timeout 5 \
  --min-success-rate 1.0 \
  --max-p95-ms 800
```

Save the JSON output with the release SHA and VPS monitoring data. Increase one parameter at a time and stop immediately if readiness, error rate, latency, CPU, memory, disk latency, PostgreSQL connections, Redis latency or MinIO health degrades. The hard ceiling is 300 total requests including three warm-up requests, concurrency 8, 20 request starts per second and a calculated worst-case release-lock duration of five minutes; use a dedicated load-testing plan outside this script for higher loads.

The GitHub workflow runs only local safeguard tests. It never contacts production.
