"""Fixed clarification reasons, never provider prose or partial intent state."""
from typing import Literal

from .ai_search_quota import FailureCode, StrictContract

ClarificationReason = Literal["budget_period", "rental_mode", "balcony_requirement", "location", "dates", "unsupported"]

REASONS: dict[str, ClarificationReason] = {
    "CLARIFY_BUDGET_PERIOD": "budget_period", "CLARIFY_RENTAL_MODE": "rental_mode",
    "CLARIFY_BALCONY_REQUIREMENT": "balcony_requirement", "CLARIFY_LOCATION": "location",
    "CLARIFY_DATES": "dates", "CLARIFY_UNSUPPORTED": "unsupported",
}


class IntentClarification(StrictContract):
    reason: ClarificationReason

    @property
    def failure_code(self) -> FailureCode:
        return FailureCode(next(code for code, reason in REASONS.items() if reason == self.reason))
