# Payment release rollback compatibility

The operator confirmed production host `vmi3640228`, application release
`24047b6181dab5ba81fd66bd4b4781fa282b50fc`, and applied Alembic head
`0056_external_scope_checkpoint` on 2026-10-14. All seven persistent services
and application services shown by Compose were healthy.

Freeze released migration blobs through 0056 without changing any migration.
The original SHA-256 integrity baseline through 0032 stays intact. The static
compatibility gate also checks the released blob manifest before considering
any constraint operations eligible.

Payment migrations 0059, 0060 and 0062 change constraints on `payment_orders`,
which is first created by unreleased migration 0057. Allow these operations only
when their literal target is a table created directly by an unreleased ancestor.
The previous production application does not read or write this new table.
Constraints on existing tables, schema-qualified or unknown targets, destructive
table/column changes, and prohibited SQL remain rejected. Same-revision,
conditional and unrelated-branch table creation does not grant an exception.

The migration files themselves are unchanged. PostgreSQL payment integration
tests and full migration application passed in Payment audit on head 3ded340c;
the revised static gate must pass CI on the new head before merging.

Keep real payments disabled for this rollout. Before deployment confirm
`STRIPE_LIVE_PAYMENTS_ENABLED=false` and absent/empty Stripe secret and webhook
keys in the server-only environment; a configured live key with the flag false
fails backend startup, and a test key must not enable free public purchases.
Do not print credentials or commit production environment files.

After a successful deployment, extend the released migration blob manifest
through the deployed head before preparing any later migration release. Once
frozen, the payment table is no longer eligible for the new-table exception.
Application rollback retains the upgraded database and does not run downgrade.
