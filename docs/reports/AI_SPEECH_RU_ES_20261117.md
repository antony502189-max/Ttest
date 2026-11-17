# S4.1/S4.4 Russian and Spanish live-speech work

The owner explicitly prioritized human Russian/Spanish voice search over the prior authenticated-routing increment. The released primary49d7fcc0/isolatedb0/Whisper Small image60a1c713 were not changed in this session.

## Source changes

A correctly recognized Spanish spoken amount could fail intent parsing: all7new exact full-request cases initially failed (setecientos, seiscientos cincuenta, novecientos noventa y nueve, mil, mil quinientos, dos mil trescientos veinticinco, veintiún). Exact cardinal forms1–9999 now preserve numeric value, including cien/ciento, irregular hundreds and apocope. The article un remains outside global number normalization so piso de un dormitorio stays intact. Ambiguous, incomplete, contradictory, foreign-currency and unknown-tail requests still reject atomically.

Five natural full RU/ES sentences also initially failed. Known search prefixes and the ordinary Russian location case «в Ла Лагуне» are now supported. A separate Parakeet prototype transcribed the existing complete Russian fixture with «Лалагуна» as one word; that rejection was preserved before repair. Joined names are derived from complete existing aliases only, preserving every letter; collision detection includes every canonical municipality, including ones excluded from unique aliases. Changed or missing letters are not corrected and unknown places are not substituted.

Local validation:117targeted testsPASS,2050backend unit testsPASS/16SKIP/1257integration deselected, RuffPASS. Full exact-source CI and compatible release remain separate gates. No ASR production-engine switch is part of these source changes.

## Human diagnostic comparison

[PolyAI MINDS-14](https://huggingface.co/datasets/PolyAI/minds14), Daniela Gerz et al.,2021, CC BY4.0:3RU and3ES full telephone-banking recordings, selected deterministically before inference. Original Parquet and derived PCM SHA256 are recorded. G.711 mu-law was decoded and resampled to canonical16kHz mono PCM16; no utterances were cropped. See [comparison](ai-speech-ru-es-20261117-evidence/human-comparison.json).

| Variant | Completed | Audio-stage duration | Peak bytes |
| --- | --- | --- | --- |
| Released Whisper Small, beam5/place hotwords |5/6|14.015–17.433s plus one18s timeout|631529472|
| Same Small without hotwords |6/6|12.955–17.459s|631549952|
| Parakeet TDT0.6b v3 int8 prototype |6/6|2.152–3.498s|999239680|

All inference used network-none/read-only containers,2CPU,1536MiB, uid65534 and one recording per disposable child. Timing excludes public model preparation (bounded15s), HTTP and card queries. Per-sample transcription accuracy is mixed; removing hotwords did not improve aggregate errors and is not adopted. MINDS references contain possible omissions/noise, so raw WER is diagnostic and cannot establish general accuracy. Telephone banking speech is not acceptance of housing queries, accents or this site's microphone capture.

[NVIDIA Parakeet TDT0.6b v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) supports RU/ES under CC BY4.0; this experiment uses the k2-fsa/csukuangfj ONNX export at ed5d745623472f97cfc2e6c2916ee248798fc5a8 with independently hash-verified maintainer wheels. The model is a prototype overlay, not an application composition. Model files, wheel provenance and exact executed public diagnostic scripts are retained in [evidence](ai-speech-ru-es-20261117-evidence/README.md).

Initial Parakeet semantic test rejected the joined La Laguna name. After source word-boundary repair, all6existing synthetic speech fixtures preserved their complete expected typed conditions and silence rejected without timeout:7/7PASS, audio1.506–4.021s, memory peak1001852928bytes. Original failure and diagnostic are retained in [semantic evidence](ai-speech-ru-es-20261117-evidence/sealed-semantic.json). This does not demonstrate Spanish housing speech or real microphone quality. Four additional synthetic normal/quiet Russian probes completed; they do not explain the prior two live clarification failures whose audio was not retained.

Initial semantic harness selected the ASR-only Python, which lacks the app's HTTPcore dependency. It was corrected to the app interpreter without a runtime change; this setup failure is not an ASR result. FLEURS viewer rejected oversized Parquet row groups; it was not used. Initial direct server asset download failed at TLS; public pinned CDN bytes were verified instead. A PyPI/HF wheel hash mismatch was rejected before using independently published HF-wheel hashes at a fixed revision. No downloaded customer voice, live business query, new identity or paid inference was involved.

## Remaining acceptance

One owner Russian recording and its independent reference were subsequently supplied; see the owner check below. No Spanish owner recording is required; use independent public human speech for ES. Next checks must cover real RU/ES housing speech, numbers and negations, full place names, pauses/noise and sample-level failures. The prototype also needs final engine composition, dependency/security checks, private-audio lifecycle, truncation/completeness policy, immutable packaging and compatible release evidence before switching the live recognizer. Primary authenticated200, signup-email, source/provider, performance and fullS7 gates remain open.

## Owner recording and explicit headcount (3.54)

One6.04-second owner-supplied Russian OGG recording was processed directly over stdin in offline disposable containers. Both recognizers matched the supplied reference; the reference was not supplied as an ASR prompt. The failure was the party contract: a total-only request could not be represented without inventing adult/child composition. The owner cannot provide Spanish speech; Spanish acceptance continues with public human data instead.

Add the mutually exclusive party value variant `{persons:N}` for1–10people, alongside the unchanged legacy `{adults,children,relationship}`. Counts remain hard/soft criteria, confirmed by BOTH current capacity_total and available_spots. Child/couple/friends rules apply only when actually specified in an age-specific party. Neutral follow-ups never erase known child/relationship constraints; incomplete explicit-age composition still clarifies. The browser renders total-only values without invented adults or zero children. Signed handoff preserves the exact value; SQL, inventory-consistency and saved/card/map parity regressions are included for CI.

Rollback now checks for real total-party schema, matching and summary readers before stopping a healthy journal-enabled release. Existing main49d7fcc0 lacks this new reader. A compatible retained release and paired primary/pilot packaging are required before live total-only snapshots are enabled; no activation or deploy was performed here.

The same owner input passed the corrected current-Small→candidate-parser path with exactly the requested fields. Small audio-stage reruns were13.096/10.425/14.213seconds, not independent speakers or end-to-end latency. Parakeet matched at2.571seconds but touched the1536MiB cgroup memory limit in the app-context diagnostic, so production memory suitability remains open. See [redacted summary](ai-speech-ru-es-20261117-evidence/owner-russian-summary.json); original audio, exact transcript, filename and query values are not published.

Initial diagnostic containers used Docker's json-file stdout logging. The earlier never-written claim was inaccurate: those temporary logs existed until --rm removed the containers. Cleanup was verified; only the3standing pilot services remained. The corrected owner check used --log-driver=none and disabled container swap, with no explicit audio files or retained diagnostic containers. This does not change the site's logging configuration or claim a new production privacy acceptance.

Current local checks:2073backend unitPASS/16SKIP/1268integration deselected;194targeted and39handoff/runtime checksPASS; mypy189files/Ruff/TypeScript/i18nPASS;94Chrome browser casesPASS. The initial local managed-Chromium executable was absent(92setup failures/2pure formatter checks passed); an ignored Chrome launch config fixed the harness, keeping original failure traces. Source761321c4 has13CI successes; the new headcount increment requires its own exact-source CI. Site runtime, budget, keys, identities and saved owner data are unchanged.

## Exact-source security blocker

Source24d65cc2bc60398f15ccc9dcdf695c75323d5432 failed [Security dependency and static audit44152552628](https://github.com/antony502189-max/Ttest/actions/runs/44152552628). Python exact-graph audit and static checks passed; npm audit failed on existing picomatch4.0.7 and its dependent Vite build graph (5high entries, one root advisory). Local full-graph npm audit reproduced the failure. [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), updated17November, lists affected versions<=4.0.7 and no patched release; npm latest was4.0.7 at verification. No security allowance, threshold reduction or force-downgrade to Vite6 was applied. Prior source761 CI does not supersede this failed gate. Other exact-source workflows were still finishing when this checkpoint was written. No merge or deployment occurred.
