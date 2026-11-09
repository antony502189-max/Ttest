# S4.1: Russian “до семисот евро в месяц”

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
