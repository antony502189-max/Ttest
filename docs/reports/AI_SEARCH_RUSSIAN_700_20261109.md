# S4.1: Russian “до семисот евро в месяц”

## Owner confirmation and PR completeness

After the255b65ef release the owner confirmed in this chat that voice input
actually works. This is one owner-observed scenario, not a human/accent/browser
benchmark or p95 certification. The retained failed synthetic attempt below is
not deleted or relabelled. The owner next requested verification that every
change is included in PR412; [the completeness audit](PR412_COMPLETENESS_20261109.md)
records the source and final evidence synchronization.

Owner explicitly reported saying “до700евро вмесяц” in Russian. The stored
operation aggregate had terminal INTENT_UNSUPPORTED failures; no owner audio or
transcript was retained or inspected. The previous microphone availability fix
was insufficient evidence of human speech acceptance.

The reported class of failure was reproduced with locally generated Russian
speech. The same phrase “До семисот евро в месяц.” in Microsoft Irina Desktop was
misrecognized by the deployed tiny/beam1 worker as “до7сут и вравмесяц”; Microsoft
Pavel yielded700correctly. This is a synthetic reproduction, not proof of the
owner's exact ASR output. Forcing Russian alone did not fix the Irina sample;
a domain prompt also failed. No expected amount was provided to the model.

Beam5 correctly transcribes both700samples, while retaining the original EN/RU
600samples. It uses the same pinned model, local-only dependencies,2CPU/1536MiB,
8s child deadline and15s PCM bounds. A sealed network-none container running the
actual async adapter passed all4fixtures in4.979/4.018/4.221/3.835seconds. This is
four synthetic observations, not p95/human/accent certification.

The positive grammar now recognizes exact Russian cardinal forms, including
“семисот” and“семьсот”, within the existing50–1000EUR/month range. It still matches
the entire utterance, rejects unknown tokens/personal/instruction suffixes,
ambiguous amounts and out-of-range values, and reconstructs only the previous
canonical English constants/amount for the existing provider. It never guesses
700from the garbled transcript. Initial new numeral tests exposed greedy capture
of“евро”; the corrected bounded pattern passes. No new provider/spending scope.

The UI now distinguishes ordinary busy processing from ambiguous replay. The
pilot's replay action is explicitly“Проверить результат попытки”. A terminal voice
grammar rejection explains failure to read the budget, releases the pending UI
and permits retry; it does not incorrectly instruct the owner to settle a live
operation during normal processing.

Source validation:74focused unit tests PASS (pilot/privacy/review/local-ASR),
19pilot browser PASS including delayed voice response/terminal rejection,
same-key lost-ACK replay, cancel, quota/stale and permission handling.
Ruff/TypeScript/lint/i18n PASS;4real local synthetic ASR fixtures PASS offline.
Runtime deployment, exact-head CI and the authorized live Russian700voice→SQL
sample must be recorded separately. Up to this source-preparation point, new
agent paid calls0; original approval, provider journals, signing and cohort/TTL
remain unchanged. Existing full release/human/performance/saved/delivery gates
remain open.


## Final closed-pilot release and limits

Released source255b65ef3efffcfb2606000204a8dfb47163b307 to the same protected
pilot, with backend/maintenance/egress image
sha256:45baf80a5d28e311a642e669f6a4d31c8cede77faf775bf4d8d2cf3feda6ee12
and frontend sha256:72bc677b1f89dfd7ac76bcd85c87c24577e3f215fcf0bdfcd619d912bd66c6b3.
Actual image async-adapter4fixtures PASS,3.607–4.302seconds, no inference network.
Changed runtime files match Git source after explicit CRLF→LF normalization;
source provenance1031inputs PASS. Model assets/dependencies and8s deadline unchanged.

One real HTTPS synthetic Russian microphone sample completed700EUR/month→12
verified listings,8394ms Stop→conditions. Reload at390px restored the same result
without another upload/paid call. One business debit, one authorized provider
call8→9/50. Current status: catalog_ready=true,approved=true,halted=false. The
30min catalog timer is active with service Result=success/ExecMainStatus=0.
Approval, signing, original snapshot, environment/provider journal were unchanged
at cutover; PG/Redis containers retained, migrations/seed/reset0. Backup:
`/srv/112233-ai-site-pilot-20261108/backups/ru700-255b65ef-20261109T190126Z`.

Important remaining quality limit: the first actual-browser synthetic attempt
on this same release still returned INTENT_UNSUPPORTED, with no paid call/debit.
The second passed; this is not a claim of perfect recognition. A separately
captured synthetic browser waveform also transcribed700 correctly offline.
The first rejected waveform was not retained, so its exact acoustic cause is
not proven. Human acceptance and browser/microphone quality remain open. No
owner's audio/transcript was stored or inspected. Keep the failed live proof
alongside the successful proof; do not relabel it as a successful paid test.

Three further separate Chrome microphone captures of the synthetic Irina700
phrase all decoded correctly as700 in the deployed-image network-none worker,
5.441/5.141/4.842seconds including container startup. No provider calls. These
additional captures did not reproduce the first browser rejection; they do not
erase it or prove its cause. [Additional capture evidence](ai-russian-700-20261109-evidence/extra-browser-captures.json).

Initial staging build missed Dockerfile-specific ignore files and failed before
deployment; packaging was corrected without runtime-source changes. The first
cutover automatically rolled back because the operator script incorrectly
expected Docker Health on the minimal pilot (which has none). The corrected
probe checks the real private status endpoint before frontend activation.
No DB/journal restore/reset occurred; the rollback and eventual successful
cutover are distinct from ASR acceptance. Unchanged original-model/8s bounds
are not p95 or full15s speech-quality certification.

Exact-head CI13workflows SUCCESS/2conditional SKIPPED. Test merge
9fa3e6ecdee488d6d15ec28c461ca3b9281be5dd has the identical
tree3d7d9e3a7b088645884fe7a1f616a4f352df5f9f. CI local-ASR4 and pilot-browser19
PASS;74focused local units PASS. See [evidence](ai-russian-700-20261109-evidence/ci-final.json),
[successful HTTPS proof](ai-russian-700-20261109-evidence/live-voice-second-proof.json)
and [retained failed proof](ai-russian-700-20261109-evidence/live-voice-proof.json).
Next: owner repeats the Russian phrase on their own microphone. If rejection
persists, continue S4.1 acoustic/browser diagnosis; do not substitute more source
freshness work or call human quality complete. S2.1/S5/saved/delivery/full-release
gates remain open. PR412 remains for owner review; no merge was performed.
