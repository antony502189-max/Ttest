"""Offline real-DB composition rehearsal; never reads a real key/budget journal.

Run only inside the owned decision-transport-fixture lab from committed source.
Provider transport alone is replaced. Simulated historical reservations live in
a new disposable temporary file and are explicitly identified in the result.
"""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httpx
from pydantic import SecretStr

from app.services.ai_closed_deepseek import EvaluationBudget
from lab.ai_text import ORIGIN, require_lab
from lab.closed_ui import APPROVAL, BASELINE_ATTEMPTS, CORPUS_SHA256, create_app, smoke_cases
from lab.closed_ui_test_support import admission_fixture


async def rehearse():
    require_lab()
    if os.environ.get("AI_LAB_PARSER") != "decision-transport-fixture":
        raise RuntimeError("offline decision-transport-fixture lab required")
    cases, _ = smoke_cases()
    seen = []

    def handle(request):
        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        case = next(c for c in cases if c["text"] == data["text"] and c["current"] == data["criteria"])
        seen.append(case["id"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({"status": "patch", "patch": {
                "set": case["expected"], "remove": []}})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})

    with TemporaryDirectory(prefix="offline-ui-rehearsal-") as directory:
        journal = Path(directory) / "DISPOSABLE-simulated-history.sqlite3"
        budget = EvaluationBudget(journal, corpus_sha256=CORPUS_SHA256)
        for _ in range(BASELINE_ATTEMPTS):
            budget.reserve()
        with (patch.dict(os.environ, {"AI_LAB_PARSER": "closed-live-synthetic"}),
              patch("httpx.AsyncHTTPTransport", side_effect=lambda **kw: httpx.MockTransport(handle))):
            app = create_app(key=SecretStr("synthetic-test-only"), journal=journal, approval=APPROVAL,
                             approved_corpus_sha256=CORPUS_SHA256,
                             admission=admission_fixture(journal, source=os.environ["AI_LAB_SOURCE_SHA"]))
        headers = {"Origin": ORIGIN, "X-AI-Request": "1"}
        rows = []
        async with app.router.lifespan_context(app), httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url=ORIGIN, headers=headers) as client:
            contract = (await client.get("/api/v1/ai-search/lab-runtime")).json()
            client.headers.update({"X-AI-Lab-Mode": contract["parser"], "X-AI-Lab-Source": contract["source"],
                                   "X-AI-Lab-Instance": contract["instance"]})
            identity = await client.post("/api/v1/ai-search/identity")
            assert identity.status_code == 200
            for case in cases:
                session = await client.post("/api/v1/ai-search/sessions", json={"idempotency_key": str(uuid4())})
                assert session.status_code == 200
                intent = session.json()["intent"]
                body = {"session_id": intent["session_id"], "expected_version": 0,
                        "idempotency_key": str(uuid4()), "text": case["text"], "search": {"limit": 6}}
                response = await client.post("/api/v1/ai-search/query", json=body)
                assert response.status_code == 200
                answer = response.json()
                assert answer["operation"]["status"] == "succeeded"
                saved = await client.get("/api/v1/ai-search/sessions/" + intent["session_id"])
                assert saved.json()["intent"]["criteria"] == case["expected"]
                before = budget.summary()["attempts"]
                replay = await client.post("/api/v1/ai-search/query", json=body)
                assert replay.json()["operation"]["receipt"] == answer["operation"]["receipt"]
                assert budget.summary()["attempts"] == before
                rows.append({"id": case["id"], "passed": True, "exact_retry_no_new_attempt": True})
            assert budget.summary()["attempts"] == 54 and len(seen) == 3
            quota = await client.get("/api/v1/ai-search/quota")
            assert quota.json()["used"] == 3
        return {"mode": "OFFLINE_COMPOSITION_REHEARSAL", "provider_calls": 0,
                "simulated_baseline_attempts": 51, "fixture_transport_attempts": 3,
                "real_ui": False, "real_backend_pg_redis": True, "cases": rows,
                "real_eval_journal_opened": False, "real_key_opened": False}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(rehearse())))
