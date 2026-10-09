# Monthly price cap — preserve PR #298 design and Tourism inventory

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
`deploy/deploy-release.sh` performs migrations and applies the deduplication and gallery repair commands while writers are paused; it also restarts `external-listings-worker`. A green code CI run does not verify current production backups or importer flags.

**Status: CODE CHANGES UNDER REVIEW — NO PRODUCTION DEPLOY.**
