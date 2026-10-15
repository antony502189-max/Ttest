# Security baseline — 15 October 2026

Scope: owner-authorized source review, isolated synthetic tests, and read-only
production assessment. Repository: https://github.com/antony502189-max/Ttest.
No production settings, services, data, DNS, financial provider objects or
credentials were modified. No PR was merged or deployed.

## Independently observed release identity

| Surface | Observed identity |
|---|---|
| Remote main | `8625775cafdd8ca58086a55294fc5f2309ccbe2b` |
| Production current symlink and Git HEAD | Same full SHA; checkout clean |
| Public build-info.json | Same full SHA |
| Backend release setting | Same full SHA |
| Applied Alembic head | `0063_financial_inbox_receipts` |
| Recorded previous release | `24047b6181dab5ba81fd66bd4b4781fa282b50fc` |
| Previous recorded schema | `0056_external_scope_checkpoint` |

The server deployment metadata records success. Public HTML returned 200,
HTTP redirected to HTTPS, backend readiness returned `status=ok`. These are
point-in-time observations, not a sustained error-rate or latency measurement.
No artificial production benchmark or vulnerability scan was run.

Initial desktop checkout was detached at `adc48435`; fetch failed because of
broken internal Codex checkpoint references. A clean single-branch clone was
created beside that checkout; the original Git references were not repaired or
deleted. Work is in `codex/security-boundaries-2026-10-15`, based on the separate
dependency branch `codex/security-dependency-pins-2026-10-15`.

## Repository governance

Repository is public. Main protection enforces admins, strict required checks
`snapshot`, `safeguards`, `frontend-static`, `backend-production`, `validate`,
`full-audit`; approving-review count is **zero**, code-owner reviews are not
required, stale reviews are dismissed. Owner approval remains mandatory under
this audit's instructions even though GitHub does not require a reviewer.
No CODEOWNERS file was found. Remote branches and 12 existing open PRs were
inventoried locally without changing them. Payment PR #332 and its audit and
release-compatibility documents were reviewed; its checks were successful.

Current workflows pin remote Actions to commit SHAs, use contents:read by
default and disable checkout credential persistence. Some UI-baseline/Pages
workflows intentionally have write permissions; those are reviewed separately
from application deployment. No production deployment was triggered.

## Host baseline

Ubuntu 24.04.5 LTS, kernel 6.8.0-146-generic; Docker 29.8.2, Compose 5.6.0.
Uptime approximately 8 days 21 hours. Host has about 18 GiB RAM, 15 GiB
available; root filesystem 8% used, inodes 1% used. These are observations,
not capacity guarantees. A reboot-required marker exists; unattended upgrades
are active. Package backlog and kernel CVE applicability are not established.

Public host listeners: 22, 80 and 443 on IPv4 and IPv6. PostgreSQL, Redis,
MinIO and FastAPI have no host-published ports. UFW is active with default
incoming/routed deny and intended SSH/HTTP/HTTPS allowances; Docker forwarding
chains were inspected. Neither ruleset was changed. No independent external
IPv6 reachability scan or provider-console verification was performed.

All application/data containers were healthy except the external importer.
Its heartbeat is current but its recorded health is failed; last success was
14 October 08:06 UTC. Mail worker is healthy. Production Stripe secret and
webhook keys are absent in both env-file classification and running backend;
live flag is false and payment-order table count is zero. No other environment's
Stripe credentials were enumerated.

Production environment permissions are 0600 root-owned; backup directory is
0700. Secret values were never printed or copied. Raw sanitized command
results remain in ignored local `output/` and are not uploaded in PRs.

## Limitations

No Contabo console, Google/Stripe dashboard, DNS provider, off-site storage,
customer account or live payment test was used. Existing restore-evidence
filenames were found dated 6 October; their contents and restoration outcome
were not validated. Latest archives' HMACs pass; this does not prove restore.
Historical production error rates and percentiles are unknown. The ASVS matrix
explicitly distinguishes verified slices from untested requirements.
