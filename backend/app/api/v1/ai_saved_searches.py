"""Private, registered writes; caller cannot supply criteria or model output."""
import asyncio
from uuid import UUID

import sentry_sdk  # type: ignore[import-not-found]
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field

from ...models import User
from ...repositories.ai_saved_searches import SavedAIError, SavedAISnapshot
from ...repositories.ai_search_sessions import SessionError
from ...schemas.ai_search_quota import QuotaSubject
from ...services.ai_saved_handoff import SavedHandoffError
from ...services.ai_saved_runtime import SavedRuntime
from ..dependencies import current_user


class PrivateSavedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request: Request):
            with sentry_sdk.isolation_scope() as scope:
                scope.add_event_processor(lambda event, hint: None)
                scope.set_tag("ai_private", True)
                try:
                    async with asyncio.timeout(15):
                        body = bytearray()
                        async for chunk in request.stream():
                            if len(body) + len(chunk) > 40000:
                                raise HTTPException(413, "AI_SAVE_BODY_TOO_LARGE")
                            body.extend(chunk)
                        request._body = bytes(body)
                        response = await handler(request)
                        response.headers["Cache-Control"] = "private, no-store"
                        return response
                except RequestValidationError:
                    code, status = "AI_SAVE_REQUEST_INVALID", 422
                except SavedHandoffError:
                    code, status = "AI_SAVE_REFRESH_RESULT", 409
                except SavedAIError as error:
                    allowed = {"SAVED_SEARCH_LIMIT", "SAVED_AI_VERSION_CONFLICT", "SAVED_AI_IDEMPOTENCY_CONFLICT", "SAVED_AI_DELETED", "SAVED_AI_NOT_FOUND"}
                    code, status = str(error) if str(error) in allowed else "AI_SAVE_UNAVAILABLE", 409
                except SessionError:
                    code, status = "AI_SAVE_UNAVAILABLE", 409
                except HTTPException as error:
                    error.headers = {**(error.headers or {}), "Cache-Control": "private, no-store"}
                    raise
                except Exception:  # noqa: BLE001 - fixed private response; no token/SQL/body logging
                    code, status = "AI_SAVE_UNAVAILABLE", 503
                return JSONResponse({"detail": code}, status, headers={"Cache-Control": "private, no-store"})
        return private


router = APIRouter(prefix="/saved-searches/ai", route_class=PrivateSavedRoute)


@router.get("/capabilities")
async def capabilities(request: Request):
    return {"save": isinstance(getattr(request.app.state, "ai_saved_runtime", None), SavedRuntime)}


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    token: str = Field(min_length=1, max_length=32768, repr=False)
    name: str = Field(default="", max_length=120, repr=False)


class ToggleBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int = Field(ge=1)
    enabled: bool


def runtime(request: Request) -> SavedRuntime:
    active = getattr(request.app.state, "ai_saved_runtime", None)
    if not isinstance(active, SavedRuntime):
        raise HTTPException(503, "AI_SAVE_UNAVAILABLE")
    return active


def summary(saved: SavedAISnapshot):
    return {"id": saved.id, "matcher": saved.matcher, "name": saved.name,
        "revision": saved.revision, "enabled": saved.enabled}


@router.post("")
async def save(payload: SaveBody, user: User = Depends(current_user), active: SavedRuntime = Depends(runtime)):
    return summary(await active.repo.save_handoff(QuotaSubject(kind="auth", id=user.id),
        payload.token, active.signer, name=payload.name, notifications=True))


@router.patch("/{search_id}")
async def toggle(search_id: UUID, payload: ToggleBody, user: User = Depends(current_user), active: SavedRuntime = Depends(runtime)):
    return summary(await active.repo.set_enabled(QuotaSubject(kind="auth", id=user.id), search_id, payload.revision, payload.enabled))
