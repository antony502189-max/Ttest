# S4.1/S4.4 RU/ES/EN human speech, 18 November 2026

This increment fixes two English text-to-conditions rejections and adds independent public human speech diagnostics. It does not change the released ASR engine or attest complete voice acceptance. Verified remote main remains `f5ba0c18edc4083c6087cbb5648ebe54269d218d`; work continues from the clean existing checkout and its retained plan3.57 on a new `codex/ai-search-human-voice-ru-es-en` branch. The old root checkout was not reset, checked out or stashed.

## Confirmed parser failures and change

The attributed public text [Tatoeba2258804](https://tatoeba.org/en/sentences/show/2258804), _undertoad, CC BY2.0FR, says “I need to rent a room.” Existing `I need` handling left `to rent` unconsumed. Four bounded present-tense renter prefixes now work: `I need to rent`, `I want to rent`, `I would like to rent`, `I'd like to rent`. The whole remaining request must still become typed conditions. Renting out, past-tense narratives, third-person statements, alternatives, unknown locations/conditions and foreign currency still reject atomically.

The composite regression also exposed an independent rejection of `not furnished`. Direct `not` before the existing boolean vocabulary now sets a hard false, preserving the same verified-negative matching contract. It does not remove a criterion. `not necessarily`, double negatives, conflicting values and unknown negated conditions still reject; existing unrelated party constraints survive. No schema, quota, matcher, saved reader, provider or ASR setting changes.

Before repair: four prefix composites failed; after the prefix repair, eight explicit-negation/composite checks failed. Final97housing tests pass, including24new cases. Full backend unit: **2108PASS/16SKIP/1268integration deselected**, RuffPASS, mypy189filesPASS, diff checkPASS. All33public diagnostic transcripts were replayed against the new parser and rejected as unsupported narratives. Exact-source CI and deployment remain separate checks; the initial pre-push validation checkpoint did not claim CI. The final source result is recorded below.

## Public human data and licensed use

[Mozilla Common Voice17, fsicoli mirror](https://huggingface.co/datasets/fsicoli/common_voice_17_0), pinned revision `8262c16bf297c87a9cd88c51997c4758ed7a8ba2`, **CC0-1.0**. Nine complete test recordings, three per language, were selected by housing/rent vocabulary before inference. Nine distinct pseudonymous client IDs are hashed; physical speaker identity or accent balance is not independently certified. Independent references come from the dataset sentence field, not ASR. No manual listening certification is claimed.

The entire MP3 is decoded and resampled to canonical16kHz mono PCM16. No words or failed portions are cut. Source tar/TSV/member/PCM hashes and byte offsets are retained in [evidence](ai-speech-ru-es-en-20261118-evidence/README.md). Bounded range reads extracted the nine members without downloading the three complete396–750MB tar files. Original clips remain ignored engineering fixtures, not committed audio.

These are housing-related **narratives**, not positive rental-search acceptance. They test recognizer behavior and safe whole-request refusal. The Spanish sample containing `dos dormitorios` provides a real spoken quantity, but does not establish Spanish housing-query acceptance. No corpus score below closes that gate.

Tatoeba legacy api_v0 omitted audio-license details. The v1 API and sentence audio details revealed **CC BY-NC-ND3.0** for the discovered English CK and Spanish arh recordings, unlike the CC BY sentence text. Those recordings were excluded from ASR and redistribution. Only the separately licensed attributed English text seeds the parser regression. A Spanish owner recording is not required.

## Identical full-recording comparison

Released producer image `sha256:7b3fb5810f51978ff70a7753360e35ff38f36410d6e271eef656e696629f8ebc`;2CPU/1536MiB, swap disabled, read-only/network-none, uid65534, dropped capabilities, Docker logging disabled. The unchanged Small has beam5, fixed reviewed place hotwords,96tokens,18s audio and15s public preparation limits. References never configure ASR.

| Variant | Complete | Audio stage | Word edits / reference words | Peak bytes |
| --- | --- | --- | --- | --- |
| Released Small |9/9|8.261–15.899s|6/80|1221169152|
| Same Small, only hotwords removed |9/9|7.436–11.284s|5/80|706187264|
| Existing Parakeet prototype |9/9|1.229–2.321s|4/80|1050562560|

Small changed `lodger` to `larger`, `tenant` to mixed-language `La Tener`, and Spanish `dos` to `tonos`. Removing hotwords changed the English error to `tanner`, retained the Spanish quantity error and introduced a Russian `Вскоре`→`Скорее` change. It is **not adopted**. Parakeet preserved the Spanish quantity and `lodger`, but still produced `Lieutenant` for `The tenant` and changed Russian `одну` to `одно`. It is faster on these samples, not uniformly error-free.

All three variants reject all nine complete transcripts, as required for these narratives. Raw token edits are diagnostic: accents, dataset punctuation/reference differences and inflection are not a calibrated semantic-accuracy metric. The memory difference between Small runs is not credited to tuning: cache charging and run order differ. Parakeet preparation was7.068–8.280s. All cgroup `max`/OOM events were0 and swap.max0 in these runs. No browser latency or p95 claim follows.

## Quiet/noise/pause stress

One fixed complete clip per language produced a -20dB gain variant and a deterministic20dB-SNR white-noise variant with1s leading/0.5s trailing silence. This is six **derived** cases from three existing recordings, not six independent speakers or real recordings in noise. Small completed6/6 in7.520–9.985s, peak706285568bytes, no swap/OOM. All six remained atomic clarifications. The noisy Russian fragment changed `Вскоре` to `Скорее`; originals and failures are retained.

## Authorized owner recording, imported app and privacy

The previously authorized single private recording was reused over stdin only, with original, -20dB and noise/pause variants. Both engines preserved the **complete expected typed conditions in all three variants**. Small audio7.993–8.613s, Parakeet2.433–2.527s. Full primary application routes/modules were imported and held in the parent; no lifespan, database/Redis connections, HTTP/business queries or live identity was started. Small peak747057152bytes, Parakeet1042374656bytes, swap0/max0/OOM0. Two Parakeet raw lexical comparisons differ while typed conditions remain equal; no exact-transcript claim is made for those cases.

These shared-file repeated runs do not supersede the earlier1536MiB peak. In particular, private Parakeet `memory.stat.file` was0: shared host page-cache charging is not a cold immutable-composition test. Full lifespan/PG/Redis/HTTP concurrency, cold cache/memory behavior, completeness and privacy/packaging gates remain open.

Only [redacted results](ai-speech-ru-es-en-20261118-evidence/owner-redacted-summary.json) are public. No original private audio, transcript, filename, exact query values or transcript hash is published. New private diagnostics disable Docker logging and swap; all source audio stays in memory/stdin with no explicit remote audio files. The earlier temporary-json-file logging correction remains part of the history and is not erased.

## Limits, failures and next action

Corpus-viewer HTTP500 authentication-service errors were bypassed with pinned public files, not authenticated/private data. A metadata discovery print TypeError and deliberately incomplete tar-preview ReadError were harness failures before inference; neither is a product success/failure. An initial composite test used unsupported `not furnished`; that exposed and then separately reproduced the explicit-negation defect above rather than silently accepting a partial request.

The production image/settings and provider/cohort/identity/quota state were not changed. No new guest, reset, live business query, paid call, external audio receiver or large capacity benchmark was used. Effective session file/network access is unrestricted, with approval policy never; that grants no spending or quota exception.

Next: complete current-source CI/review of the parser increment. Continue S4.1/S4.4 with freely reusable human **positive** housing requests in RU/ES/EN, complete numbers/places/negations and the existing microphone→ASR→conditions→cards path. Before a possible engine change, complete cold composition/memory, long-tail completeness, private-audio lifecycle and immutable packaging checks. Prior two live clarification failures, human ES/EN positive acceptance, browser p95, native authenticated200/signup-email, data/provider and fullS7 remain open. A new live business-query allowance would require a concrete separately approved test after independent preparation; none is assumed here.

Evidence packaging check: initial Git auto-CRLF conversion changed archived byte hashes. A directory-specific `-text` rule now preserves the captured files exactly; canonical Git blob hashes are checked after staging. Application code and inference results did not change.

## Immutable parser candidate, not activated

Candidate image `sha256:4388af9a69e406441af549abaa8c14c42fcb64dda4382ab35f554ed90248e6a6` is built from source `b88d7280b6acc6dfcb757bd973bb2e7ddf126c4f` on the exact retained released Small parent7b3fb581. All287Python app/demo/pilot/alembic files match the Git archive; only `app/services/ai_housing_input.py` differs from the released parent. All4model assets match the retained manifest. No dependency/model install or download, frontend change, migrations or service activation is involved.

Offline network-none/read-only/logging-none/no-swap candidate checks passed four complete positive English composites and four atomic refusals. Source/image/actual release remain separate. The source archive hash, complete input manifest, Dockerfile and successful argument-array builder/probe are retained. Initial local-image-ID Dockerfile resolution, premature missing-image probe and a PowerShell remote-substitution quoting error were packaging harness failures; their correction did not change application/ASR behavior. See `packaging-attempts.json`.

Additional public-data discovery read only Common Phone text/language/speaker columns across27pinned Parquet shards (about76krows; no audio-column download) and the small Colombian Spanish OpenSLR72 line indexes. The searched housing/rent patterns did not supply a positive supported rental request; these sources are not claimed as extra voice acceptance. Restricted Tatoeba audio was not substituted for missing freely reusable samples.

## Exact-source CI and review handoff

[PR430](https://github.com/antony502189-max/Ttest/pull/430), source `b88d7280b6acc6dfcb757bd973bb2e7ddf126c4f`: **13/13 actual PR workflows SUCCESS**, including local ASR, security, Full audit, production, mobile, combined PostgreSQL/HTTP/browser and frontend checks. The archived source CI record identifies all13runs. Subsequent evidence-only documentation commits retain the same1080runtime-input projection; their own CI is tracked separately. No merge, deployment or live business acceptance is implied. Candidate4388 is still inactive; actual site parent7b/mainf5 remain unchanged.
