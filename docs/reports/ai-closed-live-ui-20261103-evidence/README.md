# Authorized synthetic LIVE smoke evidence

Result **FAIL**, not model acceptance. The pre-IO run used zero new provider
attempts; the subsequent run used one attempt, stopped on terminal failure and
left the remaining two unused. Provider usage/billing for that attempt is unknown.

Artifacts contain fixed metadata, quota aggregates and approved synthetic test
results only. Neither the real key file nor SQLite journal is published.
`authorized-execution.ps1.txt` records the actual local orchestration as evidence;
it is not authorization to run it again. The one-shot driver rejects journal52
as a fresh baseline, and the LIVE network/mounts are now removed.

The original local run directories and source archives remain retained under
`output/ai-closed-live-ui-20261103-owner-approved-v1/` and `...-v2/`.
Full build/dependency logs are retained locally; selected result metadata is
published here. The TLS diagnostic made zero HTTP requests and had no key mount.

`SHA256.json` covers exact artifact bytes. This evidence directory is marked
`-text` to preserve Windows line endings in Git. Verify binary bytes directly
without shell newline conversion. Earlier preparation/main evidence is untouched.
