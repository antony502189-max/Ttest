# Rental policy change — release blockers and safe production inventory

## Verified baseline and scope
The requested long-term-only product policy is **not implemented** by the current price-cap PR:
- This PR intentionally retains holiday rentals in imported/public/user-created listing paths.
- Existing frontend search price ceiling remains EUR 1,200.
- It does not execute or implement physical deletion of existing listings.
- It does not change the running importer or the VPS configuration.
- The existing production importer was most recently observed with `EXTERNAL_IMPORT_ENABLED=1` and `EXTERNAL_IMPORT_NATIONWIDE_ENABLED=1`.

Do not mark this PR ready for production under the customer's long-term-only specification. This narrower implementation is a useful first layer of long-term price enforcement, not the whole migration.

## Read-only classification manifest
`python -m app.commands.audit_long_term_policy --output /path/unique-private-name.json`

The command:
- queries every **not-yet-deleted** database listing;
- counts eligible `long` rentals at EUR 1–1,000 inclusive;
- flags over-limit long rentals, invalid/missing monthly prices, and every holiday/other-mode listing;
- aggregates by imported/user origin, status and provider;
- writes a new (never overwritten) mode-0600 JSON manifest with candidate UUIDs and a SHA256 digest;
- executes `SET TRANSACTION READ ONLY` and performs no updates, deletes, storage operations or notifications.

It is **not** a cleanup command. Candidate UUIDs are sensitive operational metadata: do not commit the manifest or upload it to public CI artifacts. Run it only against a deliberately selected database after verifying connection settings. It cannot prove referential deletion safety without a separate dependency inventory.

## Required before any production cleanup
1. Verify the effective running importer flags and worker state. Quiesce catalog writers through an approved change plan.
2. Check authenticated fresh PostgreSQL and MinIO backups, plus restore-verify evidence. Keep backups outside Git.
3. Decide the customer-facing treatment of holiday listings (requested: remove from active product). Build and validate long-term-only frontend/backend changes and update tests.
4. Enumerate the dependent relationships: favorites, source identities, gallery/media, promotion/payment/audit logs, notifications, reports, and related state.
5. Dry-run and review the exact candidate list and manifest digest, then obtain a separate operator approval before any destructive database operation.
6. Stage reversible catalog withdrawal first; any physical deletion needs tested referential integrity and verified restoration.
7. Deploy code and perform catalog cleanup as separate, serialized operational steps. Do not add a data purge to the existing unconditional deployment routine.
8. Verify post-change catalog counts, price boundaries, importer restart safety, and media access.

## Existing deploy behavior
`deploy/deploy-release.sh` performs migrations and applies the deduplication and gallery repair commands while writers are paused; it also restarts `external-listings-worker`. A green code CI run does not verify current production backups or importer flags.

**Status: CODE CHANGES UNDER REVIEW — NO PRODUCTION DEPLOY.**
