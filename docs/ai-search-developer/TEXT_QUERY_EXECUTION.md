# Text query execution — 2026-10-27

Connects actual quota/session contracts to verified existing-card query through an explicit TextSearchExecution service. Dependencies are injected and have no provider, Redis, key, public-route or activation defaults. An offline fake parser is used in tests. This service is not production privacy approval for sending text externally.

## Lifecycle

- Validate bounded final text/hash/channel and reject a paging cursor on a new message before reserve. The server must derive subject/hash from authenticated or signed guest context at the future HTTP boundary.
- Reserve idempotently, claim fence, check owned session/version, run attempt gate, parse strict patch and preserve unrelated criteria, query current verified cards for the candidate intent.
- Verify returned intent hash, then invoke existing AI-08/07 finalize: session CAS + durable normalized intent/count receipt + debit in one PG transaction/savepoint. Successful confirmed-zero result counts once. CAS loser returns no cards and no debit.
- Duplicate inflight operations never invoke gate/parser again. Terminal success replay loads original durable intent/receipt, revalidates current cards/eligibility and never reapplies patch or debits. Receipt count remains historical; current cards total can differ and must not be presented as an identical old snapshot.
- Gate/parser/validation/query failures release without debit; pre-finalize cancellation best-effort releases, otherwise existing fenced lease recovery handles cleanup. Arbitrary injected service exceptions map to fixed private codes, without raw error/text logging.
- Finalize is outside the generic release handler: a missing commit acknowledgement may follow successful CAS/debit. Propagate ambiguity and replay authoritative PG on retry, rather than turn a committed success into failure or call parser again.

VerifiedCardSearch now offers candidate and durable-result paths using the same eligibility/card helper and a fresh read-only RR transaction. Candidate path verifies original owned intent hash/version before querying, and finalize CAS rechecks later. Result replay verifies owned active session and the original durable intent; a later followup cannot rewrite semantics of the earlier receipt.

No clarification response is added and no clarification debit policy is chosen. Voice remains a future combined ASR+intent operation, not two text calls. Background alerts/guest transfer/retention/owner precedence remain unchanged. Page reads never debit.

## Verification

Pinned Python3.14.4/SQLAlchemy2.0.51:1252 unit passed/15platform-or-opt-in skips;59 quota/session/execution realPG passed/1Redis unavailable skip (14new orchestration cases). Covers successful zero/nonzero, inflight duplicate, failed replay, owner/version/gate/parser/query/invalid-patch failures, same-version competing operations, cancellation, lost commit acknowledgement, original-intent replay after followup and hash/cursor rejection before reserve. Shared session fixture moved into conftest; existing cases retained. Ruff/mypy143. Actual end-to-end PostGIS test uses real proofs/cards/session/quota with fake parser/gate, follows a signed candidate cursor after commit, then replays after a source changes without an extra parser/debit. Exact-head CI required; local PG lacks PostGIS.

## Remaining release gates

No public endpoint or provider/worker/importer activation, liveDB/crawl/backfill/mainmerge/deploy. HTTP ownership/CSRF/bounds/anti-abuse and privacy outbound contracts, provider adapters with fakeHTTP, ASR single-debit voice path, registered saved-search reuse/rematch and frontend panel remain work. Native-owner fact precedence/extraction, real coverage/freshness, SQL capacity and browserp95<=10s are not established. Existing manual search/TOP/Stripe/gallery/map stay on their original public path.
