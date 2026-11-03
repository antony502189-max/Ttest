"""Prepared closed LIVE UI composition. Import/prepare never opens keys or IO.

Not an activation switch for app.main or the offline lab launcher. Calling the
explicit factory requires a newly authorized synthetic smoke and reviewed egress.
"""
import argparse
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

import httpx
from pydantic import SecretStr

from app.services.ai_closed_deepseek import (
    MAX_MICRO_USD,
    RESERVE_MICRO_USD,
    EvaluationBudget,
    _BudgetTransport,
)
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, ProviderFailure
from lab.intent_eval import SyntheticCorpusGate, load_corpus

APPROVAL = "deepseek-synthetic-ui-smoke-v1"
CASE_IDS = ("ru-balcony", "es-monthly", "en-negation")
CORPUS_SHA256 = "7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288"
BASELINE_ATTEMPTS = 51
SMOKE_ATTEMPTS = 3
POLICY = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8, total_budget_seconds=10,
                        max_tokens=1024, max_attempts=1, retry_delay_seconds=0, max_response_bytes=65536)


def smoke_cases():
    cases, digest = load_corpus()
    if digest != CORPUS_SHA256:
        raise ProviderFailure("UI_SMOKE_CORPUS_MISMATCH")
    selected = [next(case for case in cases if case["id"] == case_id) for case_id in CASE_IDS]
    # Separate empty UI sessions, rental-mode selector explicitly 'none'. No
    # history or client-provided state can expand this synthetic allowlist.
    if any(case["current"] != {} for case in selected):
        raise ProviderFailure("UI_SMOKE_CORPUS_MISMATCH")
    return selected, digest


class ExistingSmokeBudget(EvaluationBudget):
    """Reopen only: never create/reset/migrate/move the approved eval journal.

    The absolute 54-attempt fence survives restarts and competing UI processes.
    Baseline 51 stays spent, even when provider ACK or usage is unavailable.
    """
    def __init__(self, path: Path, *, corpus_sha256: str):
        self.path = Path(path).resolve(strict=True)
        # A root-created eval journal may be readable by the non-root UI user
        # but reject the first INSERT. Fail startup before reading credentials.
        if not os.access(self.path, os.W_OK) or not os.access(self.path.parent, os.W_OK):
            raise ProviderFailure("UI_SMOKE_JOURNAL_NOT_WRITABLE")
        with self._connect() as db:
            self._verify(db, corpus_sha256)
        self.corpus_sha256 = corpus_sha256

    @contextmanager
    def _connect(self):
        # mode=rw also prevents an accidental reset if the file disappears
        # between preflight and IO. SQLite errors remain fail-closed.
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)) as db, db:
            yield db

    @staticmethod
    def _verify(db, digest):
        if db.execute("SELECT corpus FROM binding WHERE id=1").fetchone() != (digest,):
            raise ProviderFailure("EVALUATION_JOURNAL_MISMATCH")
        calls, spent = db.execute("SELECT count(*), coalesce(sum(reserved),0) FROM attempts").fetchone()
        if calls < BASELINE_ATTEMPTS or spent < BASELINE_ATTEMPTS * RESERVE_MICRO_USD:
            raise ProviderFailure("UI_SMOKE_BASELINE_MISSING")
        return calls, spent

    def reserve(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, spent = self._verify(db, self.corpus_sha256)
            if calls >= BASELINE_ATTEMPTS + SMOKE_ATTEMPTS or spent + RESERVE_MICRO_USD > MAX_MICRO_USD:
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            return db.execute("INSERT INTO attempts(reserved) VALUES (?)", (RESERVE_MICRO_USD,)).lastrowid


class ClosedUIParser(DecisionDeepSeekIntent):
    def __init__(self, *, key: SecretStr, journal: Path, approval: str, approved_corpus_sha256: str):
        cases, digest = smoke_cases()
        if approval != APPROVAL or approved_corpus_sha256 != digest:
            raise ProviderFailure("LIVE_UI_SMOKE_APPROVAL_REQUIRED")
        if not isinstance(key, SecretStr) or not key.get_secret_value():
            raise ProviderFailure("DEDICATED_TEST_KEY_REQUIRED")
        self.budget = ExistingSmokeBudget(journal, corpus_sha256=digest)
        self.key, self.gate, self.policy = key, SyntheticCorpusGate(cases), POLICY
        self.transport = _BudgetTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), self.budget)


def create_app(*, key: SecretStr, journal: Path, approval: str, approved_corpus_sha256: str):
    # Deliberately no environment-key loader or generic 'live' parser mode.
    # Existing lab launcher remains offline and rejects live credentials.
    from lab.ai_text import _assemble_app, require_lab
    require_lab(closed_ui=True)
    return _assemble_app(lambda: ClosedUIParser(key=key, journal=journal, approval=approval,
                                               approved_corpus_sha256=approved_corpus_sha256))


def plan():
    cases, digest = smoke_cases()
    return {"schema": "ai-closed-ui-smoke-plan.v1", "status": "PREPARED_NOT_AUTHORIZED",
            "origin": "https://localhost:9443", "corpus_sha256": digest,
            "case_ids": list(CASE_IDS), "policy": POLICY.model_dump(),
            "sessions": "three fresh owned sessions, rental_mode unset; no arbitrary text",
            "outbound": "fixed instructions/schema + exact synthetic text/current criteria only",
            "journal": "SAME output/ai-intent-provider-v1/budget.sqlite3; existing binding required",
            "baseline_attempts": BASELINE_ATTEMPTS, "max_new_http_attempts": SMOKE_ATTEMPTS,
            "max_new_reserved_micro_usd": SMOKE_ATTEMPTS * RESERVE_MICRO_USD,
            "absolute_attempt_fence": BASELINE_ATTEMPTS + SMOKE_ATTEMPTS,
            "cumulative_max_micro_usd": MAX_MICRO_USD,
            "checks": ["UI -> shared strict adapter -> verified SQL cards/map",
                       "exact retry returns same receipt without new attempt",
                       "reload returns owned result without new attempt",
                       "unapproved text/state rejected before provider IO"],
            "gates": ["explicit NEW spend/outbound approval", "review isolated network/egress and key mount",
                      "verify current provider rates before authorization"],
            "provider_calls_made": 0, "real_user_outbound": "BLOCKED",
            "cases": [{"id": c["id"], "text": c["text"], "current": c["current"],
                       "expected": c["expected"]} for c in cases]}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(plan(), output, ensure_ascii=False, indent=2)
        output.write("\n")
