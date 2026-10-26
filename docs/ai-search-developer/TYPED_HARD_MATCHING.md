# Typed hard matching — 2026-10-27

Stacked on combined integration #387. Uses the actual AI-08 SearchIntent and AI-03 SearchProjection instead of a parallel DTO. Explicit bridge between intent taxonomy rental.v1 and facts ai-search.v1. Server FactVocabulary validates catalog/amenity/zone mappings; friends permission requires the literal configured tenant-group code. No production vocabulary is invented.

A shared immutable plan covers all15 current criteria; unsupported future hard fields raise rather than disappear. SQL compiler and offline evaluator consume that same plan. Unmet criterion names are deterministic schema-order reason codes, never percentages. Soft criteria remain in intent and do not exclude or reorder paid TOP.

- Price/deposit compare exact EUR decimal amounts only in the same period/unit, with no weekly/monthly or deposit conversion.
- Province/municipality/zone use hierarchical exact supplied INE/catalog identity; supported room/shared/studio/one-bedroom/catalog_other types remain distinct.
- Party requires confirmed rented-unit capacity AND available places, not legacy defaults; couples/children need explicit permission when requested. Friends need configured explicit tenant-group evidence.
- Pets retain species/size and total requested count. Generic or exact scoped permission can confirm a known size; narrow size does not confirm unspecified size. Multiple overlapping rules or uncertainty cannot be selected around. Total pets is used conservatively against all limits, which can reject some otherwise permissible mixed-species parties.
- Smoking respects indoors/outdoors/balcony/terrace scope: outdoors may cover balcony/terrace, narrow balcony does not confirm outdoors. Pending approval never confirms permission.
- Negative boolean requests match explicit false; amenities match every configured requested code. Dates require a covering availability interval AND confirmed min/max nights. Stay requires both confirmed bounds in the requested unit. Missing bounds are unknown, with no invented unlimited stay or conversion of months to30days.

The conservative capacity/bounds/pet overlap choices may yield false negatives; they never turn missing or conditional evidence into permission. This is an engineering compatibility boundary, not an approved UX policy for displaying uncertain alternatives. Owner precedence, clarification debit, background-alert quota, guest transfer and production TTL/retention are unchanged.

## Verification

Local pinned Python3.14.4/SQLAlchemy2.0.51:1251 unit passed/15 platform-or-opt-in skips. Focused279passed/1Redis unavailable skip, includes unit overlap and230 realPG tests. SQL differential cases cover all criteria, null-preserving DTO serialization, uncertainty/duplicates, narrow/broad policies, scalar corruption, guarded numeric casts and criteria before count/commercial-rank/seek/limit on synthetic candidates. Ruff/mypy138. Existing facts/session/migration suites retained. CI required on exact head; synthetic cases do not establish real coverage/precision/latency.

## Query boundary

No public endpoint, default activation, provider/LLM-per-card, importer change, migration or source permission. SQL caller MUST supply authority-validated current projection and combine existing public eligibility BEFORE count/order/seek/limit. This predicate does not prove currentness/provenance for arbitrary stored JSON. It is not wired into public cards yet; per-card post-page filtering is prohibited. Existing cards/TOP/Stripe/gallery/map/cursors remain unchanged.

Next integration must provide efficient set-based current-source proof and eligibility, signed intent-bound cursor and quota/session result orchestration, then reuse this plan in query and saved-search matching. The single-listing #385 reader is not an N+1 search substitute. Full historical/browser CI and privacy/source freshness/10s measurements are distinct gates.
