from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.moderation import HomepageHeroPromotion
from app.services.homepage_hero import homepage_hero_response


def test_homepage_hero_response_reports_active_window_and_inclusive_day_count():
    now = datetime.now(UTC)
    row = HomepageHeroPromotion(
        id=1,
        listing_id=uuid4(),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=2, hours=23),
        configured_by=uuid4(),
    )
    response = homepage_hero_response(row)
    assert response.state == "active"
    assert response.days == 3


def test_homepage_hero_response_reports_expired_window():
    now = datetime.now(UTC)
    row = HomepageHeroPromotion(
        id=1,
        listing_id=uuid4(),
        starts_at=now - timedelta(days=3),
        ends_at=now - timedelta(seconds=1),
        configured_by=uuid4(),
    )
    assert homepage_hero_response(row).state == "expired"
