# AI Search continuation: S2.1 / S4.4 / S5.1 / S6

Session15–16November2026, Europe/Moscow. Canonical status and next action remain
in [completion plan](../ai-search-completion-plan.md). This is release evidence,
not a replacement roadmap or a claim of S7 completion.

## Source and runtime

PR419 source `ba311d8637d48a5c1e0c401d85dae1f7fb3e3ef7`: all13triggered workflows
SUCCESS; merged main `c8ae9f3614aa123445c4f946fb8172d29a00a47b`, identical tree
`1d1a427ae6a208f184ffb68d9903a3963f0a3d66`. PR420 source
`2f50955b3e461094d50abdb082b1fd2297e67863`: all7triggered workflows SUCCESS;
merged main `f5a1d240e8d2e55c1f2fd96251df5cae3c5d8953`, identical tree
`03ce8f4115391727ae59c65ec8439f55d45ea85e`. The smaller source workflow count is
the actual path-filtered set, not13hypothetical PASS. Exact-main push CI is separate.

Primary `f5a1d240` released by the regular runner after8/8exact-main push workflows SUCCESS; schema0080, data maintenance skipped, delivery/retention timers ACTIVE and post-release ticks SUCCESS. The approved13source cohort and independent keys/journals were retained. Calendar adoption was not executed.

Isolated issuer/ASR now uses `ttest-ai-saved-candidate:2f50955b`, image
`sha256:d53ea8a0c6803d76278b5f5e896dba190a0b22f7839b0e3560342fe83aae3029`.
All287Python files match canonical Git source. ASR model SHA256 remains
`540a5081aecc10692ec80b83499c49cbee903133178d307d1b0c9e6eccf6c68e`;
dnspython2.9.2 retained. Historical proxybf33/SPA90b68 remain intentionally
separate from the primary SPA. Release used the same13source IDs, PG/Redis
containers, keys, original approval and provider journal. Encrypted isolated
PG/journal backups were authenticated, signing keys were not copied. No seed,
migration, calendar adoption or provider request occurred; attempts30→30.

The first isolated readiness helper wrongly expected the configuration-level
`voice` capability to become false after expiry. It was interrupted through its
rollback/finally path; prior501image and refresh timer were verified restored.
The corrected helper checks runtime configuration separately from
`approved=false` at the dispatch/status fence. Rejected helper log is retained
locally; its summary is included in the proof manifest.

## S2.1: source evidence and genuine missing data

Piso housing extractorv2 recognizes exact scoped smoking clauses. A blanket
published prohibition entails an indoor denial; it creates no balcony/terrace/
outdoor permission. Qualified statements, unscoped positive statements and
negotiated exceptions stay unknown; contradictory supported observations remain
conflict. Extractor version changes force existing generation/CAS handling.

Read-only candidate extraction from13original primary snapshots:13indoor denials,
13unchanged source snapshot CAS, no source/model writes. After actual isolated
release and standing refresh: indoors known-current coverage13, matches0;
balcony coverage0/matches0. Budget700 retains13coverage/12matches, composite
room+700/month+furnished+bills retains4coverage/3matches. Known denial is different
from unavailable coverage; SQL retains those semantics.

Owner selected native listings plusPisoCompartido. Additional read-only primary
inventory found7visible native listings. All7have populated legacy capacity,
resident, available-from, minimum-stay, deposit/furniture/smoking fields; none
has available-until or a complete ordered availability range. Presence is not
explicit owner provenance or verified AI coverage. These7were not activated in
the AI catalog. Imported29Piso objects likewise were not added to the approved13.

District vocabulary, total/available unit capacity, complete dates with year,
finite stay bounds and broader source currentness remain required. No year,
infinite stay maximum, room occupancy, district or permission was fabricated.
Piso source basis and refresh limits are promised by the owner and still pending.

## S5.1: shared eligibility, proof guards preserved

The previous two baseline SQL plans exercised the single-listing predicate,
whereas actual cards/map also build a matching cohort scope. Both were inspected
on the same13objects/LIMIT20, read-only, statement10s/lock1s, JIT off.
The shared candidate CTE removes repeated public/manual eligibility evaluation
within a statement, keeping original renderer User/room-detail FROM joins.
Current proof/input signature, freshness, card values and hard matching remain
before count/order/seek/LIMIT. No persistent cache or post-page filtering added.

First candidate regression:50PASS/19FAIL. Counts were right but cards were empty
because the renderer's optional room-detail JOIN had been lost. ID-only timings
did not detect this. That candidate was never deployed. Original FROM joins were
restored and the full selected PostgreSQL suite passed70cases in481.37s.
A new volatile-counter regression independently verifies one eligibility
evaluation per candidate and immediate exclusion after source mutation.

Corrected small comparison (planning/execution ms): budget28.353/33.777 →
9.032/10.062; composite19.166/14.691 →10.759/12.539. One sample per case, with
shared-server variability; these are SQL graph observations, not p95, capacity,
browser latency or proof of broad-scale improvement. The schema-readiness
InitPlan is another visible fixed cost. ISSUE-004 and deferred large runs remain open.

## S4.4: additional real browser engines, no new paid IO

Released primary42 plus compatible isolated runtime: Edge, Firefox and WebKit
restored the existing committed composite result at390px, opened the map200 and
reloaded while preserving all four conditions and original guest identity.
Firefox/WebKit ran after spending expiry; the saved result remained readable.
Query/voice dispatch routes were blocked by the test harness and observed
provider attempts stayed30→30. No page errors. Edge remains Chromium; the
Firefox/WebKit checks add independent engines for this restoration scenario.

This does not certify live microphones, RU/ES/EN accents/media paths, a wide
viewport/error/a11y matrix or actual signup-email delivery. The deleted QA account was not reprovisioned. An initial restore harness copied
a storage snapshot containing a stale auth cookie; the final harness explicitly
filters auth cookies while retaining the same guest cookie. No password login or
new guest identity is used. Earlier browser proofs remain historical.
Frontend `src` and `public` Git trees are identical between primary42 and mainf5;
existing native card styling/commercial ordering are retained.

## Permanent spending decision and code preparation

Owner approved$50/calendar month and$5/Madrid day, without auto top-up, after
implementation/verification. See [decision package](../ai-search-developer/PERMANENT_RELEASE_DECISIONS_20261115_RU.md).
New source prepares a single-host SQLite calendar ledger with atomic day/month
reservations, exact-snapshot in-place adoption, original binding/history retention,
unknown-usage halt, idempotent usage, account/policy binding, rollback-clock and
history-integrity checks. With no separately supplied reviewed dispatch guard,
reservation is denied. Compatible PilotBudget refuses an adopted journal.

Legacy attempts have no trusted timestamps: adoption conservatively charges
**all** prior reserves to the adoption day/month, rather than deleting or refunding
them. Source preparation does not run adoption or connect the new ledger to the
provider adapter. All old dispatchers must be stopped/fenced before a future
reviewed adoption, and pre-calendar binaries must not be reactivated afterward.
Single-host SQLite is not multi-host or provider-invoice-cap certification.

Final focused calendar tests19PASS; housing/catalog36 and typed/input/privacy85
PASS. Relevant preceding calendar/pilot subset93PASS; broader preceding unit
run1988PASS/16skipped before the last storage guard/final focused case.
Final calendar app mypy/Ruff/Bandit medium/high checks pass. A separate exploratory
mypy invocation of `pilot/budget.py` exposed its pre-existing unbound DemoBudget
method typing issue; production CI's configured app/lab checks passed, and that
exploratory invocation is not described as a clean check of pilot typing.

The prior50attempts/$1artifact expired at `2026-11-15T20:59:59Z`.
Actual status confirms approved=false, attempts30; no extension/reset occurred.
Provider account reference/terms/DPA/region/training exclusion/retention/deletion
remain awaited from the owner. No arbitrary real-user outbound was enabled.

## Evidence and next dependency

[Redacted proofs](ai-search-20261115-continuation-evidence/SHA256.json) retain the
failed candidate/helper alongside corrected checks. The original32proofs remain
unchanged. Large capacity, provider/account, standing broader data, human mic,
real registration and S6/S7 acceptance gates remain open. Continue the canonical
next action; approval of monthly money does not certify these gates.


## Owner visual priority: local voice increment

The owner's16November instruction prioritizes visible compound voice search on
the actual site. The existing whole-request housing parser can return its typed
patch directly without external intent IO, then use the existing owned quota,
current-proof SQL and card pipeline. Local ASR remains the real server-side model.
This provides a permanent path for supported housing conditions, not unrestricted
language-model intent acceptance. Unknown/ambiguous clauses still reject the whole
request instead of falling back silently to budget alone.

Separate local_housing_available does not change provider approved=false or the
expired artifact. Only the local ASR/intent path becomes independent of that
external spending approval. Catalog health, resource bounds, media limits, quota,
ownership and replay remain. The public AI section gains an AI-search title and
RU/ES/EN examples with room type, furniture and bills; technical pilot spending
counters are removed from customer copy. Source119unit/parser/pilot,30browser,
and2real PostgreSQL HTTP composition cases PASS. Actual local-ASR/browser acceptance
follows exact-source CI/release. The first PG fixture failures and old-copy browser
assertions are retained; production guards were not weakened.


## Russian ASR correction before local activation

Actual offline tests found that tiny corrupted the Russian furniture phrase;
those failed transcripts are retained, never normalized into invented conditions.
Pinned Systran/faster-whisper-base revision
`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`, plus a fixed reviewed place-name
vocabulary, correctly recognized the same Russian room/LaLaguna/700/furniture
recording. English room/700/furniture/bills also passed. The place hints contain
no rental facts, prices or expected answers. Model assets are pinned and SHA256
verified; runtime inference remains offline/disposable, int8/2CPU/1536MiB,
beam5/max96tokens and the same8-second cap. Public model files alone were downloaded;
no user audio was sent outward.

Comparison with place vocabulary: tiny English4.731s PASS/Russian4.214s FAIL;
base English6.649s and Russian6.948s PASS. Controls: Russian price-only4007.651s
and price700+bills7.790s produced exactly those fields, without invented city,
furniture or accommodation; silence4.095s correctly produced no transcript.
These are single bounded samples with narrow timing headroom, not p95 or broad
accent/human/capacity certification. Actual released browser acceptance still follows.
The model card and pinned files are at
https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 .


### PR421 ASR follow-up, source-only

Exact4f source CI local voice failed SYNTHETIC_ASR_MISMATCH; failure artifact14201852346 retained. Diagnostic Base auto-detected Polish on short Russian700 samples. Beam1 also corrupted the amount and is rejected. The candidate keeps beam5 and selects among the three supported languages RU/ES/EN from detector probabilities; identical encoder-feature windows can reuse their result only within one disposable worker. Four legacy samples now retain exact amounts; Irina emits reviewed “семи сот” (same700), supported by exact Russian-hundred morpheme spelling. Compound EN/RU passed6.551/7.555s; no inferred bills for RU. Narrow timing headroom remains; not p95. Focused parser/ASR56PASS and RuffPASS. Added compound and silence fixtures to source CI, keeping per-operation8s/2CPU/1536MiB/96tokens and increasing only the sequential7-sample suite bound45→70s. Seven-case sealed smoke and new exact-source CI pending; no new release claimed.


### Follow-up after PR421 merge

PR421 source722c592b:13SUCCESS/2conditionalSKIP, merged main631e8b06 with identical treeca85d16c. Isolated722c activated,287exact Git Python blobs/Base assetsha63d9b89b verified; provider30→30, expiry enforced, cohort13 and PG/Redis/keys unchanged. Initial candidate archive was rejected by byte attestation because Windows git archive exported CRLF. Rebuilt with core.autocrlf=false and verified287exactblobs before activation; rejected candidate was never deployed. Exact-main voice run43820157421 failed on an ASR variant “комната в Лагуна…” (missingLa). Artifact14204161710 retained. No geography alias was added: that incomplete name must clarify. Follow-up adds reviewed Cyrillic equivalents to fixed place vocabulary, without prices or housing facts.35parser tests/RuffPASS; source ASR CI and live result still pending. Primary631e regular runner started from passing exact PR source/tree; its result and main CI are tracked separately. Seven-case sealed smoke of exact722c server image passed6.034–7.857s speech, silence rejected4.014s; narrow timing headroom remains. A new-vocabulary test overlapped primary build and hit8s timeout, retained as failure and not counted as pass.


PR422 firstcandidateba16 voiceCI failed on “Смибелью” despite the complete place name; artifact14203669738 retained. It is not accepted as furniture by the parser. Next candidate extends the fixed ASR vocabulary with multilingual housing nouns/inflections (room/studio/furniture/bills/balcony/terrace). This is contextual speech recognition vocabulary, not criteria substitution: no amounts, polarity or requested facts are prompted. All four price-only transcripts must remain exact and contain no injected housing conditions, and silence must reject. This narrows a demonstrated recognition failure without adding fuzzy text aliases or weakening the seven strict assertions. Validation pending. Primary631e runner succeeded/0080/data_maintenance skipped, delivery/retention timers restored and post-release ticks succeeded. Exact-main original voice failure remains recorded separately from passing source722c CI; full release gate is open.


PR422 glossary061b failed price-only Irina (“до 7 сотья в ров месяц”), artifact14205051259 retained; both glossary variants rejected and worker restored to released722c place-only vocabulary. Production host is AMD EPYC/AVX2; CTranslate2 dispatch differs from CI vendor/ISA. New candidate pins worker CT2_FORCE_CPU_ISA=AVX2 and CT2_USE_MKL=0 before import (upstream environment-variable contract), keeping int8/beam5/8s/2CPU/1536MiB/96tokens. Sealed seven cases on actual722c image with only candidate parent module mounted: speech4.992–6.361s all exactPASS, silence-reject3.770s;44unit/Ruff/types/i18nPASS. CI of this new candidate remains separate. No inference that vendor dispatch is the sole root cause until repeatability proof.

Actual primary631e Chrome microphone UI (synthetic PCM through normal capture path): EN room700/month+furnished+bills→3, Stop-to-result9.900s; RU room+LaLaguna+700/month+furnished→1,6.961s. Provider30→30 in both, original guest preserved, no paid API IO. Added unsupported complete party2adults/0children after RU:SOURCE_COVERAGE_UNAVAILABLE, used2/reserved0/remaining1, previous result/hash unchanged. Initial live harness clicked NewConversation while restoration was still running and then expected a notice even without loaded result; no query was sent. Corrected harness awaits restoration and exact reset response; candidate UI also disables that button during restoration, consistent with its handler guard. These live successes do not erase original main voice CI failure or close human-microphone/p95/fullrelease gates.
