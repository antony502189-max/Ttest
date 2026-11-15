"""Shared explicit housing vocabulary and freshness; no IO or automatic enable."""
from ..repositories.ai_fact_pipeline import FactPipeline
from ..schemas.ai_fact_pipeline import FactQueuePolicy
from ..schemas.ai_listing_facts import FactVocabulary
from .ai_fact_quality import FactQualityPolicy


def housing_pipeline(factory, *, resolver_version: str) -> FactPipeline:
    return FactPipeline(factory, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset({"wifi", "lift", "air_conditioning", "parking"}),
            catalog_other_codes=frozenset(), tenant_group_codes=frozenset({"friends"}),
            municipality_zones=frozenset()),
        resolver_version=resolver_version, operating_policy=FactQualityPolicy(
            price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=86400))
