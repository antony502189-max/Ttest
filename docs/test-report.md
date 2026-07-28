# Test report

Latest local verification after the full-stack integration update:

```text
backend: ruff check app tests        PASS
backend: mypy app                    PASS
backend: pytest -q -m "not s3"      38 passed, 1 deselected
backend: pytest -q tests/integration 7 passed, 1 skipped
frontend: npm run typecheck          PASS
frontend: npm run lint               PASS (one existing unused-helper warning)
frontend: npm run build              PASS
Docker PostGIS: alembic upgrade head PASS (0015_integrity_constraints)
Playwright full-stack                3 passed, 1 skipped (desktop + 390×844)
Playwright accessibility (Axe)      28 passed (no serious/critical violations)
S3-compatible MinIO round-trip      1 passed (put/read/delete)
Compose runtime                      OpenAPI OK, /health/ready 200, Redis PONG
Docker: docker compose config        PASS
Backend: OpenAPI generation          PASS
```

Runtime checks used Docker PostGIS and FastAPI:

- registration creates a hashed e-mail verification token and an outbox entry;
- development outbox delivery marks the entry `sent`;
- `POST /auth/verify-email` completes a real browser verification flow;
- invalid verification links show the backend validation message;
- the verification route was inspected on desktop and 390×844 mobile viewports;
- `POST /listings/search` was exercised against the running PostGIS API.
- The full-stack tests register a host through FastAPI, create a PostgreSQL/PostGIS listing, then confirm that the SPA renders it from the real API on desktop and mobile. The mobile room-count filter request is also verified against the backend.

Visual regression is intentionally not marked passing: the repository has no committed `tests/visual-snapshots/` baseline, and the map routes need a configured Google Maps key or a dedicated Maps stub to capture the normal map state. The visual command was run; no generated snapshot was accepted as a new baseline.

Playwright CLI snapshots are local ephemeral artifacts under `.playwright-cli/`; they are not committed. CI runs frontend lint/typecheck/build and backend lint/typecheck/tests/migrations/Docker build. Full visual/a11y and all end-to-end coverage remain separate CI work where configured.
