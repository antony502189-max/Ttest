# Performance optimization report

Baseline: `1a9c76bad9c8094a59ce912a1b8582e3493b8d77`.

## Frontend

The mobile code-splitting experiment was measured and rejected.

The aggressive variant reduced entry JavaScript but changed mobile lifecycle and stylesheet ordering. A safer partial variant restored correctness, but its production entry measured about 624.55 kB raw / 213.69 kB gzip versus the original 625,868 B raw / 211,258 B gzip. The raw change was negligible and gzip was worse.

The final candidate therefore restores `src/components/layout.tsx` and `src/main.tsx` to the approved baseline topology. Scoped `@radix-ui/*` runtime imports remain where APIs are equivalent.

## Backend

Listing coordinate projection now uses PostGIS `ST_X`/`ST_Y` instead of `ST_AsGeoJSON` plus Python JSON parsing while preserving response coordinates.

On a disposable PostGIS 3.4 database with 30,000 published listings, the isolated coordinate projection benchmark changed from 48.21 ms to 28.05 ms (41.8% lower). Average coordinate payload text changed from 58.8 B to 37.2 B (36.7% lower), with the same 1,287 shared buffers.

A proposed lightweight COUNT relation was rejected after measurement. Representative 30,000-row plans used the same 1,288 shared buffers and measured 21.75 ms for the existing shape versus 22.84 ms for the proposed rewrite.

Integration cleanup preserves PostGIS `spatial_ref_sys`; truncating it had caused subsequent radius searches to fail.

## Acceptance

Targeted checks covered frontend lint/typecheck/build, bundle checks, focused backend tests, migration-chain validation through `0033_admin_moderation`, and direct browser flows.

Merge acceptance requires Production audit, Full audit, Mobile validation, Audit Source Snapshot, and Capacity smoke safeguards to pass on the same final HEAD.

## Rejected changes

- Mobile lifecycle code splitting: no meaningful safe net bundle gain.
- COUNT rewrite: measured plan was not better.
- Global observer/gate rewrites: insufficient evidence to justify interaction risk.
- Speculative aggregation/index changes: no measured query-plan need.
