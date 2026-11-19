# S4.4/S6 — native registered foreground, 18 November 2026

The public beta previously stripped bearer tokens and used its isolated guest database even after login. The primary application installed saved-search consumers, but no foreground runtime. This change adds explicit primary account composition for the existing text/voice/session/result/quota API. It remains **disabled by default**, independently of the already released guest search. A source implementation or mocked browser result is not actual account200 acceptance.

## Ownership and data

Native requests require a valid primary bearer and active account. Anonymous, cookie-only, invalid-bearer and blocked-account requests do not fall back to guests. The existing durable ledger supplies200/day Europe/Madrid; sessions, voice, receipts, cards and save-token issuance share one authority. No ledger, journal, old signing key or user is reset. Independent operator-provisioned IP/cursor keys are required; the existing handoff key is reused only for its already approved save purpose, never as a cursor/IP key.

The explicit existing saved-search source cohort is required. `VerifiedCardSearch` restricts its SQL candidate population to the configured anchors **before coverage, count, order, LIMIT and map**. Current authority, proof, visibility, fact/card value and freshness checks remain in force. Membership is read inside the query transaction, and the signed cursor includes the scope. No crawl, import, wider cohort, new fact or inferred housing attribute is introduced. The unscoped existing constructor retains its previous context and behavior.

The native parser uses the existing strict local supported grammar and verified SQL, with no provider IO or expired approval bypass. Unknown clauses, ambiguities and missing coverage remain separate failures/clarifications without a successful debit. This is not unrestricted model acceptance.

## Browser authority

Account traffic explicitly targets primary and retains bearer. Public guest traffic explicitly omits bearer, including its save-token request. Login/logout remount the panel under different locator namespaces; private text/audio/criteria are not put in storage. Normal login opens the account scope. Only the explicit `?ai=save` return may reopen an existing guest snapshot, under its original authority, read/save-only. Starting a new conversation exits that return and opens an empty account scope; it does not transfer guest quota or pending payloads. Account results use the existing native map and pass the same authority through paging, map and save.

Transport recovery is also fenced by session generation. Old401 responses do not retry under a new login, and late refresh responses cannot replace its token. Logout invalidates local authority immediately. Cookie-mutating login/register/Google/logout/refresh requests are serialized so a delayed revocation cannot delete a newly installed account cookie. Authentication errors do not recursively refresh while holding that queue. Tests include actual delayed HTTP responses and a browser cookie, not just a mocked counter.

## Explicit deployment configuration

Both backend mode `AI_REGISTERED_SEARCH_MODE=local-housing-accounts.v1` and build flag `VITE_AI_REGISTERED_SEARCH=1` must be deliberately paired. Defaults are off. Required files are `AI_REGISTERED_KEYS_FILE`, existing `AI_SAVED_COHORT_FILE` and `AI_SAVED_HANDOFF_KEY_FILE`; saved mode remains `signed-housing-inapp.v1`. Key schema is `ai-registered-keys.v1` with independent32byte base64 `ip`/`cursor` fields. There are no default/generated keys in application startup.

Local Small assets/interpreter must be explicitly provisioned via `AI_REGISTERED_ASR_PYTHON` and `AI_REGISTERED_ASR_MODEL`. Startup verifies all4fixed model hashes and rejects missing, modified, extra or linked files; it never downloads a model. The interpreter/dependency artifact also needs independent release verification. The same one-use worker/preparation/private-audio lifecycle and18s ASR/2s intent/24s operation budgets are retained. Native startup requires the **full composition** to have1536MiB memory, swap0 and at most2CPU in cgroup v2. Production Compose exposes explicit resource variables `AI_REGISTERED_MEMORY_LIMIT`, `AI_REGISTERED_MEMORY_SWAP_LIMIT`, `AI_REGISTERED_CPU_LIMIT`; off/default0 preserves the prior ordinary backend resource configuration. Missing required assets, resource caps, schema, Redis, journal binding/replay, saved configuration or configured cohort fails startup.

Public Small assets were staged from existing immutable image4388af9a:9096file hashes, manifest SHA256 `d8f5dc9f5d607aec18a33521856984b64080715409923ee4ab594ec973b9dd75`, all4model assets identical to revision536b0662. This staged package is inactive; **zero new keys/configuration/live queries** at this checkpoint. Full native cold composition, exact-source CI, actual release and existing-owner read-only200 observation remain required before activation/acceptance.

## Verification checkpoint

Local backend:2144PASS,16SKIP,1270integration deselected; Ruff/mypy190app filesPASS, TypeScriptPASS, lintPASS with pre-existing unrelated warnings. New unit cases cover opt-in, independent keys, exact cohort, fixed model hashes, shared session/voice authority, resource/swap bounds and anonymous no-mint/no-read. New PostgreSQL tests cover scoped coverage/cards/count/pagination/map/cursor and actual account200→199/replay/anonymous denial; **their execution is pending CI**, not counted in the local2144.

Browser validation uses dedicated remote-provider mode and explicit native flag, never real credentials/provider traffic:9/9PASS, covering390/1440px text/voice, native map without another query, reload, explicit save, separate guest return and delayed auth/cookie races. Source validation and artifact hashes are in [evidence](ai-registered-foreground-20261118-evidence/SHA256.json). Existing15public and94AI/map/saved browser cases pass. The first ordinary AI attempt could not launch absent bundled Chromium; the owned rerun used installed Chrome with unchanged assertions. Subsequent source changes are verified separately. These are controlled browser contracts, not a released live microphone/p95 or actual owner quota proof.

## Related increments and remaining delivery gates

PR430 is actually released: primary07ebc1d5, guest backend image4388af9a, verified287Python files/4model files,5read-only HTTPS endpoints, all3timers active. Provider30→30, cohort13, protected keys/state and existing PostgreSQL/Redis preserved, encrypted backups authenticated. SSH interruption was recovered through the independent regular release unit; final proof and timers were checked afterwards.

PR431 human-Spanish furniture repair passed13/13source workflows and merged asdcadba27. Its inactive image22f55c50 verified287Python/4model files and passed all11public FSI audio expectations in a second actual ASR run. Lower706MiB cached-run peak is not credited as a memory optimization. Main-wide CI and its actual rollout are separate from source CI. The packaging root-directory guard rejection and repair are retained.

Human positive composite EN, fuller ES/RU coverage, real microphone/p95, signup/email, broader data/provider/performance and complete S7 remain open. SpokenWOZ official audio is CC BY-NC4.0 despite permissive mirror tags; no such audio is used. Taskmaster's published text documentation does not establish a downloadable audio release. LibriSpeech text-only search examined132553rows across clean100/360 and yielded no supported complete housing request; no clips were cropped or relabeled as positive acceptance. The owner is not asked for ES/EN recordings.


## Actual release and owner checkpoint3.62

Final source f9fef02e:13actual workflows SUCCESS/2conditional SKIP, including real PostgreSQL scope and account200→199/replay tests. The original reserved .test registration fixture failure and targeted rerun of the cancelled combined job remain distinct from the final PASS. Main5cb1503a has exactly the reviewed source tree; main-wide audit is tracked separately in evidence.

Full native cold composition with existing primary PG/Redis/journal/cohort13 passed startup and six complete public audio expectations under2CPU/1536MiB/no swap: startup13.386s, final peak1342234624bytes, OOM/max events0. File-page eviction was restricted to owned public artifacts; this is not whole-host cold boot or browser p95. The first attempt's incorrect bind-mount assumption was rejected before key changes; actual named-volume authority and protected hashes were verified.

Ordinary production runner actually released5cb1503a with paired native flag1/mode. Existing keys/state/cohort and PG/Redis/MinIO were preserved; independent native IP/cursor keys were provisioned once, never reset. Public9096assets/4model hashes, encrypted authenticated backup with decrypt roundtrip, schema0080/data-maintenance skipped, postticks and all3timers passed. Actual ordinary primary271Python files exactly match Git blobs. A failed comparison against the Windows-CRLF pilot manifest was corrected by generating a separate Git-blob manifest; no normalization was used for final byte equality. Pilot22f55c50 remains unchanged. Five HTTPS read-only checks passed; provider attempts remain30 and expired approval remains enforced.

Existing normal Chrome/account opened the normal text dialog and displayed200 remaining. No new business query, identity, quota reset, exported cookie/token or archived private screenshot. Actual account debit, microphone, new notification delivery and full S7 remain open. Earlier source-only/inactive/zero-new-keys paragraphs above describe historical checkpoints, not the current deployed state.


## Owner-authorized actual query and Save3.63

The owner expressly authorized one native local text query and explicit Save. Normal existing Chrome/account showed the correct long/room/La Laguna/700EUR-month/furnished criteria, one550EUR-month card, and quota200→199. Explicit Save confirmed success and notifications enabled; actual delivery is not claimed. The first Save click was rejected as outside window bounds; scrolling and fresh observation preceded the actual click. Subsequent reload verification was stopped by Windows browser URL policy. No further browser input or bypass; reload, server SQL equality and rematch/delivery remain separate open checks. No new identity, quota reset or credential export.
