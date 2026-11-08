"""Positive rental grammar, not redaction or general real-user privacy clearance.

The entire input must parse. Only generated English constants and a bounded rent
amount leave this process. Unknown text is rejected, never partially scrubbed.
"""
import re
from decimal import Decimal

from app.schemas.ai_search_intent import Criteria, apply_patch
from app.services.ai_deepseek_intent import OutboundIntentInput, ProviderFailure

REMOVE = {
    "убери ограничение бюджета", "без ограничения бюджета", "без бюджета",
    "remove budget", "remove the budget limit", "no budget limit",
    "sin límite de presupuesto", "sin limite de presupuesto", "quita el presupuesto",
}
ALL = {"все варианты", "покажи все варианты", "all options", "show all options", "todas las opciones"}
PATTERNS = (
    r"(?:ищу |нужна |покажи |теперь )?(?:комнат[ау] |варианты )?(?:до|бюджет до|не дороже) ([1-9][0-9]{1,3})(?: евро| €)?(?: в месяц|/мес)",
    r"(?:find |show |now )?(?:a room |rooms )?(?:under|up to|budget up to) ([1-9][0-9]{1,3})(?: euros| eur| €)?(?: per month|/month)",
    r"(?:busco |ahora )?(?:una habitación |una habitacion |habitaciones )?(?:hasta|menos de) ([1-9][0-9]{1,3})(?: euros| eur| €)?(?: al mes|/mes)",
)


def minimize(text: str) -> str:
    if type(text) is not str or not 1 <= len(text) <= 160 or any(ord(c) < 32 for c in text):
        raise ProviderFailure("INTENT_UNSUPPORTED")
    value = text.casefold().strip().rstrip(".!?").strip()
    if value in REMOVE:
        return "Remove the budget criterion. Preserve all other criteria."
    if value in ALL:
        return "Remove the budget criterion. Preserve all other criteria."
    for pattern in PATTERNS:
        match = re.fullmatch(pattern, value)
        if match and 50 <= int(match[1]) <= 1000:
            return f"Set a hard budget of {int(match[1])} EUR monthly. Preserve all other criteria."
    raise ProviderFailure("INTENT_UNSUPPORTED")


def safe_criteria(criteria):
    value = criteria.model_dump(mode="json", exclude_none=True)
    if set(value) - {"rental_mode", "budget"}:
        raise ProviderFailure("INTENT_UNSUPPORTED")
    if value.get("rental_mode") != {"strength": "hard", "value": "long"}:
        raise ProviderFailure("INTENT_UNSUPPORTED")
    if "budget" in value:
        money = value["budget"]
        if (money["strength"] != "hard" or money["value"]["currency"] != "EUR"
                or money["value"]["period"] != "monthly" or not re.fullmatch(r"[1-9][0-9]{1,3}(?:\.0+)?", money["value"]["amount"])
                or not 50 <= float(money["value"]["amount"]) <= 1000):
            raise ProviderFailure("INTENT_UNSUPPORTED")
    return Criteria.model_validate(value)


class PilotGate:
    async def prepare(self, text, current):
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek",
            purpose="intent_patch", text=minimize(text), criteria=safe_criteria(current.criteria))


def validate_result(current, patch, canonical):
    actual = safe_criteria(apply_patch(current, patch).criteria).model_dump(mode="json", exclude_none=True)
    expected = current.criteria.model_dump(mode="json", exclude_none=True)
    if canonical.startswith("Remove"):
        expected.pop("budget", None)
    else:
        expected["budget"] = {"strength": "hard", "value": {"amount": canonical.split()[5], "currency": "EUR", "period": "monthly"}}
    if "budget" in actual:
        actual["budget"]["value"]["amount"] = format(Decimal(actual["budget"]["value"]["amount"]).normalize(), "f")
    if actual != expected:
        raise ProviderFailure("PILOT_SEMANTIC_RESULT_REJECTED")
