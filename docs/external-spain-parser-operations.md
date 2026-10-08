# Spain rental parser: operator runbook

This is code support, not activation. No production imports, gate changes or
enabled production scopes were performed by this change. No migration is added.
Canonical modes remain `long` and `holiday`; allowed units are rooms, studios
and whole apartments with exactly one bedroom.

## Admission and source contracts

`rental_classification.property_type` uses provider fields first, provider room
routes second, and listing-specific text last. Whole apartments require a safe
bedroom count; bare lofts, houses, sales, wanted ads, non-residential and bed-only
offers are rejected. A studio has zero separate bedrooms. Existing canonical
`bedroom_count` constraints allow NULL or 1..99: studio zero is kept in the
normalized source snapshot and `room_type=Estudio`, with canonical count NULL.

`rental_price` checks structured categories, provider routes, positive textual
signals and cadence. Monthly residential/academic/temporary offers are `long`;
nightly tourist offers are `holiday`. Bare `temporada` and weekly offers without
holiday evidence fail closed. Structured mode/cadence conflicts are rejected.
Weekly holiday prices retain `weekly_price` and use rounded-up weekly/7 as the
canonical nightly equivalent; `source_price_text` keeps the advertised cadence.

Province scopes require the listing's own recognized province and Spain
country evidence, never the current crawl scope as a guessed address. Missing
country is accepted only when a recognized Spanish province is supplied.
Municipality and source coordinates are preserved; no province-centre points
are generated. The legacy Santa Cruz geography contract stays available.

`run_source` still owns source state, upsert, snapshots, bounded image ingestion,
fingerprints and lifecycle. Its completed health contract now admits all allowed
units rather than rooms only; it still requires discovery, fetched details,
accepted rentals and a publishable result. Partial discovery is never complete
inventory and never triggers missing-listing reconciliation. A dry audit's
`healthy` means a valid sampled detail; it does **not** prove worker success.
A detected challenge overrides sampled success and remains `blocked`.

## Read-only commands (from backend/)

```bash
python -m app.commands.provision_external_spain \
  --output ../output/spain-scopes.json
python -m app.commands.bootstrap_external_spain \
  --manifest ../output/spain-scopes.json \
  --max-pages 2 --max-details 3 --source-timeout 45
```

Provisioning defaults to live validation without DB access. It extracts actual
links from Pisos `/alquiler_viviendas/` and PisoCompartido `/zonas/`. It does not
synthesize province URLs. Each accepted route must use HTTPS, an exact provider
host, no credentials/fragment/unexpected port, and show listing links or explicit
empty-catalogue evidence. Cross-province/homepage redirects are rejected; a
recognized canonical alias redirect within the same province is permitted.
Only successfully validated routes are saved. Nonzero exit reports failures;
the successful subset can still be reviewed. A supplied manifest receives the
same validation. It can contain at most 468 unique source/province scopes, each
with 1..6 routes, using only known adapters and the 52 recognized territories.
Multi-route scopes validate each URL independently. Failed URLs remain in both
`evidence` (`validated: false`) and `failures`, with source/scope/URL/error;
the command exits nonzero but saves the verified subset. Either valid Málaga
route survives the other failing. If both fail, no scope is saved.

The bootstrap dry run is a bounded public discovery/detail audit without DB
reads or writes. Details default to at most five per scope. Its source timeout
applies to each sampled scope. Use a small reviewed manifest for first audits.
Raw public pages are not production import records and sample counts must not
be extrapolated into canonical inventory.

### Dedicated Málaga holiday pilot (future authorization only)

Review this SMALL manifest as `../output/malaga-holiday-pilot.json`:

```json
[{"source_name":"Pisos","scope_key":"province:Málaga","discovery_urls":[
  "https://www.pisos.com/alquiler/pisos-malaga/",
  "https://www.pisos.com/alquiler-vacacional/pisos-malaga/"
]}]
```

```bash
python -m app.commands.provision_external_spain \
  --manifest ../output/malaga-holiday-pilot.json --output ../output/malaga-holiday-validated.json
python -m app.commands.bootstrap_external_spain \
  --manifest ../output/malaga-holiday-validated.json \
  --max-pages 2 --max-details 3 --source-timeout 90
```

Proceed only if validation retains BOTH routes without failures. This pilot is
read-only, without DB access or production activation. FIFO traversal visits
the two initial roots before any appended long pagination; one page is
insufficient. Require `discovery_roots` to show `visited_pages >= 1` for BOTH
URLs, otherwise holiday traversal failed. Two pages prove root visitation,
not catalogue completeness or 500 accepted holiday offers. Each root checks its
own expected count/unique URLs; the importer receives their unique union.
Any incomplete/failed/repeated/blocked root keeps the scope partial and forbids
missing-listing reconciliation.

```bash
# Creates disabled rows. Rerun preserves an existing row's enabled flag.
python -m app.commands.provision_external_spain \
  --manifest ../output/spain-scopes.json \
  --output ../output/spain-scopes-revalidated.json --apply

# Explicit activation: use a reviewed SMALL subset, not an unreviewed full file.
python -m app.commands.provision_external_spain \
  --manifest ../output/pilot-scopes.json \
  --output ../output/pilot-scopes-revalidated.json --apply --enable
```

Upsert uses the existing `uq_external_import_scope` constraint on
`(source_name, scope_key)`. Plain `--apply` never implicitly activates or
deactivates an existing row. `--enable` requires `--apply`.

## Bootstrap apply / resume

```bash
EXTERNAL_IMPORT_ENABLED=1 EXTERNAL_IMPORT_NATIONWIDE_ENABLED=1 \
python -m app.commands.bootstrap_external_spain --apply \
  --target-total 2500 --target-holiday-min 500 --max-total 3000 --max-pages 30 --max-details 500 --max-scopes 156 \
  --checkpoint ../output/spain-bootstrap-checkpoint.json
```

Apply reads enabled scopes only; every source must also be enabled in the
existing source configuration. There must be at least one enabled scope.
The command acquires the worker's `ttest:external-listings-import` Redis lease,
renews it every 30 seconds and cancels on lease loss. It fails closed if Redis
cannot be used. Only when Redis is intentionally absent may `--worker-paused`
confirm that **all** import/removal workers are stopped. It is not a workaround
for a failed Redis connection. Keep the normal worker health threshold unchanged.

Three breadth-first rounds visit the enabled scopes in province/source order:
1 page/25 details, 5 pages/100 details, then configured page/detail limits.
Every round is capped by the configured maximums; identical effective rounds
are removed before execution. For 1 page/2 details the sequence is [(1,2)],
for 3/50 it is [(1,25),(3,50)], and for 30/500 it is [(1,25),(5,100),(30,500)].
Each scope reuses `run_source`;
detail requests retain the configured semaphore (default three), batches of
100 and discovery lookups of 250. No second ingestion pipeline exists. HTTP
requests retain the baseline bounded three attempts; page budgets, repeated URL-set
detection and provider challenges prevent infinite traversal. Apply does not
use the dry-run `--source-timeout`: its bounds are page/detail/request budgets.

The objective counts all active canonical external listings, including legacy
inventory, and requires BOTH total >= `--target-total` (default 2500) AND
holiday >= `--target-holiday-min` (default 500). `--target` remains an alias for
the total target. Explicit `--target-holiday-min 0` opts out of the holiday
minimum for an intentionally total-only operation, never by default.
The check runs between scopes and can overshoot by one scope. It does not
guarantee geographic distribution or permit relabelling monthly offers.
2600 long / 0 holiday cannot satisfy the default objective: reviewed scopes
continue until objective reached or another bounded stop. The final `objective`
reports total/long/holiday, both configured targets, individual satisfaction
and combined `satisfied`. Stop reasons distinguish `inventory_target_reached`,
`max_total_reached_holiday_unmet`, `scope_budget_reached`, and `reviewed_scope_rounds_exhausted`. An apply invocation
with an unmet objective exits **2**, even after exhausting all reviewed rounds;
dry runs and satisfied objectives exit 0. Inspect provider results separately.
`--max-total` defaults to 3000; require 1 <= target-total <= max-total <= 10000.
Success wins first; otherwise total >= max-total stops with the explicit unmet
holiday reason and exit 2. Each import's detail budget is capped by remaining
capacity (`max-total - current total`), preventing this bootstrap from crossing
the ceiling in one scope. The Redis lease excludes the normal importer worker;
unrelated writers/pre-existing inventory are outside this command's ceiling.
The objective also reports `max_total` and `max_total_reached`.

Progress prints one JSON line per scope, then a totals report. `result` can be
success/partial/blocked/failed; a completed operator process is not proof of
healthy sources. Existing provider backoff remains active. Counters include
discovered/fetched/accepted/rejected/created/updated/unchanged/failed and mode/
unit counts. Legacy `accepted_rooms` remains rooms only. Unsupported units use
`rejected_unsupported_property_type`; legacy `filtered_not_room` /
`rejected_not_room` remain incremented for compatibility. Duration and failed
pages remain on `ExternalImportRun`. A detail budget marks discovery partial
with `bootstrap_detail_budget`; it cannot archive unseen source records.

Atomic checkpoint writes record completed scope/round attempts, run ID and a
hash of scope IDs/routes plus page/detail, effective round budgets and max-total. Old
checkpoints without the max-total/unique-round contract require a new checkpoint or an
explicit `--restart`; changed configurations fail closed. Resume uses the same command
and persistent checkpoint. A crash can replay the current scope, safely through
existing idempotent upsert. Configuration changes require a fresh checkpoint
or deliberate `--restart`. Completed failed/blocked attempts remain recorded;
review their errors/backoff and deliberately restart a reviewed phase to retry.
`--max-scopes` bounds attempts per invocation, not number of provinces.

Canonical totals group mode/unit and primary source. Province coverage counts
distinct canonical IDs with active source rows per scope. A canonical backed by
multiple provinces/providers can appear in several coverage rows: these rows
are **not additive**. No native-user listings enter the target.

## Public evidence from 2026-10-07

Read-only full route validation accepted **88** scopes: Pisos 52,
PisoCompartido 36. Union coverage is all 50 provinces plus Ceuta and Melilla.
PisoCompartido published 42 provincial routes, with ten absent in its index:
Asturias, Burgos, Cádiz, Huelva, Jaén, Palencia, Segovia, Soria, Zamora, Ávila.
Six published routes failed validation: Bizkaia, Castellón, Gipuzkoa,
Illes Balears and Álava redirected outside recognized province routes; Ceuta
supplied neither detail links nor explicit empty-catalogue evidence. A bounded
recheck of the five redirects still failed; they were not provisioned.

The province sample used one page and up to three details for Pisos in Madrid,
Barcelona, Málaga, Illes Balears, both Canary provinces, Ceuta, Melilla, plus
PisoCompartido in six of those provinces. It accepted 25 long offers out of 41
fetched details: 17 rooms, seven one-bedroom apartments and one studio.
Later parser fixes for bilingual province aliases and temporary-rental
breadcrumbs were verified in tests, not silently added to these audit totals.
Zero holiday offers were accepted in that residential sample.

A separate actual Pisos studio detail in Arenas, Málaga normalized as holiday,
zero bedrooms and **40 EUR/night** using its primary displayed price,
structured bedroom span and provider breadcrumbs. Its published catalogue
was a regional vacation-studio page, which also contained offers outside the
named region. The published province holiday breadcrumb returned 404. Neither
route was fabricated into a province manifest. The 500–1,000 holiday target is
**unproven**; monthly Flatio offers were not relabelled as holiday.

| Source | Final bounded default audit | Discovered | Accepted long / holiday |
|---|---|---:|---:|
| Idealista | blocked on detail access | 60 | 0 / 0 |
| Fotocasa | valid sample, partial discovery | 60 | 3 / 0 |
| Milanuncios | access challenge | 0 | 0 / 0 |
| PisoCompartido | valid sample, partial discovery | 29 | 3 / 0 |
| Pisos | valid sample, partial discovery | 30 | 3 / 0 |
| ThinkSpain | empty anonymous HTTP 202, blocked | 0 | 0 / 0 |
| AlquilerDocenteCanarias | valid limited-geography sample | 17 | 1 / 0 |
| Flatio | rejected sample: required structured contract | 76 | 0 / 0 |
| Habitaclia (initial final audit) | HTTP 200, obsolete detail-route recognition | 0 | 0 / 0 |

Defaults audited at two pages/up to three details, source budget 45s/detail
12s; Habitaclia separately at one page with the same detail/budget caps. Most
discovered detail URLs do not encode rental mode; these counts are `unknown`,
not invented long/holiday discovery totals. Mode is resolved from fetched
details. None of these counts prove 2,000–3,000 unique active canonicals.

The first live Habitaclia CI exposed a public route change: current cards use
`/alquiler/.../<uuid>/d` rather than only `/i<numeric>.htm`. The adapter now
recognizes both, decodes public Next-flight `JSON.parse` payloads without
executing JavaScript, matches the primary listing's UUID/legacy ID, and reads
its own unit/rooms/municipality/province and gallery. It preserves the provider's
legacyNumericId for historical identity and still suppresses map coordinates
and contacts. The audit probe recognizes the same actual public routes.
`accepted_rentals` covers allowed units; `accepted_rooms` remains genuine rooms.
Repeated URL sets terminate as partial. Sanitized UUID/flight fixture tests
cover actual fields, wrong-ID isolation and multi-bedroom rejection.
The subsequent bounded public audit (one page/three details, 45s/12s caps)
discovered eight target routes and accepted three long one-bedroom rentals with
images. Discovery remained partial under the one-page cap; this does not
replace the CI requirement for complete discovery and valid image-bearing units.

## Future production steps — not executed

After review, merge and all required CI succeeds, use the existing release
pipeline, on the authorized host, with the current full origin/main SHA:

```bash
bash /srv/112233.es/repo/deploy/deploy-release.sh <full-current-main-sha>
release=$(readlink -f /srv/112233.es/current)
export DEPLOY_SHA=$(basename "$release")
compose=(docker compose --env-file /srv/112233.es/shared/production.env \
  -f "$release/docker-compose.production.yml")
"${compose[@]}" run --rm --no-deps external-listings-worker \
  python -m app.commands.provision_external_spain --output /tmp/spain-scopes.json
```

For durable manifests/checkpoints, mount a dedicated operator directory writable
by the image's `app` user; determine that UID with `id -u` inside the image.
Do not mount the entire production shared directory into the crawler.

```bash
"${compose[@]}" run --rm --no-deps -v /srv/112233.es/shared/parser:/operator \
  external-listings-worker python -m app.commands.provision_external_spain \
  --output /operator/spain-scopes.json
"${compose[@]}" run --rm --no-deps -v /srv/112233.es/shared/parser:/operator \
  external-listings-worker python -m app.commands.bootstrap_external_spain \
  --manifest /operator/pilot-scopes.json --max-pages 1 --max-details 3
"${compose[@]}" run --rm --no-deps -v /srv/112233.es/shared/parser:/operator \
  external-listings-worker python -m app.commands.provision_external_spain \
  --manifest /operator/spain-scopes.json --output /operator/revalidated.json --apply
```

Review disabled rows and record each row's prior enabled state before activation.
Choose a pilot containing mainland/island territories and a **validated actual
holiday route** if one becomes available. Enable only that reviewed manifest
using `--apply --enable`. Set no retired source active merely to fill a quota.

Production Compose forwards `EXTERNAL_IMPORT_NATIONWIDE_ENABLED`, defaulting to
`0`. Leave it disabled while auditing and doing the first controlled bootstrap.
For a one-off explicit bootstrap, pass the flag to that container only:
Perform the dedicated read-only Málaga holiday pilot above before this bounded
inventory import. An apply breadth-first first round uses one page and cannot
by itself validate both holiday/long roots.

```bash
"${compose[@]}" run --rm --no-deps -e EXTERNAL_IMPORT_NATIONWIDE_ENABLED=1 \
  -v /srv/112233.es/shared/parser:/operator external-listings-worker \
  python -m app.commands.bootstrap_external_spain --apply --target-total 2500 --target-holiday-min 500 --max-total 3000 \
  --max-pages 1 --max-details 25 --max-scopes 4 \
  --checkpoint /operator/pilot-checkpoint.json
```

After validating the pilot, expand disabled scopes in controlled groups, enable
reviewed groups, then invoke the same command with 30 pages/500 details/156 scope
attempts and a **new** persistent checkpoint. Check totals, actual geography,
duplicate suppression, source results and price cadence after every phase.

After importing and verifying a small curated enabled scope set, an authorized
operator can set the flag to `1` in production.env and recreate the worker with
the base Compose. Check that its effective environment receives the flag.
Only enabled, due rows are refreshed, at most eight per full cycle, after the
unchanged useful-source health gate. Scoped refresh defaults to two discovery
pages and 50 details per scope (`EXTERNAL_IMPORT_SCOPE_MAX_PAGES`, 1..30, and
`EXTERNAL_IMPORT_SCOPE_MAX_DETAILS`, 1..500). It retains each adapter's smaller
page cap. These limits do not affect the existing Santa Cruz full imports.
Budget-limited refresh remains `partial`, schedules a bounded retry and never
archives unseen listings. It does not prove complete coverage of a province.
The independent direct-state removal sweep checks already imported sources.

The legacy Pisos Santa Cruz room route timed out in production on 2026-10-08.
The adapter now uses the provider-published
`/alquiler/habitaciones-santa_cruz_de_tenerife/` route linked from the live
Tenerife catalogue, alongside the existing Tenerife root. Both roots and their
pagination must still satisfy completeness independently; failures remain
partial and preserve existing inventory.

```sql
SELECT source_name, scope_key, enabled, last_result, next_run_at
FROM external_import_scopes ORDER BY scope_key, source_name;
SELECT rental_mode, room_type, count(*) FROM listings
WHERE is_external AND status='published' AND deleted_at IS NULL
GROUP BY rental_mode, room_type;
SELECT s.scope_key, count(DISTINCT l.id)
FROM external_listing_sources s JOIN listings l ON l.id=s.canonical_listing_id
WHERE l.is_external AND l.status='published' AND l.deleted_at IS NULL
  AND s.current_status='active' GROUP BY s.scope_key;
SELECT source_name, scope_key, result, counters, last_error, next_check_at
FROM external_import_runs ORDER BY started_at DESC LIMIT 30;
```

Use the existing authenticated DB operator session; do not print the DSN.
Inspect `docker compose ... logs --tail 100 external-listings-worker` and run
`python -m app.workers.external_listings --healthcheck` inside the running worker.
Do not certify the target until distinct active canonical totals, both modes,
geographic coverage and full completed source contracts are verified.

## Rollback

Stop the operator bootstrap cleanly and preserve its checkpoint. Remove the
nationwide flag (set it to `0`) and recreate the worker from the
base Compose. Restore **only recorded changed scope IDs** to their prior enabled
states using a reviewed DB transaction; never blanket-disable historical scopes.
Use the existing `deploy/rollback-release.sh [recorded-previous-release-sha]`
to restore application code/images. It preserves database, Redis and media
volumes. No new migration requires reversal. Do not delete imported listings or
source records; any historical reclassification requires a separate reviewed
operation. The bootstrap target is operational evidence, not permission to
delete or misclassify data.
