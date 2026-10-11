# Monthly price cap — preserve PR #298 design and Tourism inventory

> **Historical planning and read-only classification record.** Do not treat observed environment flags or rollout status from this document as the **current** VPS state. The current application retains both `long`/`holiday` modes and applies the inclusive €1,000/month cap to long-term listings only. Source of truth: [database](../database.md), [external import](../external-import.md), and [production operations](../production-operations.md). Ordinary code releases **do not** perform catalog cleanup or gallery repairs.

## Verified baseline and scope
The customer explicitly corrected the scope: **do not redesign the marketplace**, keep the current PR #298 / #303 UI, both `Vivienda` and `Turismo` mode cards, their original colors, search navigation and property galleries. Do not redirect existing tourist mode to long-term mode. Long-term listings are defined by their verified **monthly price**, without a six-month lease-duration requirement. The inclusive €1,000/month cap is applied only to long-term listings; the existing Tourism mode continues to operate under its original behavior.

- This PR intentionally preserves holiday rentals in imported, public and user-created listing paths.
- The long-term frontend price ceiling is now EUR 1,000; Tourism price controls are unchanged.
- It does not execute or implement physical deletion of existing listings.
- It does not change the running importer or the VPS configuration.
- The existing production importer was most recently observed with `EXTERNAL_IMPORT_ENABLED=1` and `EXTERNAL_IMPORT_NATIONWIDE_ENABLED=1`.

Superseded PR #309 was closed without merge because it removed approved tourist UI. Do **not** use its deletion plan; its old candidate classification would have removed Tourism inventory.

## Read-only classification manifest
`python -m app.commands.audit_long_term_policy --output /path/unique-private-name.json`

The command:
- queries every **not-yet-deleted** database listing;
- counts eligible `long` rentals at EUR 1–1,000 inclusive;
- flags only over-limit long rentals and invalid/missing monthly prices as cleanup candidates; records in holiday mode are counted separately as **preserved**, never included in the candidate list; unsupported modes are review-only;
- aggregates by imported/user origin, status and provider;
- writes a new (never overwritten) mode-0600 JSON manifest with candidate UUIDs and a SHA256 digest;
- executes `SET TRANSACTION READ ONLY` and performs no updates, deletes, storage operations or notifications.

It is **not** a cleanup command. Candidate UUIDs are sensitive operational metadata: do not commit the manifest or upload it to public CI artifacts. Run it only against a deliberately selected database after verifying connection settings. It cannot prove referential deletion safety without a separate dependency inventory.

## Required before any production cleanup
1. Verify the effective running importer flags and worker state. Quiesce catalog writers through an approved change plan.
2. Check authenticated fresh PostgreSQL and MinIO backups, plus restore-verify evidence. Keep backups outside Git.
3. Preserve holiday listings, user-facing Tourism controls and related media. Exclude them from every long-term cleanup manifest and deletion operation.
4. Enumerate the dependent relationships: favorites, source identities, gallery/media, promotion/payment/audit logs, notifications, reports, and related state.
5. Dry-run and review the exact candidate list and manifest digest, then obtain a separate operator approval before any destructive database operation.
6. Stage reversible catalog withdrawal first; any physical deletion needs tested referential integrity and verified restoration.
7. Deploy code and perform catalog cleanup as separate, serialized operational steps. Do not add a data purge to the existing unconditional deployment routine.
8. Verify post-change catalog counts, price boundaries, importer restart safety, and media access.

## Existing deploy behavior
`deploy/deploy-release.sh` verifies backup prerequisites, quiesces writers, backs up PostgreSQL, runs migrations, deploys application containers and restarts `external-listings-worker`; it **does not** run deduplication, automatic listing closure, media deletion or gallery repair. The current script explicitly records `data_maintenance=skipped`. A green CI build does not verify current production backups, importer flags or runtime SHA.

**Status of this document: historical review.** For current release status check `/srv/112233.es/current` and the public `build-info.json` on the VPS; do not infer deployments from this dated plan.
