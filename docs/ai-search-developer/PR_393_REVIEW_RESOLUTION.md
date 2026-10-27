# PR #393 review resolution — 2026-10-27

Review covered67ee7de414cbd74f6061bf47c5d7564e393b22a7 against merged#392 main. All seven findings are addressed, including supporting intent/matcher/orchestration contracts. No live provider, credential, production registration, migration or deployment is added.

| Finding | Correction | Regression evidence |
| --- | --- | --- |
| F-01 | Pets/amenities require at least one value for hard and soft criteria; explicit remove only. Empty hard rule groups fail closed. | Fake provider -> apply_patch -> compile/evaluate preserves remaining requirements; real PG rejection preserves intent/version and zero debit. |
| F-02 | identity request plus pre-read rejection of non-identity Content-Encoding; raw reads and advertised/accumulated byte bounds. | Actual HTTPX gzip stream representing8MiB decoded data, decoder traps, zero reads, close, traced adapter peak<4MiB; deflate/br/mixed encoding, raw overflow and Content-Length rejection. |
| F-03 | Explicit thinking.type disabled in request. | Actual payload assertions; current primary Thinking/Chat docs rechecked without live model calls. |
| F-04 | Required total monotonic budget includes gate/retries/waits/body/validation, late synchronous decode rejected; declared parser budget strictly shorter than running lease. | Slow chunks/cleanup, aggregate attempts, stalled gate before HTTP, delayed synchronous decode, cancellation, equal/oversized lease configuration; PG timeout releases quota/replays without provider call. |
| F-05 | Adapter rejects empty/effectively unchanged interpretations as PROVIDER_RESULT_INVALID; existing LLM_FAILURE release path debits zero. Order-only conjunction/money-format changes are no-ops. | Real PG preserves criteria/version, skips query, releases reservation and replays without HTTP. Genuine changed intent with zero matches succeeds once, replay adds no debit. |
| F-06 | Full-jitter exponential backoff; Retry-After seconds/date minimum wait, constrained by total budget; long valid waits stop instead of early retry. | Seconds/date delays, huge numeric header, single call for excessive delay, jitter/exponential bounds. |
| F-07 | Complete valid nonempty illustrative balcony patch in system prompt alongside JSON Schema. | Actual outgoing payload assertion; not a substitute for validation or real model-quality evidence. |

The no-op choice is scoped to invalid provider interpretation. It does not establish business rules for human clarification, voice or other injected parsers. Deliberate result refresh has a free read path. No production TTL, retention or technical budget defaults are chosen.

MockTransport handlers are trusted Python, not a network/DNS sandbox. The synthetic gate is not a production minimizer. Input is bounded but ordinary JSON object overhead remains; raw-byte limits are not total process-memory limits. Async timeout rejects late results but cannot preempt blocking trusted code. Parser/lease configuration validation does not establish the full search latency SLO.

Final local source verification:1336 backend units passed/15 platform or opt-in skips;347 isolated PostgreSQL facts/proofs/matcher/quota/session/execution cases passed/1 unavailable Redis skip. Ruff, mypy145, git diff checks, immutable migrations and supply-chain pins passed. Exact-head CI links are recorded in the PR description after completion; old-head green checks are historical. CI exercises Redis/PostGIS separately.

Primary references: [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/), [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/), [JSON Output](https://api-docs.deepseek.com/guides/json_mode/). Public runtime/provider activation remains disabled. Owner review/merge is separate; no automatic merge is authorized.
