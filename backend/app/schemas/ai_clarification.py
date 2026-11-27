"""Fixed clarification reasons, never provider prose or partial intent state."""
from typing import Literal

from .ai_search_quota import FailureCode, StrictContract

ClarificationReason = Literal[
    "budget_period", "rental_mode", "balcony_requirement", "location", "dates", "unsupported",
    "budget", "accommodation", "pets", "alternatives", "conflict", "deposit", "party", "amenities",
]

REASONS: dict[str, ClarificationReason] = {
    "CLARIFY_BUDGET_PERIOD": "budget_period", "CLARIFY_RENTAL_MODE": "rental_mode",
    "CLARIFY_BALCONY_REQUIREMENT": "balcony_requirement", "CLARIFY_LOCATION": "location",
    "CLARIFY_DATES": "dates", "CLARIFY_UNSUPPORTED": "unsupported",
    "CLARIFY_BUDGET": "budget", "CLARIFY_ACCOMMODATION": "accommodation", "CLARIFY_PETS": "pets",
    "CLARIFY_ALTERNATIVES": "alternatives", "CLARIFY_CONFLICT": "conflict", "CLARIFY_DEPOSIT": "deposit",
    "CLARIFY_PARTY": "party", "CLARIFY_AMENITIES": "amenities",
}


class IntentClarification(StrictContract):
    reason: ClarificationReason

    @property
    def failure_code(self) -> FailureCode:
        return FailureCode(next(code for code, reason in REASONS.items() if reason == self.reason))
