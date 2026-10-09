from pathlib import Path
import re
from app.services.rental_policy import MAX_MONTHLY_RENT_EUR, POLICY_VERSION


def test_frontend_backend_policy_contract_stays_synchronized():
    root = Path(__file__).resolve().parents[2]
    contract = (root / "src/lib/rental-policy.ts").read_text(encoding="utf-8")
    assert int(re.search(r"MAX_MONTHLY_RENT_EUR = (\d+)", contract).group(1)) == MAX_MONTHLY_RENT_EUR
    assert POLICY_VERSION in contract
