# One-operation voice contract

`VoiceSearchExecution` is an injected offline service, with no application/HTTP
registration or microphone UI. The server hashes final bounded immutable audio
bytes and binds media, session/version and the complete validated card request.
It reserves and claims once, checks ownership/version/technical gate, runs ASR
and the existing intent parser, queries the candidate and atomically finalizes
the same operation. It never invokes text execution or generates another key.

The injected policy allocates explicit monotonic ASR, intent and total budgets.
Their allocation leaves query time and lease headroom for finalize. Synchronous
late results are rejected too. ASR/intent/backend failures release with fixed
phase codes. Cancellation before finalize releases or relies on fenced recovery.
Finalize acknowledgement loss remains outside speculative release handling.
Running/replayed operations never call either provider again. Zero matches after
a meaningful successful change still cost one search. Reviewed DeepSeek no-op
rejection and text fingerprints remain unchanged.

Successful voice replays use the same terminal receipt reader as text search.
Expired or unavailable original cards return the durable successful receipt with
`cards_error`, without rerunning ASR/intent or debiting again. Card reads retain
their ownership, expiry and integrity checks; unexpected errors still propagate.

`OfflineASR` accepts only HTTPX MockTransport, targeting a synthetic `.invalid`
host. Its explicit local outbound gate is not production consent approval. It
rejects compression/redirects, limits raw response bytes before JSON parsing,
validates a strict bounded transcript and emits fixed errors. Audio/transcripts
are in memory only and excluded from stored session/ledger/receipt and repr.

Local validation: 240 tests passed (full disposable-PG quota/session/text/voice
suite plus 18 mock-ASR wire contracts), one optional Redis test skipped; Ruff
and mypy (150 source files) passed. The dependent PR records isolated CI evidence.

Real ASR/provider transport, consent/minimization/retention/DPA, production media
policy and public capability remain separate activation gates. No live service,
application database, notification, crawler or deployment was used.


Own total deadline includes reserve/claim, replay reads, providers, queries,
cleanup and atomic finalize; an HTTP deadline can only shorten it. Failure or
external cancellation cleanup gets only the remaining budget. Exhaustion raises
TimeoutError (or preserves external CancelledError), leaving the reservation for
fenced lease recovery and exact-key replay. Finalize timeout/ack uncertainty never
invokes speculative release. No extra unbounded cleanup allowance is provided.
