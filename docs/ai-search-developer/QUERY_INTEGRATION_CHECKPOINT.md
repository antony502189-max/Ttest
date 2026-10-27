# AI Search query integration checkpoint — 2026-10-27

This is the main-based integration vehicle for #387 -> #388 -> #389 -> #390 -> #391. It contains actual parser/facts/quota/session refs and the implemented typed matching/current-source/card/query orchestration. No source PR branch/state is changed or main merged. Review those incremental deltas, then choose ONE integration vehicle: this PR, or the refreshed stack. Do not merge both unreconciled copies. Older #378–386 remain reference/incremental reviews; #377 remains a reference lab, not a second runtime. #373 is already approved/merged into planning and needs no repeated planning review gate.

## Concrete runtime now available internally

- Reconciled parser + facts + quota + sessions, model registry and both historical journals. Unreleased0069 parent0068, followed by0070 and additive0071 query-proof cache. Linear0066->0067->0068->0069->0070->0071, twelve AI tables, no released history rewrite.
- All15 typed hard criteria compile through the same immutable offline/SQL plan. Unknown/conditional/conflict/defaults never confirm permission, units and scopes are preserved; no fabricated scores or commercial reorder.
- Current-query proof rechecks bounded complete evidence/source/projection signatures at the SQL snapshot before count/order/seek/limit; preparation verifies in read-only RR and CASes separately. No N+1 application per-card verifier.
- Existing public eligibility, cards/gallery/source URL, paid TOP/boost/favorite sort and bidirectional seek are reused; signed AI cursors bind subject/intent/version/filter/config/catalog/fact revision context. Manual search keeps original public path/cursor format.
- Text orchestration reserves/claims once, checks owned session/attempt gate, applies strict patch, queries verified cards and atomically finalizes CAS+durable normalized result+debit. Zero success=1, failures=0, inflight/replay no repeated inference/debit. Lost commit acknowledgement replays authoritative receipt. Current cards revalidate against original intent while durable receipt keeps original count.

All entry points are explicit internal services, not public activation. No default parser/provider/client/background worker/API route is enabled.

## Review corrections

See [PR_392_REVIEW_RESOLUTION.md](PR_392_REVIEW_RESOLUTION.md) for F-01 through
F-06 fixes, exact replay/pagination contracts, canonical consistency checks,
bridge coverage and the still-open public release gates R-01 through R-07.
Historical CI evidence below predates these corrections; the new head requires
its own required checks before merge.

## Verified evidence before opening main integration

#391 head f1d38e359573be14f8f0b4ea7a40d52ce4132eff: all4triggered workflows SUCCESS. Combined [40425280443](https://github.com/antony502189-max/Ttest/actions/runs/40425280443):1260unit passed/7skips,500focused cases passed including real PG16/PostGIS/Redis,8real PostGIS cards/gallery/orchestration cases, Ruff/mypy143, complete historical chain and alembic check(no operations). Focused units overlap full unit totals. Payment [40425282004](https://github.com/antony502189-max/Ttest/actions/runs/40425282004), quota [40425280547](https://github.com/antony502189-max/Ttest/actions/runs/40425280547), Security [40425280422](https://github.com/antony502189-max/Ttest/actions/runs/40425280422) success. #388/#389/#390 all4workflows success on their final heads.

Local pinned Python3.14.4/SQLAlchemy2.0.51:1252unit/15platform-or-opt-in skips;59quota/session/executionPG/1Redis unavailable skip; all earlier facts/proof/matcher suites passed (see individual reports). Owned disposable PG18cluster stopped; zero leftover schemas. Local has no PostGIS; full real-schema card evidence is CI. New main integration head MUST run its own Full/Mobile/Production/Parser/Payment etc; those results are not inferred from a stacked base. #387 Production audit was still installing ffmpeg at last inspection; not claimed green.

## External boundary and remaining implementation

No main merge/deployment, live applicationDB/catalog/crawl/backfill, paid API or credential collection. Existing public-source workflow guard retained and confirmed SKIPPED on #387; live discovery only schedule/manual. This does not establish provider privacy or elapsed-time source freshness.

Registered AI saved-search storage/matching/rematch delivery, provider adapters/privacy outbound contracts, public HTTP/guest controls, single-debit ASR/voice and frontend panel remain work. Do not present the internal core as complete product activation. Legacy SavedSearch notifier currently ignores unknown filter keys: any AI marker integration MUST explicitly prevent legacy broad fallback, reuse shared matcher and ownership/visibility, and respect unresolved background-alert quota policy. No saved-search code changed in this checkpoint.

Pending owner decisions remain clarification debit, background alerts quota, guest transfer, production TTL/retention/technical policies, owner-fact precedence. No silent policy choice. Native-owner evidence extraction/precedence, actual source coverage/freshness/privacy/DPA, representative SQL capacity and browserp95<=10s are unproven. Correlated proof hashing still needs realistic plans/load; synthetic correctness is not performance evidence. Keys are unnecessary for continued offline contracts/fakeHTTP/UI preparation.

## Owner checkpoint

After final exact-head CI and human review, this integration can be merged as ONE runtime change; no automatic merge/deploy is configured. Documentation #374->#375 and reconciled proposed #376 remain separate review history. Do not merge old independent0069root onto0066 after this integrated chain. Refresh remaining PR bases/checks after the chosen parent lands; do not auto-close old branches/PRs. Production activation and live tests require their own explicit authorization.
