"""Read-only standing eligibility before paid IO, independent of user budget."""
from uuid import UUID

from sqlalchemy import select, text

from app.repositories.ai_verified_cards import verified_intent_predicate
from app.repositories.listings import visible_query
from app.schemas.ai_search_intent import SearchIntent


def readiness_query(pipeline):
    intent = SearchIntent.model_validate_json('{"schema_version":"ai-search.v1","taxonomy_version":"rental.v1",'
        '"session_id":"' + str(UUID(int=1)) + '","version":0,"criteria":{"rental_mode":{"strength":"hard","value":"long"},'
        '"budget":{"strength":"hard","value":{"amount":"1000","currency":"EUR","period":"monthly"}}}}')
    return select(visible_query().where(verified_intent_predicate(pipeline, intent)).exists())


class CatalogReadiness:
    def __init__(self, pipeline, health=None):
        self.pipeline, self.health = pipeline, health

    async def __call__(self):
        try:
            token=self.health.ticket() if self.health is not None else None
        except (ValueError,TypeError,OSError):
            return {'catalog_ready':False,'catalog_reason':'PILOT_CATALOG_REFRESH_UNAVAILABLE'}
        async with self.pipeline.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            ready = bool(await session.scalar(readiness_query(self.pipeline)))
        if self.health is not None:
            try:self.health.unchanged(token)
            except (ValueError,TypeError,OSError):ready=False
        return {"catalog_ready": ready, "catalog_reason": None if ready else "PILOT_CATALOG_STALE"}
