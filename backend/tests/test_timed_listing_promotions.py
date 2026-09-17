from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.admin import _promotion_metadata


def promotion(*, start: datetime, end: datetime | None, daily: int = 100, total: int | None = None):
    return SimpleNamespace(
        boosted_at=start,
        starts_at=start,
        ends_at=end,
        daily_price_cents=daily,
        total_price_cents=total,
    )


def test_active_timed_promotion_is_public_and_exposes_price_snapshot() -> None:
    now = datetime.now(UTC)
    row = promotion(
        start=now - timedelta(hours=1),
        end=now + timedelta(days=6, hours=23),
        total=700,
    )

    result = _promotion_metadata(row)

    assert result["promoted"] is True
    assert result["promotionState"] == "active"
    assert result["promotionDays"] == 7
    assert result["promotionDailyPriceCents"] == 100
    assert result["promotionTotalPriceCents"] == 700


def test_future_promotion_is_scheduled_not_public_top() -> None:
    now = datetime.now(UTC)
    row = promotion(start=now + timedelta(days=2), end=now + timedelta(days=9), total=700)

    result = _promotion_metadata(row)

    assert result["promoted"] is False
    assert result["promotionState"] == "scheduled"
    assert result["promotionDays"] == 7


def test_expired_promotion_remains_visible_to_admin_but_not_public_top() -> None:
    now = datetime.now(UTC)
    row = promotion(start=now - timedelta(days=8), end=now - timedelta(days=1), total=700)

    result = _promotion_metadata(row)

    assert result["promoted"] is False
    assert result["promotionState"] == "expired"
    assert result["promotionDays"] == 7


def test_legacy_promotion_without_window_remains_active_until_reconfigured() -> None:
    now = datetime.now(UTC)
    row = SimpleNamespace(boosted_at=now - timedelta(days=2), daily_price_cents=None, total_price_cents=None)

    result = _promotion_metadata(row)

    assert result["promoted"] is True
    assert result["promotionState"] == "active"
    assert result["promotionEndsAt"] is None
    assert result["promotionDays"] is None
