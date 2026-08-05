# Test report

> Historical verification snapshot recorded after the original full-stack integration update. It is retained for traceability and is not the current release gate. Current validation is defined by the GitHub workflows and `scripts/final-audit-local.sh`.

The recorded local verification was:

```text
backend: ruff check app tests        PASS
backend: mypy app                    PASS
backend: pytest -q -m "not s3"      38 passed, 1 deselected
backend: pytest -q tests/integration 7 passed, 1 skipped
frontend: npm run typecheck          PASS
frontend: npm run lint               PASS (one existing unused-helper warning)
frontend: npm run build              PASS
Docker PostGIS: alembic upgrade head PASS (historical head: 0015_integrity_constraints)
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

At the time of this snapshot, visual regression was intentionally not marked passing because the repository had no approved visual baseline available to that local run, and map routes required a configured Google Maps key or dedicated Maps stub. No generated snapshot was accepted as a new baseline.

Playwright CLI snapshots are local ephemeral artifacts under `.playwright-cli/`; they are not committed. For the current release gate and current migration head, use the workflows under `.github/workflows/` and `docs/database.md`.
