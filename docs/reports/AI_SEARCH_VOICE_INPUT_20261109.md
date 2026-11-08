# S4.1: local voice input

Base: merged PR411/main `1a91d8fe6025ef49fc17765ed97b7638116870b8`.
Owner explicitly prioritized voice on09.11 after confirming merge. Existing
worktree/branch `codex/ai-search-voice-input`; root dirty files preserved.

Microphone →15s canonical PCM → same-origin private HTTP → local ASR → existing
positive-rent parser → verified SQL/cards/map is one durable voice operation.
There is no transcription-only second quota operation or second text submission.
The same audio/key/session/version is replayed after lost acknowledgements;
reload uses the existing receipt locator and never persists audio/transcript.
Media validation rejects noncanonical WAV, arbitrary codecs/URLs, malformed
lengths and oversized audio before quota reservation. CSRF/ownership/IP gates,
source/approval preflight and the existing provider journal remain authoritative.

The optional local CPU adapter runs faster-whisper in a separate exact-version
environment and hard-bounded disposable process. Model revision and every asset
SHA256 are pinned; no model download during inference. Audio stays on the owned
server, outside third-party ASR. Child environment excludes app/provider secrets;
stdout is bounded and stderr discarded. ONNX telemetry is disabled; pilot's
internal network has no direct external route. The CI ASR test additionally runs
with Docker network=none/read-only/nobody/no capabilities/2CPUs/1536MiB, synthetic
speech only. [Upstream implementation](https://github.com/SYSTRAN/faster-whisper)
and [model source](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66).

Browser capture uses AudioWorklet and bounded Float32 chunks converted to PCM,
not browser speech-recognition vendor services. Explicit start/stop/cancel;
permission denial and unavailable media retain text fallback. Cancel/dialog close
release all tracks, including streams resolving after close. In-memory ambiguous
audio is dropped after15minutes; only the existing nonprivate locator survives.
The emitted worklet must be a same-origin asset (`no-inline`) to satisfy CSP.
Proxy buffering is off to avoid audio request bodies being spooled to disk.
The pilot document explicitly uses `camera=(), microphone=(self)`, covered by
preview and actual proxy assertions. The earlier running API had microphone=()
from app.main, while its HTML document had no such header; API headers are not
the document's permission policy. Ordinary-site headers are unchanged.

Source/runtime changes are opt-in: ordinary voice capability remains false;
pilot voice requires `voice.yml`, local assets and explicit `local-pcm-v1` config.
Voice admission now shares text's transaction/owner/version lock and inference
slot. Invalid owner/version creates neither a request nor a usage row. Existing
offline voice tests were strengthened for this behavior; failure/error cases
remain zero-debit and terminal replay never reruns ASR or intent.

## Verification

- Local full backend unit1843 PASS/16SKIP/1199integration deselected;8 local
  ASR/media/process cases are included, with real child timeout/cancel/overlap.
- Browser11 existing pilot cases +4 new voice cases PASS across390/1440px,
  permission denial, cancellation, late grant after close, immutable-audio lost
  ACK replay and receipt reload. Chromium uses a fake device; no person's mic.
- Real local synthetic EN/RU speech matched600/month in a sealed network-none
  container:5.810s/5.132s cold processes. These are ASR-only observations, not
  end-to-end p95 or recognition quality for real speakers/accents.
- Disposable PostGIS voice/HTTP110 PASS/1optional UI bridge SKIP, including the
  distinct stale-catalog zero-debit code. Exact-head CI is recorded separately
  in the final PR description/evidence. Counts overlap broader CI.
- TypeScript/Ruff/mypy177/i18n guard PASS; oxlint six existing unrelated warnings.
  Model hashes/dependency lock and source provenance are independently checked.

Initial failures retained in ignored output: standalone ASR initially imported
the web package initializer without backend dependencies; corrected to a direct
worker entry. Vite initially inlined the tiny worklet, which CSP rejected;
corrected to an emitted protected asset. PG harness initially used a psycopg DSN
with asyncpg settings, then lacked full public migrations; corrected only in
the disposable harness. New owner/version admission correctly created no usage
row, so old tests now assert absence rather than a zero-valued row. No test/gate
was removed. Initial raw logs and final proof are under ignored
`output/ai-voice-20261108` and owned `/srv/112233-ai-voice-review-20261108`.

## Release and continuation

At initial source commit this increment is not yet deployed; actual deployed
SHA/HTTPS microphone/ASR/search proof must be reported separately. No paid calls,
source exports/refreshes, production migrations or durable journal writes were
made during preparation. Existing50/$1 nonpersonal rental approval is preserved;
ASR adds no external paid provider. Do not reset journals, replace signing keys,
or extend original source timestamps. Rollback/revoke uses existing owned egress
stop/backend restart and retained durable state; removing voice overlay restores
voice=false without deleting history or reservations. Main production/DB0066 and
sealed3/3 demo remain unchanged. S2.1 standing data, human voice/browser quality,
S5 p95/capacity, saved/delivery and full release gates remain open.
