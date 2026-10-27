# PR #392 review resolution

Scope: merge the offline foundation; public AI activation remains disabled.
The external review identifies six implementation defects and seven release or
process risks. Fixing the defects does not establish production readiness.

## Repeat review corrections (N-01, N-02, O-01)

- **N-01:** Explicit rented-unit available_spots must equal the canonical
  max(0, effective room capacity - current_room_residents). Missing occupancy
  or capacity rejects certification; household current_residents cannot fill
  in missing room occupancy. All present explicit capacity, room occupancy and
  free-place facts are checked against the same canonical inventory. Full
  PostGIS cases cover positive/negative values, omitted optional occupancy
  facts, unknown inventory, fully occupied units, inconsistent triples and
  attempted re-certification after an occupancy change.
- **Proof upgrades:** Signatures now bind query-proof.v2, the semantic verifier
  contract. Cached rows made by older checking rules cannot bypass new rules
  simply because their source/canonical inputs still match. Re-preparation is
  explicit; no migration, automatic import, crawl or backfill is introduced.
  Real PostgreSQL regressions test invalidation across verifier upgrades; the
  cursor context also binds the semantic verifier version.
- **N-02:** Hidden HTML elements close in stack order. Closing an inner nav,
  footer or header cannot expose its outer block. Mismatched hidden closing
  tags latch suppression for the remaining input; unclosed hidden blocks stay
  suppressed. Ambiguous self-closing non-void hidden elements are conservative
  openings. Tests cover nested/mixed elements, incomplete/crossed boundaries,
  void elements and raw-text script/style/iframe contents. This remains a
  selected-field minimizer, not a guarantee to recognize all personal names.
- **F-03 reinforcement:** PostgreSQL replay tests now cover every accepted
  ListingCardSearchRequest field, nested polygon changes, UUID conversion,
  explicit/omitted defaults and polygon closure normalization. Changed
  validated payloads conflict without further inference or debit; equivalent
  normalized requests replay the original receipt.

### O-01: explicit live pagination contract

AI cursors mean **live keyset pagination**, not a frozen eligible-result or
commercial-order snapshot. Every request uses its own repeatable-read database
snapshot and rechecks current source equality, public eligibility, moderation
and TOP ordering before count/order/seek/limit. Thus totals can change between
pages. A stored proof-set digest binds the prepared cache only; it does not
claim to version every change in the live eligible set.

Subject/intent/filter/config/catalog/fact/prepared-proof changes covered by the
signed context reject the cursor. Direct source payload/status changes, owner
blocking, moderation and TOP scheduling may instead leave it valid and alter
the eligible set/order. A newly eligible row or a promotion moved before the
seek point requires restarting at the first page to discover it. Reordering
may also repeat a previously seen ID; future UI should deduplicate IDs and
offer refresh rather than promise a frozen traversal. No stale/ineligible
card is returned to preserve an old total. A stable export would require a
separate durable snapshot contract and is not provided by these cursors.

Full PostGIS tests exercise source payload/status mutations, owner blocking,
moderation, TOP reordering and source restoration between pages without
changing stored proof rows. They check current counts, absence of ineligible
cards, discovering earlier rows on refresh and no quota debit for paging.
This service contract must be exposed by the future API/UI before activation.

## Implemented corrections

| Review | Contract and regression coverage |
| --- | --- |
| F-01 | Signed cursors include an ordered SHA256 identity of the prepared proof set for the selected resolver/vocabulary. Insert, delete and replacement invalidate cursors; identical preparation leaves them valid. Restoring exactly the same set restores the same identity. No shared global generation lock or unrelated resolver invalidations. Real PostGIS pagination tests exercise these mutations between pages. |
| F-02 | Proof signatures include the canonical listing and its optional room details, including insert/delete. Only views and bookkeeping updated_at are excluded; timestamps are normalized to epoch across connection time zones. Preparation also requires confirmed price, rental mode, capacity and availability facts to agree with canonical values, so reconcile/prepare cannot recertify an old 500 EUR price against a 900 EUR card. Canonical defaults do not generate evidence. Tests change prices, mode, capacity, dates and room rows independently of external sources, before count/pagination. |
| F-03 | A new text operation binds every validated card-request field, including limit, favorites and sort, via a server-computed filters_sha256 in the quota fingerprint. Reusing the key with another request conflicts before inference or debit. Replays retain the original receipt and revalidate current cards with identical request parameters. Separate owned-session page reads remain free and may use their own filters. |
| F-04 | Reconcile compares all deterministic projection fields with a fresh resolution before returning an unchanged revision. Corrupt JSON is rebuilt with a larger revision and rematch event. Tests cover valid-but-wrong and malformed feature JSON, failed preparation, repair, successful preparation and subsequent idempotent reconcile. |
| F-05 | The bridge declares its supported provider subset explicitly. Upstream empadronamiento_allowed remains accepted by the compatibility packet, retained in the hashed source manifest and reported in skipped_provider_fields; it does not block supported facts or become an invented AI fact. Unknown upstream fields still fail schema validation. Both boolean values are tested. |
| F-06 | Meaningful sanitized, typed structured evidence can admit an empty description. The bridge still requires approved field mappings, capacity/smoking scopes and vocabulary. Unsupported-only facts and contact-only evidence cannot satisfy this rule. Older packets marked insufficient are admitted only through this structured-evidence rule. |

Bridge semantics are versioned as offline-fact-bridge.v2, so these admission and
subset changes produce new content hashes instead of silently reusing v1 jobs.
Quota-only/voice callers may omit filters_sha256; text orchestration computes it
itself and rejects a supplied digest inconsistent with the validated payload.
Previously prepared proof caches fail the expanded signature and need explicit
offline re-preparation. There is no automatic crawl or backfill.

## Local validation of the corrections

Python 3.13.17 with backend/constraints.txt; isolated PostgreSQL 16/PostGIS 3.4
and test Redis namespace:

- Full unit suite after repeat review: 1280 passed, 15 platform/opt-in skips.
- Facts/proofs and quota/session/execution PostgreSQL/Redis suites: 338 passed.
- Full-schema verified cards and existing gallery regressions: 41 passed.
- Ruff, mypy (144 modules), pip check and git diff --check passed.
- Complete Alembic upgrade and metadata check passed; one head remains
  0071_ai_query_proofs, with no new upgrade operations detected.

These tests use synthetic data. Live providers, a representative load test,
browser timing, S3 and public endpoint E2E were not exercised in this local run.
CI must independently validate the corrected commit on its own environment.

## Release gates still open

| Risk | Required evidence before public activation |
| --- | --- |
| R-01: capacity | EXPLAIN (ANALYZE, BUFFERS) for count and page separately, realistic payload sizes/source/fact distributions at 10k+ catalog rows, hot/cold cache, concurrent readers and source/proof writers, p50/p95, CPU/memory and timeout budgets. Include the scoped proof-set aggregate in this measurement. Unit and small PostGIS fixtures are correctness evidence only. The aggregate is O(prepared proofs) and full snapshot hashing remains expensive; no production SLO is claimed. |
| R-02: freshness | Owner-approved provider-specific maximum successful-check age, treatment of failed checks/outages and missing timestamps; implement expiry/health predicates before count and pages, and boundary/concurrency tests. Stored-snapshot equality is not live-source freshness. No default TTL is silently selected here. |
| R-03: coverage | Provider-by-field matrix with anonymized real examples, approved provider/owner adapters and UI distinguishing insufficient verified data from no suitable housing. Matcher support is not extraction coverage; see the matrix below. |
| R-04: retention | Approved retention periods for sessions/results, quota/idempotency audit, facts/jobs/rematch events, deletion dependencies and quota recovery; bounded cleanup jobs and integrity tests, with privacy review before HTTP wiring. Expiry currently denies access and does not delete records. |
| R-05: public boundary | Authenticated and signed-guest ownership derived on the server, API authorization/CSRF/abuse/concurrency controls, approved outbound privacy/DPA, real provider/ASR/UI E2E. No endpoint, provider default or public activation is introduced by these corrections. |
| R-06: merge sequence | Use #392 as the single runtime integration vehicle. Do not merge duplicate old migration roots. Refresh dependent branches after this lands and recheck one Alembic head against the actual target main. No migration is added or rewritten by these fixes. |
| R-07: check provenance | Wait for required workflows on the new exact head. Record intentional skips separately. Historical green checks are historical evidence, not results for the corrected commit. Scheduled/manual live discovery, real provider contracts and representative performance remain separate release evidence. |

The policy and external evidence gaps above cannot be completed by choosing
arbitrary TTL/retention values or enabling a public service in this offline PR.
They remain explicit blockers for product activation, even when the foundation
has passed its merge checks.

## Current offline bridge coverage

This is a capability matrix for the synthetic compatibility adapter, not a
provider coverage claim. Every provider still needs a reviewed mapping and real
anonymized contract fixtures.

| Hard criterion | Facts the bridge can currently produce |
| --- | --- |
| rental_mode | None; packet rental_category is routing metadata, not evidence |
| budget | None |
| geography | None |
| accommodation | None; property_category is not attested accommodation evidence |
| party | Total capacity, children and couples only; no available_spots, current room inventory or tenant groups |
| pets | Supported, preserving uncertainty and qualifiers |
| smoking | Supported with explicit reviewed scopes |
| furnished | Typed structured boolean, including false |
| bills_included | Typed structured boolean, including false |
| deposit | None |
| balcony | Supported structured amenity |
| terrace | Supported structured amenity |
| amenities | Explicit approved code mapping only |
| dates | None |
| stay | None |

Municipality registration is explicitly outside this AI fact vocabulary. Missing
evidence remains unknown; future UI/alerts must not broaden a hard query or
route AI saved searches through legacy fallback matching.
