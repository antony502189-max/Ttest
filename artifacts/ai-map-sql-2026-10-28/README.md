# R-01 evidence — 2026-10-28

These are historical measurements of the **original OR-based SQL**, before the
indexed authority-ID fix. The owner stopped large tests and requested correcting
the SQL first. 100k and 500k completed; 1m setup stopped at 900k and has no load
results. The new SQL has small correctness/access-plan regressions, not a claimed
post-fix load/SLO result.

- [Report in Russian](../../docs/ai-search-developer/MAP_CAPACITY_RESULTS_RU.md)
- [Protocol](../../docs/ai-search-developer/MAP_CAPACITY_PROTOCOL.md)
- [Scenario summaries](summary.json)
- [Raw evidence ZIP](evidence.zip) and [SHA-256](evidence.zip.sha256)

The ZIP contains raw attempts, actual/estimated-only plans clearly distinguished,
dataset counts/settings/versions, resource samples, cancellation checks, source
hash verification, executed source snapshots and current fix/test sources.
`manifest.json` hashes each member. All eight measured application/harness source
hashes were reproduced from the recorded Git revisions (including Windows line
endings where applicable). Synthetic DB contents and executable dependency images
are not included. No real database, provider, source site or notification was used.

`pool_ms` is checkout plus transaction-setup round trip; `query_ms` includes
repository work and failed-transaction cleanup. Failed completion-time quantiles
are not successful SQL latency percentiles. The report deliberately does not
extrapolate throughput, production capacity or the unmeasured million scale.
