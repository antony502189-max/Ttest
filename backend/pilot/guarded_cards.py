"""Every private card/map query must see one completely published generation."""

from app.repositories.ai_verified_cards import SourceCoverageUnavailable, VerifiedCardSearch


def install_catalog_guard(app, health):
    from fastapi.responses import JSONResponse

    from pilot.surface import allowed

    def blocked():
        return JSONResponse({"detail": "SOURCE_COVERAGE_UNAVAILABLE"}, 503, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def published_generation(request, call_next):
        needs_catalog = (
            request.method == "POST"
            and allowed(request.method, request.url.path)
            and request.url.path.endswith(("/query", "/voice", "/cards", "/map"))
        )
        token = None
        try:
            if needs_catalog:
                token = health.ticket()
        except (ValueError, OSError, TypeError):
            return blocked()
        response = await call_next(request)
        try:
            if needs_catalog:
                health.unchanged(token)
        except (ValueError, OSError, TypeError):
            return blocked()
        return response


class GuardedCards(VerifiedCardSearch):
    def __init__(self, pipeline, sessions, *, signing_key, health):
        super().__init__(pipeline, sessions, signing_key=signing_key)
        self.health = health

    def ticket(self):
        try:
            return self.health.ticket()
        except (ValueError, TypeError, OSError):
            raise SourceCoverageUnavailable() from None

    def check(self, token):
        if self.ticket() != token:
            raise SourceCoverageUnavailable()

    async def _query_intent(self, *args, **kwargs):
        token = self.ticket()
        result = await super()._query_intent(*args, **kwargs)
        self.check(token)
        return result

    async def _map_intent(self, *args, **kwargs):
        token = self.ticket()
        result = await super()._map_intent(*args, **kwargs)
        self.check(token)
        return result
