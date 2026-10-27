# Current-source query proofs — 2026-10-27

Adds an explicit QueryProofs.prepare boundary and a correlated SQL current_projection_predicate for use with typed hard matching BEFORE count/order/seek/limit. This replaces the need to invoke the #385 reader separately for every returned card. Public activation and cards orchestration are still separate work.

## Proof lifecycle

1. In a new REPEATABLE READ READ ONLY transaction, reuse the exact #385 verifier: validate bounded current DTO/vocabulary, pending-source barrier, full resolver output equality, generation/config and visible listing anchor.
2. In the same snapshot compute a PostgreSQL SHA256 signature of the entire relevant projection/anchor, current AI source state, complete current batches/facts and current-or-formerly-known external identities/status/payload digests. Source/batch rows bounded129, fact rows1025, each one beyond accepted maximum to invalidate growth. Timestamps use epoch, independent of connection timezone. No raw payload/evidence leaves the DB in this digest operation or enters the cache.
3. In a separate short write, insert/update the additive cache only if the current single-statement signature still equals the verified snapshot. Concurrent change yields false, not a certified result. Subsequent changes invalidate the SQL guard immediately at the query snapshot, without waiting for reconciliation.

0071 adds only ai_query_proofs, with no legacy FK/backfill/default scheduler. It follows the reconciled0070; no deployed migration changes. Binary rollback retains cache/history. Shared verifier refactoring preserves the existing read-only reader behavior.

The signature includes projection bytes and underlying evidence, not just revision numbers: editing facts/batches/projection without changing input_hash cannot keep permission. New/remapped/deleted sources and pending generations invalidate old proofs. A stale proof may remain in storage; it cannot match SQL equality. Resolver and vocabulary hashes are explicitly bound. There is no implicit production TTL/retention/freshness/owner-precedence policy.

## Verification

Pinned local Python3.14.4/SQLAlchemy2.0.51:1251 unit passed/15platform-or-opt-in skips. Initial full PG run252passed/1Redis unavailable skip, then five extra new-proof cases included in27passing proof cases. Full final CI required. Covers18mutation classes, snapshot/CAS races for source/projection/facts/revision, read-only verification/cache-only write, timezone stability, DB failure propagation, configuration isolation, actual correlated predicate plus typed matcher before count/limit. All12 AI tables checked against the actual combined migration chain and CHECK names. Ruff/mypy140 and immutable/expand-only migration/supply-chain checks.

## Limits and next integration

This is equality with an explicitly verified stored catalog snapshot, not measured elapsed-time source freshness or catalog coverage. It does not grant provider/privacy permission or assert public eligibility; existing listing/user/moderation/price conditions must still be applied. A missing proof means unverified, not proof that the physical catalog has zero matches. Query UX must describe confirmed matches and unavailable coverage honestly.

Query remains free of per-card model inference or live crawling; preparation is a separate explicit stored-data operation. No default builder/worker/daemon/public endpoint is activated. Correlated signature SQL still hashes bounded payload/evidence rows per candidate; real production query plans, capacity and browserp95<=10s remain unmeasured and required before activation. No claim that this primitive alone is the final performance solution. Next: reuse existing card query/order/gallery/redirect and add intent/subject-bound signed cursors with atomic quota/session orchestration.
