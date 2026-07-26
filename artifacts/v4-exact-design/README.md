# V4 exact-design evidence

- `target/` — normalized target frames from the V4 corpus.
- `before/` and `after/` — fresh live captures before and after V4.
- `boards/` — TARGET | AFTER-V2 | BEFORE-V4 | AFTER-V4.
- `overlays/` — 50% alpha overlays of TARGET and AFTER-V4.
- `diffs/` — contrast-enhanced unmasked difference heatmaps.
- `masks/` — documented allowed content-only masks; not applied to boards or reported RGB differences.
- `reports/sequence-review/` — ±2.5 s sequence plus crop review for every golden state.
- `reports/geometry/` — captured layout geometry and overflow diagnostics.
- `reports/supplemental/` — responsive and non-golden product-route matrix.
- `reports/acceptance.csv` — per-golden manual review status and artifact paths.
- `reports/final-acceptance-checklist.md` — final acceptance record.
