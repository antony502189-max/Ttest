# Geography, address and search audit — 2026-10-17

Target: `codex/province-search-top`, HEAD `15b67386`, baseline `1b2805e4`.
No application code changed; no production database, secrets or real payments used.

## Scope and factual model

- `User` has no address/postcode/province field (`backend/app/models/__init__.py:37–61`). The implementation resolves province from **the property's `Listing.postcode`**, not the account's registered address. This is the repository's actual model; the customer's wording remains a decision to confirm.
- `Listing.city/area/street/postcode/location/exact_location` are independently supplied fields (`models/__init__.py:122–132,183–187`). There is no province FK or persisted verified province. Search, public DTO, counts and TOP compute the same two-digit postcode prefix (`spain_provinces.py:23–33`).
- Catalogue has 52 INE codes (50 provinces + Ceuta/Melilla). Exact names have distinct codes; aliased provider names are normalized by `canonical_province`.
- INE official [province codes](https://www.ine.es/daco/daco42/codmun/cod_provincia.htm) were opened during this audit and match 01–52.
- Official INE [España Municipal 2025 infographic](https://www.ine.es/infografias/infografia_censo.pdf), read during audit, explicitly gives **8,132 municipalities**, not provinces. The [municipality catalogue as of 01/01/2026](https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177031&idp=1254734710990&menu=ultiDatos), published 04/02/2026, distinguishes the five-digit INE municipality code from its first two province digits. An INE municipality code is not a postcode. Thus the 8132 requirement cannot be marked satisfied: either approve 52 geographic TOP pools or specify 8132 municipality pools (roughly 156 versus 24,396 possible simultaneous TOP placements).
- No IP-geolocation source introduced for province assignment. The Google selection in native widget resolves address metadata client-side.

## Executed probes

Command (exit 0):

```powershell
& '.\output\release-venv\Scripts\python.exe' '.\artifacts\audit-2026-10-17\geography\reproduce_geography.py'
```

Artifacts: `geography/reproduce_geography.py`, `geography/reproduction-output.json`.
These execute real Pydantic schemas, `apply_write`, `apply_primary_source_snapshot`, `_saved_search_payload`, and SQLAlchemy query compilation with in-memory session mocks. They do **not** claim database/API/browser execution.

### Additional real PostgreSQL + HTTP verification

Following the initial probes, an isolated PostGIS database **`audit_geo_extra`** was created in **`ttest-audit-province-20261017`**, loopback port55439, with audit-only credentials. This is separate from both production and the other agents' databases. `alembic upgrade head` completed with exit0. The script asserts `current_database() == 'audit_geo_extra'` before test writes, uses synthetic fixture accounts and persisted `AuthSession` rows with test-only JWTs, and does not override application authentication dependencies. All HTTP requests below traverse the real FastAPI application through `httpx.ASGITransport`; they are not a browser or externally deployed service test. External payment/email/image downloads are disabled; no real payments attempted.

```powershell
docker exec ttest-audit-province-20261017 createdb -U audit audit_geo_extra
# backend cwd, explicit audit DATABASE_URL and test settings:
& '..\output\release-venv\Scripts\python.exe' -m alembic upgrade head
# root cwd; script itself sets explicit isolated test settings:
& '.\output\release-venv\Scripts\python.exe' '.\artifacts\audit-2026-10-17\geography\reproduce_geography_database.py'
```

All commands exit0; async command executed outside the sandbox socketpair limitation using approved `require_escalated`. Output artifacts: `geography/migration.log`, `geography/database-run.log`, `geography/database-output.json`; reproduction script: `geography/reproduce_geography_database.py`.

| Finding | Executed real HTTP/SQL result |
|---|---|
| GEO-01 | Real `upsert(...scope_key='province:Madrid')` returns `imported`; source JSON province Madrid, persisted postcode empty, SQL derived province NULL. `POST /listings/search/cards {}` HTTP200 total1 and contains imported row; same with province28 HTTP200 total0. Province28 count endpoint returns0. |
| GEO-02 | Authenticated `POST /listings` with valid owned media fixtures, Madrid address/coordinates and postcode08001 returns HTTP201, status published, province08. Authenticated `GET /payments/listings/{id}/top/availability?days=10` returns Barcelona, available=true, slots3. Postcode-only PATCH29001 returns HTTP200, province29, city/coordinates still Madrid. |
| GEO-03 | `POST /saved-searches` queryMadrid HTTP201; real listing publication in Getafe postcode28901 and in Madrid postcode28013 both HTTP201. Province28 card search contains both. `GET /notifications` reports saved_search_match for Madrid control but **none for Getafe**. |

These reproduce the three defects through database persistence and HTTP routes, upgrading them beyond the initial mock-only evidence. Database and fixture content preserved for inspection until the parent cleans up the audit container.

Observed:

| Probe | Actual result |
|---|---|
| Madrid city/street/coordinates + postcode `08001` | Accepted by `ListingWrite` and `apply_write`; stored province becomes Barcelona (`08`). |
| Madrid + postcode empty/`garbage` | Accepted; province null. |
| `ListingPatch(postcode='08001')` without address/coordinates | Accepted. |
| Import snapshot with `province='Madrid', country='ES'`, Madrid coordinates | `Listing.postcode` stays empty; province null. |
| Saved search alert `query='Madrid'` | `provinceCode=None`; SQL uses city/area `ILIKE '%Madrid%'`. |
| Interactive `provinceCode='28'` | SQL uses postcode expression, not city. |

Initial environment probes: PATH `python` was a PyManager stub (failed runtime index resolution); bundled interpreter lacked pytest; project `output/release-venv/Scripts/python.exe` works. `asyncio.run()` in sandbox blocked during Windows loop socketpair initialization (faulthandler showed `socket.accept → _fallback_socketpair → ProactorEventLoop._make_self_pipe`), before application execution. The final isolated probe drives only immediately-completing mocked coroutines without constructing a loop. The one lingering process was interrupted. No application failure inferred from these environment errors.

## Confirmed findings (local IDs for parent to renumber)

### GEO-01 — P1 — Province search excludes every normally imported listing

**Locations:** `backend/app/spain_provinces.py:29–33`, `backend/app/repositories/listings.py:343–345`, `backend/app/api/v1/listings.py:74–79`; producer `backend/app/services/external_import.py:606–665,868–921`; `backend/app/external_sources.py:767,1529`.

**Root cause:** Normalized provider item retains canonical `province` in source JSON, but the `Listing` constructor and `apply_primary_source_snapshot` never set a province or postcode. New imported records default to `postcode=''`. Provincial search, province counts, detail/card `provinceCode` and TOP solely use postcode. This is not merely an historical migration omission: newly imported listings with valid structured province remain unsearchable too.

**Reproduction:** Import a standard eligible Madrid item through `province:Madrid` (or existing Santa Cruz importer); it gets published with Madrid metadata and blank postcode. Search `/listings/search/cards` or `/listings/search` with `{provinceCode:'28'}`; the row cannot match `CASE ... postcode ... END = '28'`. Without the province filter it can appear. Executed real importer+PostGIS+HTTP reproduction returns total1 without province and total0 with province28; province28 count0.

**Expected:** Valid structured imported province should participate in the same provincial catalogue. **Actual:** Imported catalogue disappears on provincial selection, and counts show zero even when imported listings exist. The new default location picker drives users into this failing path.

**Impact:** Core search regression affecting the entire ordinary imported inventory and all 52 provinces. Source code already supported multi-province imports before HEAD.

**Smallest safe fix:** Introduce a canonical province field/equivalent trusted source mapping shared by local and imported listings; derive owner listings from verified address and imports from validated structured province; backfill current source JSON/canonical records without inventing a full private postcode. Keep unknown records explicitly reviewable. Do not fake provider postcodes just to satisfy a prefix.

**Regression:** Real importer inserts Madrid row without postal code but valid province; search/cards/map/counts for 28 include it, 08 exclude it, repeated snapshots/failover preserve province; invalid/contradictory provider evidence stays excluded.

**Confidence:** High, executed real importer, PostGIS derived expression, HTTP cards/count routes, plus snapshot/compiled-filter probes. Introduced integration defect at HEAD.

### GEO-02 — P1 — Client can choose TOP province through unverified postcode

**Locations:** `backend/app/schemas/listings.py:65–68,196–199,111–114`, `backend/app/services/listings.py:277–283,309–316,574–578,681–698`, `backend/app/services/province_top.py:38–40,79–90`.

**Root cause:** Create/patch accepts arbitrary or empty `postcode`, city/street and coordinates independently. There is no trusted address identifier/signature, server geocoding or province/coordinate consistency validation. `apply_write` blindly persists postcode; TOP's address guard compares only old/new prefix. `extra='forbid'` blocks a literal forged `provinceCode`, but not the postcode which directly determines it.

**Reproduction:** As verified host with a valid ordinary listing and photos, submit Madrid city/street and coordinates (40.4168,-3.7038), `postcode='08001'`; or PATCH a nonpromoted Madrid row with only `{postcode:'08001'}`. The schema and write layer accept it and all province/TOP queries assign `08`. Purchase TOP in Barcelona even though map/address remain Madrid. On an active TOP row, change coordinates/street to a different physical province while retaining postcode: postcode guard either is not called or returns for unchanged prefix. No actual Stripe charge attempted.

**Expected:** Province must come from a consistent validated appropriate address and cannot be manually steered by changing a request field. **Actual:** A host can select any 01–52 TOP pool; garbage/empty postcodes are accepted for publication and then disappear from provincial search (TOP rejects these only later).

**Impact:** Wrong-province search and paid placement, bypass of the customer's automatic-address rule; effective circumvention of physical geographic capacity. Does **not** prove more than three rows within the same stored postcode bucket.

**Smallest safe fix:** Validate creation and effective patched address server-side; resolve/prove province against country/address/coordinates using trusted source evidence, preserve compatible legacy edit policy and prevent code-changing address edits throughout active/pending TOP. Merely adding a regex does not stop a well-formed wrong-province postcode.

**Regression:** Forged valid-other-province postcode plus Madrid coordinates rejected; missing postcode gets controlled error; unchanged prefix + out-of-province coordinates during active TOP rejected; legitimate consistent move without TOP succeeds and updates every search projection.

**Confidence:** High, schema/apply_write and authenticated HTTP create+patch+TOP availability executed against isolated PostGIS. Existing permissive address input newly becomes monetization authority at HEAD; do not label it a newly introduced authentication bypass. Checkout/payment itself intentionally not invoked.

### GEO-03 — P2 — Saved province alerts still match city strings

**Locations:** `backend/app/services/notifications.py:157–159,209–212,267–272`, `backend/app/repositories/listings.py:343–351`, `src/contexts/app-context.tsx:590–608`, `backend/app/schemas/searches.py:84–91`.

**Root cause:** Interactive frontend resolves province name or `provincia` into `provinceCode`; persisted saved searches store only query/filter/polygon. `_saved_search_payload` never resolves or supplies province. Alert matching therefore falls back to city/area substring filtering.

**Reproduction:** Select Madrid province (query='Madrid', provincia='28'), save and enable alert. Publish eligible row in Getafe or Alcalá de Henares with Madrid postcode. Interactive provincial search includes it; alert query uses `%Madrid%` against city/area and excludes it. Similarly Santa Cruz de Tenerife province misses listings in Adeje. Direct URL `/buscar?provincia=28&q=España` loses the explicit province entirely when saved, broadening restored searches and alerts to Spain.

**Expected:** Saved-search results/alerts preserve provincial scope. **Actual:** Alerts miss listings outside the capital, and explicit code-only scope can disappear.

**Impact:** Incomplete integration and broken saved-search promise, not financial overbooking.

**Smallest safe fix:** Persist canonical geographic scope with saved searches and restore/validate it in both frontend and backend; migrate unambiguous old province-name searches deliberately while retaining actual old city searches. Avoid blindly reinterpreting all old city-name saved searches.

**Regression:** Save Madrid provincial scope, publish Getafe postcode28901, verify notification; Barcelona does not trigger; explicit provincial code with generic q round-trips.

**Confidence:** High, actual `_saved_search_payload` + compiled SQL and real saved-search/publication/notifications HTTP routes executed with PostGIS. Control capital publication produces notification while Getafe does not. Email delivery not exercised. Integration regression at HEAD.

### GEO-04 — P2 — Mounted fallback address resolvers remain Tenerife-only

**Locations:** `src/components/publish-smart-address-autocomplete.tsx:137,271,304,329,360,584,620`; `src/components/publish-exact-address-sync.tsx:109,154,245,265–272`; mount chain `publish-route-enhancers.tsx:6–7 → publish-address-lifecycle.tsx:95–96`.

**Root cause:** HEAD changed the native Google widget in `publish-location-enhancer.tsx:435,450` to Spain, but did not change the separate smart/fallback and exact-address pipelines. They request a Tenerife restriction, reject valid mainland points and append Tenerife to geocoder queries. Exact-address sync also returns early for blank selectedCity although city is now hidden and populated only by resolution.

**Reproduction conditions:** Enter a Madrid street/postcode using the existing fallback text input when native Google widget unavailable, or use smart/geocoder fallback. Madrid coordinates fail the explicit `isInsideTenerife` checks and cannot resolve. Native successful Google selection can work across Spain; do not state all Madrid publication is broken.

**Expected:** All supported automatic selection/fallback paths cover the approved geography. **Actual:** Only native widget was widened; fallback paths retain the island constraint and copy. Existing province browser test dispatches `112233:publish-location-selected` directly and thus bypasses these production resolvers.

**Impact:** Mainland users cannot recover from native Places errors through advertised fallback. Core country expansion remains incomplete.

**Fix/test:** Share country/address resolver scope across native/smart/fallback/exact paths; run real mocked Google prediction → selection → geocoder events for Madrid, both Canary provinces, Balearics, Ceuta/Melilla, and invalid foreign address. Browser reproduction delegated to parent's frontend audit; static restriction is confirmed.

**Confidence:** High for code-defined fallback restriction, browser execution NOT VERIFIED by this agent. Newly exposed integration issue at HEAD.

## Other checks / no overstated findings

- `require_top_address_mutable` blocks changed prefix during active or scheduled TOP / unresolved payment, and `_sync_matching_owner_listing_locations` calls it for every sibling (`listings.py:148–149`). The service takes advertising lock before mutating. This guard is effective for honest postcode-based changes; it does not verify postcode correctness (GEO-02).
- Admin promotion uses `require_province_top_slot` under advertising lock (`admin.py:295–297,333`); not an unguarded extra write path.
- Owner/admin response exposes street/postcode/exact fields; public response adds only `provinceCode` (`repositories/listings.py:184,257–269`; schemas separate `OwnedListingResponse`). Public map uses `Listing.location`, intentionally set equal to exact point by previous approved changes. Exact map publication is baseline behavior, not a newly established privacy regression from adding province.
- Owner write `provinceCode` itself is forbidden by Pydantic extra='forbid'; spoof through postcode is the actual hole.
- Province code validation rejects unknown codes; database search expression checks five ASCII digits / prefix 01–52 and trims spaces consistently with Python parser.
- No new province schema migration/backfill/index. Existing private postcode column was added by migration0007 with default empty string. `docs/province-search-and-top.md` explicitly tells operators to audit missing legacy postcodes and overbooked historical provinces, but does not perform remediation. Actual production invalid/overbooked row counts NOT VERIFIED. Historical >3 promotions remain possible until operator action; don't claim observed production overbooking.
- Province expression applies regex/substr to `postcode` without an expression index; no performance run/explain obtained, so scaling risk only, not confirmed P2/P3 defect. Existing geo index can still help spatial searches.
- New `/listings/provinces/counts` route omits `optional_user/enforce_listing_view_access`, unlike regions/search. It returns public aggregate counts even for account with browsing restriction. Counts are public to anonymous visitors anyway, so this is a policy inconsistency of low demonstrated security impact, not a major data leak.
- Search history continues to reject non-Tenerife names (`app-context.tsx:578–582`); province searches outside Tenerife are not remembered. Lower-priority related UI gap; not counted separately from integration findings without checking desired scope.

## Acceptance-matrix contributions

| ID | Result supported here |
|---|---|
| T01 | FAIL against adversarial address validation: authenticated HTTP creation persisted Madrid address/coordinates in Barcelona province via forged postcode. |
| T02 | Static honest postcode move updates search scope, active/pending TOP blocks change; full DB path NOT VERIFIED here. |
| T03 | FAIL: incomplete/garbage postcode accepted by actual schema/write service. |
| T04 | FAIL: literal province field forbidden but postcode permits manual geographical selection, proven HTTP; no visible municipality dropdown is a frontend fact only. |
| T19 | Honest prefix change guarded; invariant under honest changes requires parent's DB/concurrency tests; physical move with stale prefix possible (GEO-02). |
| T20 | FAIL: HTTP201 creation and HTTP200 postcode-only patch accepted other-province postcode; TOP availability reports forged province. |
| T22 | FAIL for compatibility: old default empty postcode yields null province; ordinary **new** imports also affected (GEO-01), proven real upsert+SQL+HTTP. Actual production population unknown. |
| T25 | FAIL for saved provincial alerts (GEO-03, executed real notification API), fallback geography scope (GEO-04, static here); other application pages delegated. |

Release contribution: GEO-01 and GEO-02 block certifying full province-based requirement; 8132/address-source decisions must be resolved separately from code defects.
