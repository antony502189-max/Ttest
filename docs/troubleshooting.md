# Troubleshooting and diagnostics

Start by identifying the environment: **mock Vite, local Docker/PostGIS or production VPS**. Check the exact Git SHA and whether the issue reproduces in a clean browser context. Avoid speculative data repair.

## Local frontend / API

| Symptom | Check | Safe next step |
| --- | --- | --- |
| Search shows no listings | `VITE_ENABLE_MOCK_MODE`, Network request payload and response, mode/price filters | Confirm API base URL and data; mock fixtures do not equal live catalog |
| 404 on API | `/api/v1` prefix, correct backend port, health | Fix `VITE_API_BASE_URL` and restart Vite |
| API docs return 404 in production | Expected behavior | Use dev OpenAPI; don't expose Swagger on production |
| Map blank or missing controls | Browser console, Maps JS key/referrer restrictions, map ID | Verify enabled APIs and host, avoid a broad unrestricted key |
| Photos/video unavailable | Upload endpoint, private media object, MinIO health, media IDs | Inspect logs and reference mapping; do not make bucket public |
| Backend refuses startup | `APP_ENV`, required config, database health, secrets presence | Check against templates **without sharing secret values** |
| Browser test screenshot differs | Look at actual/expected/diff artifact, marker/data timing, recent UX changes | Fix cause; update baseline only after explicit visual review |

### Location search: Spain and communities

- Home starts without Tenerife selected. If it still says Tenerife, check active `build-info.json` and frontend bundle version before editing copy.
- Input should expand **inline** on the existing location screen. If region suggestions are absent, check `src/lib/spain-communities.ts` and whether the localized field is focused.
- `Barcelona` should rank Cataluña (`09`) first. With broad partial terms like `barce`, other municipalities may also match; ranking should still put the recognized city first.
- Counts load from **POST** `/api/v1/listings/regions/counts`; method GET will not work. Check request `rentalMode`/price filters, 17-item response and actual API error, rather than substituting hard-coded values.
- A selected `comunidad=09` route must send `autonomousCommunity:"09"` to cards/map and show Catalonia in the results header. If the URL changes but results do not, inspect the backend payload and query predicates.
- Map points outside region borders or records with missing/approximate coordinates may affect totals. Cross-check counts/cards with the **same** filters.
- If near-me rejects Madrid as "outside Tenerife", a stale frontend is running. Current geolocation uses Spain's community geometry and rejects coordinates outside supported territory.

### Map and return history

- First visit should show Spain + Canary Islands overview; old anonymous visits use localStorage key `112233:map-last-search-area:v2` with 180-day freshness check.
- Repeat visit fits a **70 km radius** around the nearest virtual cell center; exact zoom differs by screen dimensions. No circles appear on screen.
- Close/reload after pan: generated `mapAuto=1` cameras must not win over 70 km recall. An explicit bookmarked camera and a Back return inside the same document have their own priority.
- If the map jumps, inspect URL parameters `mapLat/mapLng/mapZoom`, `mapAuto`, `vista`, `comunidad`, `lat/lng` and drawn polygons. A named selected region should not be overwritten by anonymous map history.
- Do not clear users' localStorage globally to mask a logic bug. Validate with `tests/navigation-history.spec.ts`.

## Backend and PostGIS

```bash
docker compose ps
docker compose logs --tail=100 backend postgres
curl -fsS http://localhost:8000/health/ready
```

Check applied Alembic revision (current source head: `0056_external_scope_checkpoint`), PostGIS extension, DB connection pool and private Redis/MinIO services. Backend regional filter is a `ST_Intersects` predicate over listed points; it is not a city text search. For slow nationwide counts, measure `EXPLAIN (ANALYZE, BUFFERS)` against representative **non-production** or approved read-only data and inspect relevant GiST/index plans before rewriting the API.

## Production: deployment hangs or fails

**Do not run a second deploy until the first is confirmed finished.** On VPS `169.58.147.65`:

```bash
hostname
pgrep -af 'deploy-release.sh' || true
readlink -f /srv/112233.es/current
docker ps -a --filter name=ttest-production
```

Then inspect the specific operator log under `/srv/112233.es/releases/` and the target `<sha>.deploy-info`. `status=in_progress` with a running process is **not** an error. `status=failed` requires checking rollback and `<sha>.failed.log`. Verify `current` and public `/build-info.json` before declaring success. A `tail -f` racing an uncreated log does not imply that the deploy failed.

Read-only health tool:

```bash
bash /srv/112233.es/current/deploy/production-monitor-check.sh
```

**Never** use `docker volume prune`, `docker compose down -v`, `docker system prune`, delete backup archives or bypass the release lock. Releasing and data cleanup are separate operations. Escalate with redacted timestamps, exact SHA and error lines — not credentials.

[Operations](production-operations.md) · [Monitoring](production-monitoring.md) · [Testing](testing.md).
