# Synthetic speech, no microphone or personal voice data

Generated locally with Windows SAPI Microsoft Zira/Irina, then rewritten as
canonical16kHz/mono/16-bit PCM WAV. English: “Find rooms under six hundred euros
per month.” Russian: “До шестисот евро в месяц.” These are synthetic engineering
fixtures, not evidence of recognition quality for human speakers or accents.

The700EUR regression uses “До семисот евро в месяц.” in two local Russian voices:
Microsoft Irina Desktop and Microsoft Pavel. Original beam1 misrecognized the
Irina sample as unrelated words; beam5 must retain the exact700EUR amount for
both voices, alongside the original600EUR English/Russian fixtures. No example
budget or expected digits are supplied as an ASR prompt.

The real local-ASR smoke uses pinned model/dependencies and a network-none,
read-only, CPU/memory bounded container. No external ASR or model API is called.

The Base-model regression additionally includes synthetic complete requests:
`en-conditions.wav`: “A room under seven hundred euros per month, furnished, bills included.”
`ru-composite.wav`: “Комната в Ла Лагуна, до семисот евро в месяц, с мебелью.”
The Russian sentence does not request bills included. `silence.wav` must reject
without producing any transcript; a timeout does not count as a passing rejection.
The supported speech languages are Russian, Spanish and English. The detector
selects among these languages using its own probabilities. Pinned Base can emit
“семи сот” for “семисот”; the exact reviewed form retains the same numeric value.
The seven-sample suite has a 70s bound; each individual transcription retains 8s,
2 CPUs, 1536MiB, beam5 and 96 tokens. No prices or housing facts are prompted.

After a real regression on Russian furniture speech, the fixed ASR glossary also
contains housing nouns and inflections in the three supported languages. It
contains no amounts or polarity/yes-no statements. The four price-only cases
must still produce exactly their spoken conditions, and silence must reject.
Garbled furniture words and incomplete city names are never text-normalized
into criteria. This contextual-vocabulary change is tracked separately from the
previous place-only model acceptance.
