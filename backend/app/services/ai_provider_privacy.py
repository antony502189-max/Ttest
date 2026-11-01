"""Fail-closed boundary for real-user DeepSeek input, with no activation flag.

The policy is a review record, not an authorization token. Completing its review
requires a separately reviewed implementation; editing JSON cannot enable IO.
"""
import json
from pathlib import Path
from typing import Literal

from ..schemas.ai_search_quota import StrictContract
from .ai_deepseek_intent import ProviderFailure


class DeepSeekPrivacyReview(StrictContract):
    schema_version: Literal["deepseek-outbound-review.v1"]
    provider: Literal["deepseek"]
    endpoint: Literal["https://api.deepseek.com/chat/completions"]
    purpose: Literal["rental_search_intent_only"]
    status: Literal["blocked"]
    real_user_outbound: Literal[False]
    account_reference: Literal["closed-intent-eval-account-unverified"]
    accountable_owner: Literal["unassigned"]
    account_training_exclusion: Literal["unverified"]
    account_retention_days: None
    account_deletion_sla_days: None
    account_processing_region: Literal["unverified"]
    account_contract_reference: None
    minimization: Literal["deny_all_real_user_text"]
    allowed_future_fields: tuple[Literal["text", "criteria"], ...]
    reviewed_on: Literal["2026-11-01"]


def load_review(path: Path) -> DeepSeekPrivacyReview:
    review = DeepSeekPrivacyReview.model_validate_json(path.read_bytes())
    if review.allowed_future_fields != ("text", "criteria"):
        raise ValueError("OUTBOUND_FIELD_POLICY_INVALID")
    return review


class RealUserOutboundDenied:
    """Rejects everything before provider payload construction, credentials or IO.

    No regex/DLP claim: arbitrary text cannot currently be proven minimized.
    Account settings and data approval are not inferred from a corpus approval.
    """
    async def prepare(self, text, current):
        raise ProviderFailure("REAL_USER_OUTBOUND_NOT_APPROVED")


if __name__ == "__main__":
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("policy", type=Path)
    args = cli.parse_args()
    review = load_review(args.policy)
    print(json.dumps({"schema": review.schema_version, "configuration_valid": True,
                      "real_user_outbound": False, "release_gate": "BLOCKED"}))
