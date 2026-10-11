# Contributing to 112233.es

## Workflow

1. Read [README](../README.md) and [Documentation hub](index.md). Pick the current **source-code contract** relevant to your change.
2. Create a short-lived topic branch from the latest `main`. Never force-push or disable protection on `main`.
3. Keep PRs focused; separate implementation, data migration, production operation and unrelated UI redesign.
4. Preserve product modes `Vivienda` / `Turismo`, publication/gallery flows, and production listing/media integrity.
5. Add tests verifying observable behavior (including boundaries and failure cases), plus documentation for any changed URL, API, config, migration or operational workflow.
6. Run relevant local checks, open a PR, wait for required checks on **the final HEAD**, review the diff and merge by protected GitHub flow.
7. Document release notes and deploy only through the controlled operator path after merge.

## Project conventions

- **Frontend:** TypeScript strict checks, React, Vite, `src/api/` as the only transport boundary, lazy route chunks. `HashRouter` user URLs are not FastAPI paths.
- **Backend:** Python 3.12+ (CI includes 3.13), FastAPI, SQLAlchemy async, Pydantic v2 and PostgreSQL/PostGIS. Use schema validation and backend authorization for all untrusted inputs.
- **Locales:** maintain ES/EN/RU text alignment and capitalization; do not hard-code Tenerife into Spain-wide labels or counts.
- **Regions:** `comunidad` in URLs and `autonomousCommunity` in API DTOs refer to two-character IDs `01`–`17`. Reuse polygon and municipality data, not name-guessing.
- **Map:** virtual 70 km history zones and explicit/drawn map searches are distinct; maintain browser session behavior and app Back semantics.
- **Privacy:** only public approximate listing positions in public cards/markers; keep exact addresses for authorized ownership/admin paths.
- **Data:** migration revisions already deployed are immutable. PostGIS is required for spatial integration tests. Never smuggle data cleanup into a code release.
- **External sources:** comply with provider access rules; no CAPTCHA bypass. Do not change source gates without operational approval.
- **Docs:** prefer updating the canonical guide and linking to it; preserve historical audits and clearly mark their date/limitations rather than silently rewriting their evidence.

## Suggested PR description

```text
Summary:
Why:
Scope (what is deliberately unchanged):
API/schema/migration implications:
Safety/data/backups:
Tests (exact commands and CI run):
Visual changes (screenshots/approved baseline if necessary):
Deployment & rollback impact:
Documentation updated:
```

## Minimum verification

```bash
npm run lint && npm run typecheck && npm run build
npx playwright test tests/spain-community-search.spec.ts
npx playwright test tests/navigation-history.spec.ts
```

For backend changes use Ruff/Mypy/pytest; for spatial changes run actual PostGIS integration tests. For production stack changes run the release-safety and configuration scripts. Do not update visual snapshots solely to make a failing test green.

## Issues and incident reports

Include reproducible steps, expected/actual behavior, browser and viewport, URL **without auth tokens**, observed current build SHA, relevant redacted errors and minimal safe screenshots. For production incidents attach status and redacted logs, but never an env file, SQL dump, user passport/address, bearer token or cookie.

[Testing](testing.md) · [Security](security-and-privacy.md) · [Release checklist](release-checklist.md).
