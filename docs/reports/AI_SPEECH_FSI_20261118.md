# S4.1/S4.4 — real Spanish furniture-negation repair, 18 November 2026

Two complete public human utterances, “¿Sin muebles?”, are correctly transcribed by the existing Small recognizer as “sin muebles.” and “Sin muebles.” The released parser rejects both. This change recognizes explicit absence of furniture as `furnished: hard false`, preserving the committed budget and party. It also covers the equivalent exact phrases “sin amueblar”, “unfurnished” and “without furniture”. Nouns alone do not become requirements. Conflicts, double negatives, alternatives and unknown tails still reject the entire turn. Matched Spanish question punctuation is accepted without discarding words.

## Independent reference and license

The source is the original US government **FSI Spanish Basic Course, Volume 1, Unit 7A**, archived by [Yojik](https://fsi-languages.yojik.eu/languages/FSI/fsi-spanish-basic.html). The archive's [license statement](https://www.yojik.eu/index.html) identifies FSI course material as public domain. This is the original course, not a separately copyrighted remaster.

The [student text PDF](https://fsi-languages.yojik.eu/languages/FSI/Spanish/Basic/Volume%201/Fsi-SpanishBasicCourse-Volume1-StudentText.pdf), PDF pages230–231 / printed7.3–7.4, provides the independent bilingual reference. Page230 was rendered and visually inspected. The [original MP3](https://fsi-languages.yojik.eu/languages/FSI/Spanish/Basic/Volume%201/FSI%20-%20Spanish%20Basic%20Course%20-%20Volume%201%20-%20Unit%2007A.mp3) is10,271,539bytes, SHA256 `3ac4dea27f39890d17825dcbb2b5d97e368760ce16abf5bf90b1a13715f2cf87`.

Public discovery retained all91 complete VAD regions in the first600seconds; one25.728s region was explicitly rejected rather than shortened. All11 complete furniture/utility drill turns selected for evaluation are retained, including repetitions and failed transcriptions. Selection was based on printed reference and clause boundaries, not Small recognition success. Reference text was not supplied to ASR. These are classroom reading/drill turns, **not spontaneous composite rental requests or independent-speaker acceptance**.

## Results and limits

Small completed11/11, using a fresh child per sample,2CPU/1536MiB, network none, readonly filesystem, logging none and swap0. No cgroup max/OOM events; peak1,225,814,016bytes. Audio processing7.608–11.436s; preparation3.398–6.840s. Both furniture-negation turns have zero word edits and failed only at parsing before repair. Other turns preserve clarification: “No, amueblado.” is a contextual correction, “¿Cuánto al mes?” lacks an amount, and “Doscientos, sin incluir luz, agua ni gas.” has unsupported utility exclusions and no explicit currency/period. No price-only result is produced. The recognizer's “No, ha mueblado” errors are retained.

All11 unchanged Small outputs and all11 printed references were replayed against the repaired parser:2 explicit-false turns and9 clarifications match their expectations. This is **parser replay**, not a second ASR run, a browser query, or a release result. The before-repair regression run had5FAIL/10PASS. After repair112housing tests and full2123unit testsPASS/16SKIP/1268integration deselected; RuffPASS, mypy191filesPASS.15new meaningful cases cover replacement of true with false, preservation of unrelated conditions, atomic rejection and ambiguous corrections.

Public Parakeet discovery again reached the1536MiB cgroup limit. It remains unapproved for production; neither its speed nor shared-cache runs close the memory gate. Small and production model assets are unchanged.

A separate Tatoeba English metadata-only license review examined547matching sentences across6pages. Only2had redistributable audio, both third-person narratives. The other recordings are not used; text and audio licenses remain distinct. This does not satisfy English positive housing acceptance, and the user is not asked to record English or Spanish.

Canonical [evidence and hashes](ai-speech-fsi-20261118-evidence/SHA256.json) contain public metadata, baseline outputs, scripts and explicit parser replay. No private recording or private transcript is included. No provider calls, live business queries, new guests, quota resets, migrations or data-cohort expansion occurred. Full S4/S7 acceptance and registered native foreground remain separate mandatory work.
