"""Fake-LIVE root for closed local contract tests. No provider key or egress.

Not selected by either ordinary launcher or the real closed_ui_entry. The only
credential is a fixed dummy and transport is unconditionally MockTransport.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from app.services.ai_closed_deepseek import EvaluationBudget
from lab.ai_text import require_lab
from lab.closed_ui import APPROVAL, CORPUS_SHA256, smoke_cases
from lab.closed_ui import create_app as compose
from lab.closed_ui_test_support import admission_fixture

_directory = None


def create_app():
    require_lab(closed_ui=True)
    global _directory
    _directory = TemporaryDirectory(prefix="closed-ui-fake-matrix-")
    journal = Path(_directory.name) / "DISPOSABLE-matrix.sqlite3"
    budget = EvaluationBudget(journal, corpus_sha256=CORPUS_SHA256)
    for _ in range(51):
        budget.reserve()
    def completion(request):
        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        case = next(c for c in smoke_cases()[0] if c["text"] == data["text"] and c["current"] == data["criteria"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({"status": "patch", "patch": {
                "set": case["expected"], "remove": []}})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})
    with patch("httpx.AsyncHTTPTransport", side_effect=lambda **kw: httpx.MockTransport(completion)):
        return compose(key=SecretStr("DISPOSABLE-dummy-not-a-provider-key"), journal=journal,
                       approval=APPROVAL, approved_corpus_sha256=CORPUS_SHA256,
                       admission=admission_fixture(journal, source=os.environ["AI_LAB_SOURCE_SHA"]))
