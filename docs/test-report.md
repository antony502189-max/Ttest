# Test report

Latest local verification after the mail-outbox integration:

```text
backend: ruff check app tests        PASS
backend: mypy app                    PASS
backend: pytest -q                  13 passed
frontend: npm run typecheck          PASS
frontend: npm run lint               PASS (one existing unused-helper warning)
frontend: npm run build              PASS
Docker: alembic current              0014_session_audit (head)
Playwright E2E smoke                 PASS (1 passed, 24.4s)
```

Runtime checks used Docker PostGIS and FastAPI:

- registration creates a hashed e-mail verification token and an outbox entry;
- development outbox delivery marks the entry `sent`;
- `POST /auth/verify-email` completes a real browser verification flow;
- invalid verification links show the backend validation message;
- the verification route was inspected on desktop and 390×844 mobile viewports;
- `POST /listings/search` was exercised against the running PostGIS API.
- Playwright `tests/e2e.spec.ts` critical home/navigation/dataset smoke passed with the explicit QA mock mode.

Playwright CLI snapshots are local ephemeral artifacts under `.playwright-cli/`; they are not committed. CI runs frontend lint/typecheck/build and backend lint/typecheck/tests/migrations/Docker build. Full visual/a11y and all end-to-end coverage remain separate CI work where configured.
