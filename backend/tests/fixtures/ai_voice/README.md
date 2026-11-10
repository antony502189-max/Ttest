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
