# Offline DeepSeek intent adapter — 2026-10-27

Implements AI-09 IntentPatchParser through a required local outbound gate, explicit bounded policy/SecretStr test credential and HTTPX MockTransport. A real transport is rejected by the constructor; no app settings/router/worker/factory registers this adapter. This is fakeHTTP contract preparation, not provider activation or a privacy certificate. No API key is requested.

Primary references checked on2026-10-27: [DeepSeek JSON mode](https://api-docs.deepseek.com/guides/json_mode/) and [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/). Requests use the documented deepseek-flash, json_object response format and explicit JSON instruction, nonstreaming output and explicit token/timeout/retry/byte budgets. No OpenAI SDK/fallback is introduced.

The required gate returns only purpose/provider-bound minimized text and typed current criteria. No production minimizer/default exists. User/session/result IDs, raw conversation history, source payload/URL and SQL are absent from the adapter envelope. The type cannot prove that a caller properly sanitized private text; actual minimizer/evaluation/privacy/DPA approval is still needed before outbound activation.

Model output can only select strict set/remove criteria. Identity/version are injected from the server. Duplicate keys, nonfinite JSON, extra identity/SQL fields, coercion/null removal, set/remove overlap, unknown fields, empty/malformed content, truncation/refusal/tool/resource-abort outputs fail validation. One complete assistant choice is required; valid JSON alone is never trusted as schema/meaning proof. No automatic broadening or model-selected authority. Local vocabulary/SQL hard matching remain separate enforcement boundaries.

Transient429/5xx/transport errors retry only within explicit max_attempts;4xx/redirects fail immediately, redirects are never followed. Streaming read is byte-bounded; error bodies/keys/raw text are not included in fixed failure codes or logged by the adapter. These policies are engineering test configuration, not approved production budgets or a10s benchmark. Orchestrator treats parser failure as no-debit service failure.

Validation:29fakeHTTP tests, including minimized envelope/server identity, retries, no redirect credential forwarding, invalid/duplicate/type/conditional JSON, refusal/truncation, timeout/size bounds, privacy gate before HTTP and live transport disabled. Ruff/mypy144; full backend unit suite recorded in PR. No real model quality/coverage/freshness/privacy or latency claim. No real API call, crawl/backfill, liveDB, mainmerge or deploy.

Next: real outbound minimization/evaluation, provider account/privacy gates before live pilot; fact enrichment and batch ASR adapters need their own contracts. Registered saved-search/rematch, public HTTP/guest controls and UI remain independent work. Existing runtime checkpoint is #392, not complete product activation.
