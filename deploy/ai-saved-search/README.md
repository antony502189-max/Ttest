# Registered AI saved searches: S4.2–S4.4

The canonical status/next action is [the completion plan](../../docs/ai-search-completion-plan.md).
This deployment contract does not enable the feature or extend provider approval.

## Behavior and operating bounds

An explicit signed-in Save copies the immutable, owned committed result through a
five-minute HMAC handoff. Guest identity, quota, history and result ownership stay
with the original guest. Tokens remain in HTTP/UI memory; registered rows retain
only typed criteria. Renewing a token keeps the result UUID as the stable create
receipt. Repeated requests return the same saved search; deleting it leaves a
receipt that cannot recreate it. Manual and AI searches share the existing limit.

The SQL-only worker scans current verified matches: 20 rows per claimed search,
four claims per maintenance tick, five-minute per-search cadence, 30-second leases
and a 15-second per-claim deadline. A durable fence, token and saved revision reject
obsolete workers. Notification insertion and live listing/source/proof/owner checks
occur in the same SQL statement, under the same collection lock as disable/delete.
Delivery, seen IDs and scan progress commit together. Current matches at save time
form a baseline and produce no immediate alert.

The separate allowance is 20 in-app alerts per registered account per Madrid day,
shared across its searches. No model call, foreground quota reservation, email,
SMTP, browser push, raw query or manual-filter reinterpretation is involved.
Seen IDs persist while the saved search exists, and cascade with search/account or
physical listing deletion. Under the selected original thirteen-source cohort,
this is at most thirteen listing IDs per saved search. Private criteria persist
until explicit search/account deletion; existing deletion-journal/backup retention
rules continue to apply. This does not claim general-catalog capacity acceptance.

## Primary release and initialization order

1. Release the reviewed application and expand-only schema0080 with the ordinary
   backup/runner. All AI saved variables default empty; creation/delivery stay off.
2. Inspect existing primary saved rows, proof rows and journal binding first.
   Initialize an independent primary journal only when the primary has never had
   one; never replace, clear or reseed an existing journal/binding. Preserve a
   separate authenticated journal checkpoint for restore. Reuse existing lifecycle
   `configured_journal`, `bind_journal` and `replay_erasure`, not a new deletion path.
3. Supply independently random 32-byte base64 handoff and erasure key files in the
   primary `ai-saved-secrets` volume. Keep the ciphertext journal in the separate
   `ai-saved-state` volume, outside PostgreSQL dumps. Missing/wrong keys or journal
   binding block startup. File-based erasure keys are mutually exclusive with the
   previous environment-key form; the isolated pilot's keys/journal stay unchanged.
4. Supply `cohort.json` as `{"schema":"ai-saved-cohort.v1","source_ids":[...]}`,
   containing exactly the source UUIDs of the existing approved thirteen records.
   The maintenance path reads original imported payloads without rewriting listings,
   source timestamps or snapshots. Existing CAS/fact leases/publication/proofs are
   reused. Preparing a structural proof does not renew upstream source freshness;
   the matcher must independently verify current eligibility.
5. Set primary paths below, run erasure replay, prime the selected cohort and check
   current verified SQL coverage. Enable the primary mode only after successful
   initialization. Mount the **same handoff key only** into the isolated result
   issuer; it must differ from its cursor/guest keys. It gains no login endpoints,
   bearer access, primary journal or registration authority.
6. Restart verified images, check both capabilities and no-bearer isolated boundary,
   then install the three systemd units from this directory. Confirm successful
   real ticks, restart/retry and the OnFailure marker. The timer invokes the
   current primary container, so ordinary release serialization retains its image
   authority. A stopped/unready backend fails the tick rather than inventing data.
7. Complete authenticated save/retry/list/pause/delete/reload and new-match/no-
   duplicate/post-disable/account-delete checks before recording S4.2–4.4 done.

Primary settings (operator files only):

```dotenv
AI_SAVED_SEARCH_MODE=signed-housing-inapp.v1
AI_SAVED_HANDOFF_KEY_FILE=/ai-saved-secrets/handoff.key
AI_SAVED_COHORT_FILE=/ai-saved-secrets/cohort.json
AI_ERASURE_JOURNAL_PATH=/ai-saved-state/erasure.sqlite
AI_ERASURE_JOURNAL_KEY_FILE=/ai-saved-secrets/erasure.key
```

Turning off `AI_SAVED_SEARCH_MODE` disables new saves/toggles and background ticks,
but keep the journal settings, key files, state and binding: startup must still
replay deletion intents. Rollback refuses binaries lacking this contract before
stopping the healthy current application. Do not activate a primary journal until
the first compatible release has succeeded; future automatic rollback then has a
compatible previous release. Never roll the schema backward or delete volumes.

Text/voice provider dispatch still follows its separate, cumulative approval and
expiry. Saved matching does not extend that approval. A synthetic test or deployed
button does not close provider/data/ASR/performance/full-release acceptance gates.

## Existing-authority completeness and retention

The configured thirteen source UUIDs anchor the original thirteen canonical
listings. A canonical listing may already have multiple active imported
PisoCompartido records. Maintenance resolves all such current records for only
these same objects (100-source hard bound), so the existing publication barrier
can verify every authority. Unsupported publishers remain fail-closed. This does
not add canonical listings, crawl sources or rewrite original payloads/timestamps.
The live cohort currently needs fourteen imported authorities for thirteen objects.

Install the primary retention service/timer alongside the three delivery units.
It runs the existing bounded recovery/erasure/fact-retention command once per
hour using the running primary container's database and independent journal.
Database credentials stay inside that container. Historical facts/events use the
existing seven-day policy and bounded batches; active current facts remain.
Both jobs report failures through the same fixed OnFailure marker. Enabling these
units requires verified current images and a successful first real maintenance
and retention tick; deployment and journal initialization remain separate steps.
