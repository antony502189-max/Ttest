# Final pre-delivery audit — 2026-08-25

## Accepted-behavior reconciliation

| Existing contract | Classification | Disposition |
| --- | --- | --- |
| Listing-result contact opens authentication | UPDATE BECAUSE NEWER CUSTOMER REQUIREMENT OVERRIDES IT | Result-level contact now opens the canonical listing detail contact anchor; direct channels keep their own gate. |
| Internal chat, message threads, and `new_message` mail | REMOVE BECAUSE FEATURE IS INTENTIONALLY GONE | API/router/client entry points were removed. Legacy database tables remain only for migration compatibility and are unreachable. |
| Mobile Chat/Mensajes tab and route | REMOVE BECAUSE FEATURE IS INTENTIONALLY GONE | Navigation and route entries were removed; no fifth mobile tab is introduced. |
| Favorites, direct phone/WhatsApp contact, filters, maps, publication, moderation | KEEP | No accepted customer behavior was intentionally removed. |

## Findings and changes

- `DELETE /api/v1/listings/{id}` authorizes only from the authenticated server-side user email after trim/lowercase canonicalization. Only `antony502189@gmail.com` and `tf.shuler@gmail.com` pass; ownership, role, request data, and local storage cannot grant access.
- A recipient-owned notification model now supports pagination, unread count, single/all read operations, deduplication, and transactional email fan-out through the existing outbox.
- Existing message-specific tests were removed or reconciled because they asserted intentionally retired behavior.

## Validation scope

- Frontend typecheck, lint, production build, dependency security, and bundle-security checks are run for this change.
- Backend non-integration tests run locally. The executable-bit assertion for the production acceptance script is a Windows checkout limitation; source and runtime behavior were not changed by this audit.
- Database-backed integration, production deployment, and merge to `main` remain release actions and were not performed from this local audit worktree.
