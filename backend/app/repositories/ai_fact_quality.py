"""Explicit SQL freshness guard; compose BEFORE count/order/LIMIT/aggregate."""
from sqlalchemy import and_, func, literal, select

from ..models import ExternalListingSource
from ..services.ai_fact_quality import FactQualityPolicy
from ..services.ai_hard_matching import HardMatchPlan


def source_freshness_predicate(listing_id, plan: HardMatchPlan, policy: FactQualityPolicy):
    policy = FactQualityPolicy.model_validate(policy)
    source = ExternalListingSource.__table__.alias("quality_source")
    now = func.statement_timestamp()
    age = literal(policy.max_age(plan))
    relevant = source.c.canonical_listing_id == listing_id
    healthy = and_(source.c.current_status == "active", source.c.last_success_at.is_not(None),
                   source.c.last_success_at <= now, source.c.last_success_at >= now - age)
    return and_(select(1).select_from(source).where(relevant).exists(),
                ~select(1).select_from(source).where(relevant, ~func.coalesce(healthy, False)).exists())

async def audit_catalog(pipeline, *, eligibility, plan: HardMatchPlan, policy: FactQualityPolicy, limit: int):
    """Bounded offline report; overflow fails rather than reporting truncated counts."""
    from ..models import Listing
    from ..services.ai_fact_quality import classify, counters

    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("explicit cohort bound 1..1000 required")
    policy = FactQualityPolicy.model_validate(policy)
    async with pipeline.sessions() as session, session.begin():
        from sqlalchemy import text
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        ids = (await session.scalars(select(Listing.id).where(
            Listing.status == "published", Listing.deleted_at.is_(None), eligibility
        ).order_by(Listing.id).limit(limit + 1))).all()
        if len(ids) > limit:
            raise ValueError("cohort bound exceeded; counts unavailable")
        now = await session.scalar(select(func.statement_timestamp()))
        outcomes = []
        for listing_id in ids:
            sources = (await session.execute(select(
                ExternalListingSource.current_status, ExternalListingSource.last_success_at
            ).where(ExternalListingSource.canonical_listing_id == listing_id).limit(129))).all()
            if len(sources) > 128:
                raise ValueError("source bound exceeded; counts unavailable")
            projection = await pipeline._read_current_projection(session, listing_id)
            outcomes.append(classify(plan, projection, checks=tuple(s.last_success_at for s in sources),
                                     source_error=any(s.current_status != "active" for s in sources),
                                     now=now, policy=policy))
        return counters(outcomes)
