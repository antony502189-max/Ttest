# Direct publication production fix — 2026-09-10

## Problem

Production forced `AUTO_PUBLISH_LISTINGS=false`. Owner-created listings therefore entered `pending` and appeared as `Pendiente` / `На проверке` instead of becoming public immediately.

## Production contract

- owner create publishes directly to `published`;
- owner republish/renew resolves directly to `published` because production runs with auto publication enabled;
- production runtime validation rejects `AUTO_PUBLISH_LISTINGS=false`;
- the production compose file hardcodes `AUTO_PUBLISH_LISTINGS=true`;
- live internal, non-deleted, non-expired rows left in `pending` by the old production behavior are repaired to `published` by Alembic migration `0041_direct_publish_pending`;
- the migration records a `pending -> published` history row per repaired listing and bumps `catalog_state` so public consumers refetch.

Administrative moderation/restriction tools remain available as post-publication safety controls. They are no longer a required owner publication gate.

## Verification

Regression coverage checks both the production runtime invariant and the migration contract. Full CI must also run the normal backend, browser, migration and production-audit suites before merge.
