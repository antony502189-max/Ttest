"""Prepared closed LIVE UI composition. Import/prepare never opens keys or IO.

Not an activation switch for app.main or the offline lab launcher. Calling the
explicit factory requires a newly authorized synthetic smoke and reviewed egress.
"""
import argparse
import json
import logging
import os
import sqlite3
from contextlib import closing, contextmanager
from contextvars import ContextVar
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
from lab.closed_ui_authorization import Admission
from lab.closed_ui_spec import CASE_IDS, CORPUS_SHA256, SPEC
from lab.intent_eval import SyntheticCorpusGate, load_corpus

APPROVAL = "deepseek-synthetic-ui-smoke-v1"
BASELINE_ATTEMPTS = SPEC.baseline_attempts
SMOKE_ATTEMPTS = len(SPEC.case_ids)
POLICY = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8, total_budget_seconds=10,
                        max_tokens=1024, max_attempts=1, retry_delay_seconds=0, max_response_bytes=65536)
_logger = logging.getLogger(__name__)
_case = ContextVar("closed_ui_case", default=None)
_SAFE_FAILURES = frozenset({
    "PROVIDER_REQUEST_REJECTED", "PROVIDER_RETRIES_EXHAUSTED", "PROVIDER_USAGE_INVALID",
    "PROVIDER_TRANSPORT_FAILED", "PROVIDER_DEADLINE_EXCEEDED", "PROVIDER_RESULT_INVALID",
    "PROVIDER_RESPONSE_ENCODING_UNSUPPORTED", "PROVIDER_RESPONSE_TOO_LARGE",
    "PROVIDER_INPUT_ALLOWANCE_EXCEEDED", "PROVIDER_POLICY_MISMATCH",
    "PROVIDER_COST_BUDGET_EXHAUSTED", "PROVIDER_USAGE_ALLOWANCE_EXCEEDED",
    "SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED", "INTENT_CLARIFICATION_REQUIRED",
    "INTENT_NO_CHANGE", "INTENT_UNSUPPORTED",
})


class _UIBudgetTransport(_BudgetTransport):
    def __init__(self, inner, budget):
        self.case_budget = budget
        super().__init__(inner, self)

    def reserve(self):
        return self.case_budget.reserve(_case.get())

    def record_usage(self, ticket, data):
        return self.case_budget.record_usage(ticket, data)

    async def handle_async_request(self, request):
        response = await super().handle_async_request(request)
        # Fixed metadata only. Never read/log an error body, headers, URL,
        # request, credential, text or operation identity for diagnostics.
        log = _logger.info if 200 <= response.status_code < 300 else _logger.warning
        log("closed_ui_provider_http_status:%d", response.status_code)
        return response


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
    def __init__(self, path: Path, *, corpus_sha256: str, admission: Admission):
        self.admission = admission
        admission.check_journal(path)
        self.path = Path(path).absolute()
        admission.check_journal(self.path)
        # A root-created eval journal may be readable by the non-root UI user
        # but reject the first INSERT. Fail startup before reading credentials.
        if not os.access(self.path, os.W_OK) or not os.access(self.path.parent, os.W_OK):
            raise ProviderFailure("UI_SMOKE_JOURNAL_NOT_WRITABLE")
        with self._connect() as db:
            calls, spent = self._verify(db, corpus_sha256)
            data = admission.data
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            known = db.execute("SELECT digest FROM closed_ui_authorizations WHERE id=?",
                               (data["authorization_id"],)).fetchone() if "closed_ui_authorizations" in tables else None
            if known is not None and known != (admission.digest,):
                raise ProviderFailure("UI_AUTHORIZATION_BINDING_MISMATCH")
            if "closed_ui_origin" in tables and db.execute("SELECT journal_id FROM closed_ui_origin WHERE id=1").fetchone() != (data["journal_id"],):
                raise ProviderFailure("UI_JOURNAL_IDENTITY_MISMATCH")
            if known is None and (calls, spent) != (data["baseline_attempts"], data["baseline_reserved_micro_usd"]):
                raise ProviderFailure("UI_SMOKE_BASELINE_MISMATCH")
            if calls > data["baseline_attempts"] + data["max_new_attempts"]:
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
        self.corpus_sha256 = corpus_sha256

    @contextmanager
    def _connect(self):
        # mode=rw also prevents an accidental reset if the file disappears
        # between preflight and IO. SQLite errors remain fail-closed.
        self.admission.check_journal(self.path)
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)) as db, db:
            self.admission.check_journal(self.path)
            yield db

    @staticmethod
    def _verify(db, digest):
        if db.execute("SELECT corpus FROM binding WHERE id=1").fetchone() != (digest,):
            raise ProviderFailure("EVALUATION_JOURNAL_MISMATCH")
        calls, spent = db.execute("SELECT count(*), coalesce(sum(reserved),0) FROM attempts").fetchone()
        if calls < BASELINE_ATTEMPTS or spent < BASELINE_ATTEMPTS * RESERVE_MICRO_USD:
            raise ProviderFailure("UI_SMOKE_BASELINE_MISSING")
        return calls, spent

    def reserve(self, case_id):
        data = self.admission.data
        if case_id not in data["case_ids"]:
            raise ProviderFailure("UI_SMOKE_CASE_NOT_AUTHORIZED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, spent = self._verify(db, self.corpus_sha256)
            db.execute("CREATE TABLE IF NOT EXISTS closed_ui_origin (id INTEGER PRIMARY KEY CHECK(id=1), journal_id TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO closed_ui_origin VALUES (1,?)", (data["journal_id"],))
            if db.execute("SELECT journal_id FROM closed_ui_origin WHERE id=1").fetchone() != (data["journal_id"],):
                raise ProviderFailure("UI_JOURNAL_IDENTITY_MISMATCH")
            db.execute("CREATE TABLE IF NOT EXISTS closed_ui_authorizations (id TEXT PRIMARY KEY, digest TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS closed_ui_cases (journal_id TEXT NOT NULL, case_id TEXT NOT NULL, "
                       "attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempts(id), PRIMARY KEY(journal_id,case_id))")
            if db.execute("SELECT digest FROM closed_ui_authorizations WHERE id=?", (data["authorization_id"],)).fetchone() not in (
                    None, (self.admission.digest,)):
                raise ProviderFailure("UI_AUTHORIZATION_BINDING_MISMATCH")
            existing = db.execute("SELECT count(*) FROM closed_ui_cases WHERE journal_id=?", (data["journal_id"],)).fetchone()[0]
            if existing == 0:
                if (calls, spent) != (data["baseline_attempts"], data["baseline_reserved_micro_usd"]):
                    raise ProviderFailure("UI_SMOKE_BASELINE_MISMATCH")
                for old_case, ticket in data["prior_case_attempts"].items():
                    if db.execute("SELECT id FROM attempts WHERE id=?", (ticket,)).fetchone() is None:
                        raise ProviderFailure("UI_SMOKE_BASELINE_MISMATCH")
                    db.execute("INSERT INTO closed_ui_cases VALUES (?,?,?)", (data["journal_id"], old_case, ticket))
            if db.execute("SELECT 1 FROM closed_ui_cases WHERE journal_id=? AND case_id=?",
                          (data["journal_id"], case_id)).fetchone():
                raise ProviderFailure("UI_SMOKE_CASE_ALREADY_ATTEMPTED")
            if (calls >= data["baseline_attempts"] + data["max_new_attempts"] or calls >= SPEC.attempt_fence
                    or spent + RESERVE_MICRO_USD > min(MAX_MICRO_USD,
                        data["baseline_reserved_micro_usd"] + data["max_new_reserved_micro_usd"])):
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            db.execute("INSERT OR IGNORE INTO closed_ui_authorizations VALUES (?,?)", (data["authorization_id"], self.admission.digest))
            ticket = db.execute("INSERT INTO attempts(reserved) VALUES (?)", (RESERVE_MICRO_USD,)).lastrowid
            db.execute("INSERT INTO closed_ui_cases VALUES (?,?,?)", (data["journal_id"], case_id, ticket))
            return ticket


class ClosedUIParser(DecisionDeepSeekIntent):
    def __init__(self, *, key: SecretStr, journal: Path, approval: str, approved_corpus_sha256: str,
                 admission: Admission | None = None):
        cases, digest = smoke_cases()
        if approval != APPROVAL or approved_corpus_sha256 != digest:
            raise ProviderFailure("LIVE_UI_SMOKE_APPROVAL_REQUIRED")
        if admission is None:
            raise ProviderFailure("UI_SIGNED_AUTHORIZATION_REQUIRED")
        if not isinstance(key, SecretStr) or not key.get_secret_value():
            raise ProviderFailure("DEDICATED_TEST_KEY_REQUIRED")
        self.budget = ExistingSmokeBudget(journal, corpus_sha256=digest, admission=admission)
        self.cases = [c for c in cases if c["id"] in admission.data["case_ids"]]
        self.key, self.gate, self.policy = key, SyntheticCorpusGate(self.cases), POLICY
        self.transport = _UIBudgetTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), self.budget)

    async def parse(self, text, current):
        case_id = next((c["id"] for c in self.cases if c["text"] == text), None)
        token = _case.set(case_id)
        try:
            if current.version != 0:
                raise ProviderFailure("SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED")
            return await super().parse(text, current)
        except ProviderFailure as error:
            code = str(error) if str(error) in _SAFE_FAILURES else "PROVIDER_FAILURE"
            _logger.warning("closed_ui_provider_failure:%s", code)
            raise
        except Exception:
            _logger.warning("closed_ui_provider_failure:UI_PROVIDER_DEPENDENCY_FAILED")
            raise
        finally:
            _case.reset(token)


def create_app(*, key: SecretStr, journal: Path, approval: str, approved_corpus_sha256: str,
               admission: Admission | None = None):
    # Deliberately no environment-key loader or generic 'live' parser mode.
    # Existing lab launcher remains offline and rejects live credentials.
    from lab.ai_text import _assemble_app, require_lab
    require_lab(closed_ui=True)
    return _assemble_app(lambda: ClosedUIParser(key=key, journal=journal, approval=approval,
                                               approved_corpus_sha256=approved_corpus_sha256, admission=admission))


def plan():
    cases, digest = smoke_cases()
    return {"schema": "ai-closed-ui-smoke-plan.v1", "experiment": SPEC.version, "status": "PREPARED_NOT_AUTHORIZED",
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
