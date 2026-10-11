# ADR 0002 — Self-hosted VPS as production origin

**Status:** accepted for current production architecture.  
**Decision context:** the original GitHub Pages frontend + separate backend prototype is documented in [ADR 0001](0001-backend-boundary.md), now superseded for **hosting**, while its security/transport boundaries largely remain.

## Context

The marketplace needs a same-origin public frontend/API, PostgreSQL/PostGIS geography, private uploaded media, background imports and a transactional SMTP outbox, and safe release/rollback with persistent state. GitHub Pages cannot host those backend workloads and does not represent the live runtime.

## Decision

- Use Contabo VPS `169.58.147.65` with public `https://app.112233.es`. Existing Traefik serves HTTPS and discovers the Nginx frontend through Docker labels.
- Serve the Vite/React static frontend and proxy `/api/v1` to FastAPI using Nginx. No production GitHub Pages, Vercel or Netlify deployment.
- Run PostgreSQL/PostGIS, Redis and private MinIO on isolated Docker networks; persistent production volumes survive app releases.
- Keep source mirror `/srv/112233.es/repo`, per-SHA immutable Git worktrees under `releases/`, active `current` symlink, and a VPS-only mode-600 environment file.
- Use `deploy/deploy-release.sh` accepting only the exact current `origin/main` SHA. Serialize operations with `flock`; back up and smoke-test; rollback application to known prior release upon controlled failure.
- Keep destructive data maintenance and data-service image migration **out of ordinary code releases**. Require separate approval, backup/restore verification and safety gates.
- Public `/api/docs` and `/api/openapi.json` must be disabled in production.

## Consequences

- GitHub PR/CI ensures code quality, not what is running in production. The release's SHA must be verified through the `current` symlink and public `build-info.json`.
- Production operator access and recovery are VPS workflows; do not mutate runtime using GitHub README instructions or delete DB/media volumes.
- Frontend continues using its typed `src/api/` boundary; server continues authorizing public versus exact location data.
- A planned change of public host, stateful-service digest or backup regime needs a new reviewed ADR/runbook revision.

Authoritative procedures: [Deployment](../deployment.md) and [Production operations](../production-operations.md).
