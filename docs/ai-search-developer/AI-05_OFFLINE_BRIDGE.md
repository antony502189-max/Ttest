# Offline parser packet bridge into AI-04 — partial AI-05 preparation

Date: 2026-10-26. Branch: `codex/ai-05-offline-fact-bridge`.
Stacked base: [AI-04 #381](https://github.com/antony502189-max/Ttest/pull/381),
`ebcc1918c2a16f1a3aed794d7e7d0f3fe9ba9da6`, above unmerged [AI-03 #380](https://github.com/antony502189-max/Ttest/pull/380).
Main underneath remains `1292c6807ece59999238bb31c80e09ef7e2c3212` (payment #372).
All three final-head workflows on #381 were rechecked completed/success; that is
not a merge. The owner authorized continuing this independent offline preparation.

This is **not the complete AI-05 outbound privacy gate**. BASE-373 still requires
human review/port: no submitted GitHub review was present on #373 at recheck.
Its cleaner, clause grammar and importer changes are not copied/imported into the
application. No production minimizer, provider or worker is activated by this PR.

References: [Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md),
[TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md),
[AI-01 proposed ADR](https://github.com/antony502189-max/Ttest/blob/d46c44ee62aa89e0ac312e69d754aca9594f96d8/docs/ai-search-developer/adr/AI-01_CONTRACTS.md),
[AI-04 implementation and activation gates](AI-04_BACKEND.md).

## Implemented adapter and capture boundary

- `ParserEvidencePacket` is a strict bounded compatibility subset of #373's
  `listing-evidence-v1` JSON. It accepts the exact eight policy fields, typed
  structured provider facts, bounded sanitized strings/spans and explicit versions.
  Unknown/raw envelope fields, type coercion, URLs as opaque identity, invalid
  status/value combinations and mixed structured/text policy evidence fail closed.
- `FactSnapshotReader.capture` selects one active external source joined to a
  published/non-deleted listing. Raw/normalized payload JSON and source price text
  are returned only to the explicitly injected trusted builder as immutable strings
  with suppressed repr. An explicit byte policy (no production default, max 2 MiB)
  filters oversized rows inside PG; no payload truncation occurs.
- The coarse SHA-256 snapshot expression is shared with AI-04. Bytes and token
  come from the same locked source row version in one query; routing identity uses
  the provider name plus server UUID rather than an advertiser/external record ID.
  Capture releases its transaction/connection before any builder executes. The
  pre-existing AI-04 expected-token check rejects a later snapshot change.
- `prepare_captured_source` requires a builder argument; there is no default
  cleaner, automatic scalar fallback, background ingest or network client. The
  current test builder only reads a stored **synthetic already-sanitized fixture**.
  A production builder remains a reviewed BASE-373/minimization integration task.
- `bridge_packet` verifies source/canonical routing against the captured reference
  and recomputes #373's original hashed content shape. It then creates a separate
  `offline-fact-bridge.v1` evidence mapping and `SourceInput` for AI-04. Bridge hash
  covers sanitized text, typed provider values/quotes, all policy decisions,
  mapping choices and bridge version. It does not reuse the import fingerprint or
  silently equate the legacy packet digest with the AI-04 sanitized mapping hash.
- Prepared inputs store immutable string tuples and expose fresh decoded copies.
  `to_batch` is bound to all claim input fields, including snapshot/extractor/
  schema/taxonomy versions. The existing AI-04 writer supplies authoritative IDs,
  timestamps, generation/fence checks, atomic projection/event and replay behavior.
  No new migration/model/public API is needed.

The coarse snapshot token is a change detector, not minimized outbound content.
The reader necessarily exposes raw/normalized text to the selected internal builder;
it must never be passed to providers or logged. Neither the adapter nor the old
cleaner proves absence of all PII. No actual user/source data was read in this work.
All capture/queue tests use the chat's disposable loopback DB and synthetic records.

## Evidence and conservative conversion

The upstream text grammar emits quotes without offsets and hashes content but
not its `policy_evidence` decisions. The bridge preserves that distinction: its
own hash binds these decisions, but does not authenticate them or verify natural
language truth. Only a reviewed server-side producer may supply this protocol;
it is not a model/client input endpoint or a substitute for extraction evaluation.

- Text spans must reconstruct complete exact sanitized clauses. A quote inside a
  larger negation is rejected. Repeated identical clauses are accepted only when
  the number of unambiguous complete occurrences matches the evidence count.
  Whitespace/newline boundaries are checked structurally, not with another policy
  grammar. Unicode offsets are characters, not UTF-8 byte counts.
- `explicit` policy true/false maps to `explicit_allow`/`explicit_deny`.
  Conditional/conflict keep no winning value. Unknown is not denied; no legacy
  canonical defaults are read as evidence.
- Policy pets/children/couples and precisely scoped smoking can be translated.
  Generic/outdoor smoking needs explicit server scope mapping. When #373 repeats
  the same precise smoking quotes as a generic conditional, only the exactly
  covered duplicate is omitted; the precise indoor/terrace evidence survives.
  An unscoped explicit denial is never silently discarded.
- Capacity requires an explicit server-attested rented-unit scope (per structured
  provider path or text context). It produces `capacity_total`, never available
  spots or inferred `total-current` arithmetic. This is a synthetic engineering
  fixture choice, not an approved mapping for actual adapters.
- Structured paths/field identities require exact explicit mappings. Boolean false
  furnished/bills values are confirmed values, not policy denials. Approved amenity
  codes retain typed keys; balcony/terrace remain distinct. Multiple structured
  observations in one key/scope/origin merge; contradictory values become conflict
  rather than last-write-wins. Text/structured contradictions reach AI-04 resolver.
- Unverified capacity/smoking scopes, students-only narrowing, unsupported provider
  facts, unapproved paths/amenities, insufficient packets and ambiguous evidence
  reject the packet. No partial broad projection is enqueued from a rejected input.
  Rental/property/language metadata is hashed but does not by itself prove a
  category, price, geography, capacity or availability fact.

Required `BridgeMapping` and `FactVocabulary` have no production defaults. Tests
use explicit synthetic field paths, scope attestations and `test_wifi`. The bridge
supports only this compatibility subset, not all 21 facts or every legacy packet.
Input bounds align with AI-03/04: <=128 provider facts, <=16 spans/observation,
512 chars/span, <=128 mapped paths, <=256 evidence mapping entries/1 MiB.
No owner override, tenant-rule semantics, retention, freshness TTL, paid-call
budget or background-alert quota decision is introduced.

## Pinned synthetic protocol fixtures

`backend/tests/fixtures/ai_fact_bridge/parser-373-synthetic.json` contains 17 packets
generated by the original builder at #373 head
`fcae378d9dbbc8447f18df150327180f6f2c8231`, plus both exact source SHA-256 digests.
It covers negatives, allow/conditional/conflict, capacity/couple, indoor/terrace
smoking, repeats, Unicode/newlines, structured false/capacity/amenities, unsupported
students, empty input, marketing unknown and a synthetic contact/HTML cleanup case.

Optional reproduction (from the repo root with backend dev dependencies):

```text
python scripts/build-ai-fact-bridge-fixtures.py
```

This explicit standalone generator reads two pinned local Git objects, checks
their separately pinned SHA-256 digests, and executes
that historical pure builder only to regenerate **synthetic JSON test data**. It
does not fetch, install, port or load that code into the app or CI. If those objects
are unavailable it fails; no network workaround is attempted. CI consumes only the
committed JSON fixtures. Generating them is not human approval of #373 or privacy
approval for actual source text.

## Verification and remaining work

The new tests cover packet hashes/strictness, all mappings above, clipped negative
quotes, exact repeated/Unicode spans, structured conflicts/collisions, no default
fallback, detached prepared data, claim/routing binding, reader byte limits and
redacted builder errors. New PG tests run capture -> injected fixture builder ->
bridge -> actual AI-04 observe/claim/complete/replay and source snapshot races.
The minimal legacy fixture now uses the actual `listing_status` enum, so the
reader's ORM predicate is checked without weakening the production query.
Original AI-03/04 PG cases still verify the extracted shared snapshot expression.

Local final code: **236 focused passed** (161 DTO/resolver/bridge unit cases +
75 real PostgreSQL cases). This increment adds **50 unit + 14 PG cases**; all
172 prior focused cases remain included. Complete backend unit suite:
**996 passed, 15 platform/opt-in skipped, 388 integration deselected**; the 161
focused unit cases are included in 996, not additional. Ruff app/tests and the
fixture generator, mypy 123 modules, immutable/expand-compatible migrations,
supply-chain pins and diff checks passed. No new migrations/ORM tables.
Zero test schemas remained and the owned local cluster was stopped after checks.
Final-head CI evidence is recorded in the PR. JUnit remains in
ignored `output/ai05-focused-local.xml`, `output/ai05-unit-local.xml`. Full historical
PG16/PostGIS migration chain and schema checks are required CI results; installed
local PG18.6 has no PostGIS. Synthetic packets do not measure real coverage,
extraction quality, source freshness, privacy effectiveness, SQL cost or 10s SLO.

Before real ingest: human review/port #373, approved minimization and field/scope/
catalog mappings, real source/DB measurements, reader/importer concurrency review,
retention and explicit activation policy. Before outbound: separate provider
privacy/account/paid-call approval. AI-09 still needs the complete existing
visibility/price/TOP eligibility query, verified hard predicates, sessions/quota,
cursor and card integration; this PR does not expose that endpoint.

Rollback reverts only these unconnected adapters; no schema/data migration or
queue activation occurred. No actual catalog, parser/importer, cards/TOP/Stripe/
map/gallery/notifications behavior, paid provider call, crawling/backfill, live
staging, main merge or deployment changed. API keys are still unnecessary.
