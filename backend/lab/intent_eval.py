"""Closed synthetic intent evaluation, no DB/browser/app runtime.

Prepare is offline. Live execution needs an explicit corpus/data approval and a
separate environment key. Never import or start app.main from this composition.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr

from app.schemas.ai_search_intent import Criteria, SearchIntent, apply_patch
from app.services.ai_closed_deepseek import (
    APPROVAL,
    MAX_CALLS,
    MAX_MICRO_USD,
    POLICY,
    RESERVE_MICRO_USD,
    ClosedDeepSeekIntent,
    EvaluationBudget,
)
from app.services.ai_deepseek_intent import OutboundIntentInput, ProviderFailure, _criteria_state

CORPUS = Path(__file__).with_name("intent_cases.v1.json")


def load_corpus(path=CORPUS):
    raw = path.read_bytes()
    cases = json.loads(raw)
    if not cases or len(cases) > 24 or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("invalid evaluation corpus")
    for case in cases:
        Criteria.model_validate_json(json.dumps(case["current"]))
        if "expected" in case:
            Criteria.model_validate_json(json.dumps(case["expected"]))
        elif not set(case["reject"]) <= {"INTENT_CLARIFICATION_REQUIRED", "INTENT_NO_CHANGE", "INTENT_UNSUPPORTED"}:
            raise ValueError("invalid expected rejection")
    return cases, hashlib.sha256(raw).hexdigest()


def state(case):
    return SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
                        session_id=UUID("00000000-0000-4000-8000-000000000004"), version=0,
                        criteria=Criteria.model_validate_json(json.dumps(case["current"])))


class SyntheticCorpusGate:
    """Exact allowlist, not a claim of general PII redaction/privacy certification.

    No arbitrary user messages, histories, listings, identifiers or payloads can
    pass this gate. Labels/expected answers are never transmitted to the model.
    """
    def __init__(self, cases):
        self.allowed = frozenset((case["text"], json.dumps(case["current"], sort_keys=True)) for case in cases)

    async def prepare(self, text, current):
        criteria = current.criteria.model_dump(mode="json", exclude_none=True)
        if (text, json.dumps(criteria, sort_keys=True)) not in self.allowed:
            raise ProviderFailure("SYNTHETIC_OUTBOUND_CASE_NOT_APPROVED")
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek",
                                   purpose="intent_patch", text=text, criteria=current.criteria)


def manifest(cases, digest):
    return {"schema": "ai-intent-evaluation-plan.v1", "corpus_sha256": digest, "cases": len(cases),
            "provider": "deepseek", "model": POLICY.model, "policy": POLICY.model_dump(),
            "data": "Only versioned synthetic text + current typed criteria + fixed schema/instructions; "
                    "no labels, identity, quota, SQL, history or catalog data",
            "max_http_attempts": MAX_CALLS, "max_reserved_micro_usd": MAX_MICRO_USD,
            "reserved_micro_usd_per_attempt": RESERVE_MICRO_USD,
            "billing_limit_note": "Conservative local admission allowance, not a provider billing guarantee. "
                                  "A separate funded/capped test account is required; verify current rates.",
            "case_ids": [case["id"] for case in cases], "live_calls_made": 0}


async def evaluate(parser, cases):
    results = []
    for case in cases:
        started = time.monotonic()
        row = {"id": case["id"], "language": case["language"], "category": case["category"]}
        try:
            current = state(case)
            patch = await parser.parse(case["text"], current)
            actual = _criteria_state(apply_patch(current, patch).criteria)
            expected = _criteria_state(Criteria.model_validate_json(json.dumps(case.get("expected", {}))))
            row.update(outcome="patch", typed_patch=True, passed="expected" in case and actual == expected)
            row["different_criteria"] = sorted(key for key in actual.keys() | expected.keys()
                                               if actual.get(key) != expected.get(key))
        except ProviderFailure as error:
            # Exception messages from arbitrary dependencies never enter evidence.
            code = str(error)
            if not re.fullmatch(r"[A-Z][A-Z_]{1,80}", code):
                code = "EVALUATION_INTERNAL_FAILURE"
            row.update(outcome=code, typed_patch=False, passed=code in case.get("reject", []))
        row["latency_ms"] = round((time.monotonic() - started) * 1000, 2)
        results.append(row)
        if row["outcome"] in {"PROVIDER_COST_BUDGET_EXHAUSTED", "PROVIDER_USAGE_ALLOWANCE_EXCEEDED"}:
            break
    by_category = {}
    for row in results:
        group = by_category.setdefault(row["category"], {"passed": 0, "evaluated": 0})
        group["evaluated"] += 1
        group["passed"] += int(row["passed"])
    return {"evaluated": len(results), "passed": sum(row["passed"] for row in results),
            "total": len(cases), "all_passed": len(results) == len(cases) and all(row["passed"] for row in results),
            "typed_patch_count": sum(row["typed_patch"] for row in results),
            "by_category": by_category, "results": results}


async def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--live", action="store_true", help="Requires explicit external-data/spend approval")
    cli.add_argument("--approval")
    cli.add_argument("--approved-corpus-sha256")
    cli.add_argument("--journal", type=Path)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    cases, digest = load_corpus()
    plan = manifest(cases, digest)
    if args.output.exists():
        cli.error("evidence output already exists; preserve previous results")
    if args.live:
        if args.approval != APPROVAL or args.approved_corpus_sha256 != digest or args.journal is None:
            cli.error("explicit approval, exact reviewed corpus hash and persistent journal required")
        key = os.environ.get("AI_INTENT_EVAL_DEEPSEEK_KEY", "")
        if not key:
            cli.error("dedicated AI_INTENT_EVAL_DEEPSEEK_KEY is required; do not reuse application credentials")
        budget = EvaluationBudget(args.journal, corpus_sha256=digest)
        parser = ClosedDeepSeekIntent(key=SecretStr(key), gate=SyntheticCorpusGate(cases),
                                      budget=budget, approval=args.approval)
        result = await evaluate(parser, cases)
        result.update(schema="ai-intent-evaluation-result.v1", mode="LIVE", corpus_sha256=digest,
                      provider="deepseek", model=POLICY.model, budget=budget.summary())
    else:
        result = plan
    # x preserves immutable evidence on racing invocations too. Never dump inputs,
    # provider bodies, keys, arbitrary exception details or model-generated prose.
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({key: result[key] for key in ("corpus_sha256", "evaluated", "passed", "all_passed", "mode")
                      if key in result}))
    return 0 if not args.live or result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
