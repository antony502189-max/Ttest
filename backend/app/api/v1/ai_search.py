"""Disabled-by-default HTTP boundary; application never constructs its runtime."""
import asyncio
import hashlib
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

import sentry_sdk  # type: ignore[import-not-found]
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from ...repositories.ai_search_quota import QuotaError
from ...repositories.ai_search_sessions import SearchSessions, SessionError
from ...repositories.ai_verified_cards import VerifiedCardSearch
from ...schemas.ai_search_intent import SessionCreate
from ...schemas.ai_search_quota import QuotaOperation, QuotaSubject
from ...schemas.listings import ListingCardSearchRequest, ListingMapRequest
from ...services.ai_card_cursors import InvalidAICursor
from ...services.ai_guest_tokens import GuestTokens, InvalidGuestToken
from ...services.ai_http_policy import HTTP_DEADLINE, AIHTTPPolicy
from ...services.ai_search_attempts import AIAttemptRejected
from ...services.ai_search_execution import TextSearchExecution
from ...services.moderation import enforce_full_access
from ..dependencies import bearer, token_user

COOKIE = "ai_search_guest"


class HTTPGate(Protocol):
    # Must be a fail-closed distributed gate with explicit operator budgets;
    # no memory limiter, absent gate or production budget default is supplied.
    async def check(self, key: str) -> None: ...


@dataclass(frozen=True)
class AISearchRuntime:
    sessions: SearchSessions
    cards: VerifiedCardSearch
    execution: TextSearchExecution
    guests: GuestTokens
    http_gate: HTTPGate
    origins: frozenset[str]
    max_body_bytes: int
    policy: AIHTTPPolicy

    def __post_init__(self):
        if not isinstance(self.policy, AIHTTPPolicy):
            raise TypeError("explicit HTTP policy required")
        if type(self.max_body_bytes) is not int or not 1024 <= self.max_body_bytes <= 1_048_576:
            raise ValueError("explicit bounded HTTP body policy required")
        if not self.origins or "*" in self.origins:
            raise ValueError("explicit trusted browser origins required")
        if self.cards.sessions is not self.sessions or self.execution.sessions is not self.sessions:
            raise ValueError("runtime must share one owned-session authority")


async def bounded_handler(request: Request, handler, deadline: float):
    active = await runtime(request)
    if request.method not in {"GET", "HEAD"}:
        length = request.headers.get("content-length")
        if length is not None and (int(length) < 0 or int(length) > active.max_body_bytes):
            raise HTTPException(413, "AI_REQUEST_BODY_TOO_LARGE")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > active.max_body_bytes:
                raise HTTPException(413, "AI_REQUEST_BODY_TOO_LARGE")
            body.extend(chunk)
        request._body = bytes(body)
    result = await handler(request)
    if asyncio.get_running_loop().time() >= deadline:
        raise TimeoutError
    return result


class PrivateAIRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request: Request):
            with sentry_sdk.isolation_scope() as scope:
                scope.set_tag("ai_private", True)
                scope.add_event_processor(lambda event, hint: None)
                try:
                    configured = getattr(request.app.state, "ai_search_runtime", None)
                    if request.url.path == "/api/v1/ai-search/capabilities":
                        result = await handler(request)
                    else:
                        if not isinstance(configured, AISearchRuntime):
                            raise HTTPException(503, "AI_SEARCH_DISABLED")
                        deadline = asyncio.get_running_loop().time() + configured.policy.request_seconds
                        deadline_token = HTTP_DEADLINE.set(deadline)
                        try:
                            async with asyncio.timeout_at(deadline):
                                result = await bounded_handler(request, handler, deadline)
                        finally:
                            HTTP_DEADLINE.reset(deadline_token)
                    result.headers["Cache-Control"] = "no-store"
                    return result
                except RequestValidationError:
                    # Unknown JSON keys can themselves contain private text.
                    # Do not pass their locations to the shared validation logger.
                    return JSONResponse({"detail": "AI_REQUEST_INVALID"}, 422,
                                        headers={"Cache-Control": "no-store"})
                except TimeoutError:
                    # Commit acknowledgement may be lost. Do not release or
                    # infer again here; retry the exact operation to read PG.
                    return JSONResponse({"detail": "AI_REQUEST_TIMEOUT_RETRY_SAME_OPERATION"}, 504,
                                        headers={"Cache-Control": "no-store"})
                except HTTPException as error:
                    error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                    raise
                except InvalidGuestToken:
                    return JSONResponse({"detail": "AI_GUEST_IDENTITY_INVALID_OR_EXPIRED"}, 401, headers={"Cache-Control": "no-store"})
                except SessionError as error:
                    code = error.code if error.code in {"SESSION_NOT_FOUND", "SESSION_EXPIRED", "SESSION_VERSION_CONFLICT",
                        "SESSION_STATE_INVALID", "RESULT_NOT_FOUND", "RESULT_EXPIRED_REQUERY_REQUIRED", "RESULT_STATE_INVALID", "SESSION_LIMIT"} else "AI_SESSION_UNAVAILABLE"
                    return JSONResponse({"detail": code}, 429 if code == "SESSION_LIMIT" else 404 if code in {"SESSION_NOT_FOUND", "RESULT_NOT_FOUND"} else 409,
                                        headers={"Cache-Control": "no-store", **({"Retry-After": str(error.retry_after)} if error.retry_after else {})})
                except QuotaError as error:
                    code = error.code if error.code in {"QUOTA_EXHAUSTED", "IDEMPOTENCY_CONFLICT", "CLAIM_REJECTED", "STALE_WORKER"} else "AI_OPERATION_UNAVAILABLE"
                    return JSONResponse({"detail": code}, 429 if code == "QUOTA_EXHAUSTED" else 409,
                                        headers={"Cache-Control": "no-store", **({"Retry-After": str(error.retry_after)} if error.retry_after > 0 else {})})
                except AIAttemptRejected as error:
                    limited = error.code == "ATTEMPT_LIMIT"
                    return JSONResponse({"detail": "ATTEMPT_LIMIT" if limited else "ABUSE_GATE_UNAVAILABLE"},
                                        429 if limited else 503, headers={"Cache-Control": "no-store",
                                        **({"Retry-After": str(error.retry_after)} if limited and error.retry_after > 0 else {})})
                except InvalidAICursor:
                    return JSONResponse({"detail": "AI_REQUERY_REQUIRED"}, 409, headers={"Cache-Control": "no-store"})
                except ValueError:
                    return JSONResponse({"detail": "AI_REQUEST_INVALID"}, 400, headers={"Cache-Control": "no-store"})
                except Exception:  # noqa: BLE001 - private fixed response, no transcript/SQL/secret logging
                    return JSONResponse({"detail": "AI_SERVICE_UNAVAILABLE"}, 503, headers={"Cache-Control": "no-store"})
        return private


router = APIRouter(prefix="/ai-search", tags=["AI search (disabled by default)"], route_class=PrivateAIRoute)


class APIBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AICardView(APIBody):
    # Semantic constraints live only in the owned typed intent. Never mix
    # legacy manual defaults/booleans into the confirmed AI contract.
    limit: Annotated[int, Field(strict=True, ge=1, le=50)] = 20
    cursor: Annotated[StrictStr, Field(max_length=1024)] | None = None
    sort: Annotated[StrictStr, Field(max_length=64)] = "newest"
    favoriteIds: Annotated[list[UUID], Field(max_length=1000)] = Field(default_factory=list)

    @field_validator("sort")
    @classmethod
    def existing_sort(cls, value: str) -> str:
        ListingCardSearchRequest(sort=value)
        return value

    def to_request(self) -> ListingCardSearchRequest:
        return ListingCardSearchRequest.model_validate(self.model_dump())


class MessageBody(APIBody):
    idempotency_key: UUID
    session_id: UUID
    expected_version: Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
    text: Annotated[StrictStr, Field(min_length=1, max_length=16_384)] = Field(repr=False)
    search: AICardView = Field(default_factory=AICardView)


class VersionBody(APIBody):
    expected_version: Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]


class PageBody(VersionBody):
    search: AICardView = Field(default_factory=AICardView)


async def runtime(request: Request) -> AISearchRuntime:
    value = getattr(request.app.state, "ai_search_runtime", None)
    if not isinstance(value, AISearchRuntime):
        raise HTTPException(503, "AI_SEARCH_DISABLED")
    cached = getattr(request.state, "validated_ai_runtime", None)
    if isinstance(cached, AISearchRuntime) and cached is value:
        return cached
    if request.method not in {"GET", "HEAD"} and (
        request.headers.get("origin") not in value.origins or request.headers.get("x-ai-request") != "1"
    ):
        raise HTTPException(403, "AI_ORIGIN_OR_CSRF_REJECTED")
    address = value.policy.address(request)
    await value.http_gate.check(value.guests.ip_key(address, purpose="ai-http"))
    request.state.validated_ai_runtime = value
    return value


async def subject(request: Request, response: Response, active: AISearchRuntime = Depends(runtime)) -> QuotaSubject:
    if "authorization" in request.headers:
        credentials = await bearer(request)
        async with active.sessions.ledger.sessions() as connection:
            user = await token_user(credentials, connection)
            if user is None:
                # An invalid/blocked bearer never falls back to guest identity.
                raise HTTPException(401, "Authentication required")
            await enforce_full_access(user, connection)
            return QuotaSubject(kind="auth", id=user.id)
    # Strict guest cookies are supported only behind a same-origin UI/API
    # reverse proxy. Cross-origin bearer clients retain explicit CORS support.
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") not in {None, "same-origin"} or (
        origin is not None and origin != str(request.base_url).rstrip("/")
    ):
        raise HTTPException(403, "AI_GUEST_SAME_ORIGIN_REQUIRED")
    token = request.cookies.get(COOKIE)
    if token is not None:
        return active.guests.read(token)
    if request.method != "POST" or request.url.path != "/api/v1/ai-search/sessions":
        raise HTTPException(401, "AI_GUEST_IDENTITY_REQUIRED")
    address = active.policy.address(request)
    await active.http_gate.check(active.guests.ip_key(address, purpose="ai-guest-issue"))
    token, owner = active.guests.issue()
    response.set_cookie(COOKIE, token, max_age=active.guests.policy.ttl_seconds, secure=True,
                        httponly=True, samesite="strict", path="/api/v1/ai-search")
    return owner


@router.get("/capabilities")
async def capabilities(request: Request):
    # Configuration advertisement only, never a dependency-health probe.
    active = isinstance(getattr(request.app.state, "ai_search_runtime", None), AISearchRuntime)
    return {"text": active, "map": active, "voice": False, "saved_searches": False}


@router.post("/sessions")
async def create(payload: SessionCreate | None = None, active: AISearchRuntime = Depends(runtime),
                 owner: QuotaSubject = Depends(subject)):
    await active.http_gate.check(active.guests.ip_key(f"{owner.kind}:{owner.id}", purpose="ai-session-create"))
    return jsonable_encoder(await active.sessions.create(owner, payload,
        max_active=active.policy.max_active_sessions), exclude_none=True)


@router.get("/sessions/{session_id}")
async def get(session_id: UUID, active: AISearchRuntime = Depends(runtime), owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.sessions.get(owner, session_id), exclude_none=True)


@router.post("/sessions/{session_id}/reset")
async def reset(session_id: UUID, payload: VersionBody, active: AISearchRuntime = Depends(runtime),
                owner: QuotaSubject = Depends(subject)):
    await active.http_gate.check(active.guests.ip_key(f"{owner.kind}:{owner.id}", purpose="ai-session-create"))
    return jsonable_encoder(await active.sessions.reset(owner, session_id, payload.expected_version,
                                                       max_active=active.policy.max_active_sessions), exclude_none=True)


@router.post("/sessions/{session_id}/cards")
async def page(session_id: UUID, payload: PageBody, active: AISearchRuntime = Depends(runtime),
               owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.cards.search_owned(owner, session_id, payload.expected_version, payload.search.to_request()))


@router.post("/query")
async def message(payload: MessageBody, active: AISearchRuntime = Depends(runtime), owner: QuotaSubject = Depends(subject)):
    operation = QuotaOperation(idempotency_key=payload.idempotency_key, channel="text",
        payload_sha256=hashlib.sha256(payload.text.encode()).hexdigest(), session_id=payload.session_id,
        expected_session_version=payload.expected_version)
    return jsonable_encoder(await active.execution.execute(owner, operation, payload.text, payload.search.to_request()))


class ResultPageBody(APIBody):
    search: AICardView = Field(default_factory=AICardView)


@router.post("/results/{result_ref}/cards")
async def result_page(result_ref: UUID, payload: ResultPageBody, active: AISearchRuntime = Depends(runtime),
                      owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.cards.query_result(owner, result_ref, payload.search.to_request()))


class MapView(APIBody):
    north: float = Field(ge=-90, le=90)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    west: float = Field(ge=-180, le=180)
    zoom: float = Field(ge=2, le=21)

    def to_request(self) -> ListingMapRequest:
        return ListingMapRequest.model_validate(self.model_dump())


class MapBody(VersionBody):
    search: MapView


class ResultMapBody(APIBody):
    search: MapView


@router.get("/quota")
async def quota(active: AISearchRuntime = Depends(runtime), owner: QuotaSubject = Depends(subject)):
    return await active.sessions.ledger.daily_status(owner)


@router.get("/results/{result_ref}")
async def result_metadata(result_ref: UUID, active: AISearchRuntime = Depends(runtime), owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.sessions.result(owner, result_ref), exclude_none=True)


@router.post("/sessions/{session_id}/map")
async def session_map(session_id: UUID, payload: MapBody, active: AISearchRuntime = Depends(runtime),
                      owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.cards.map_owned(owner, session_id, payload.expected_version, payload.search.to_request()))


@router.post("/results/{result_ref}/map")
async def result_map(result_ref: UUID, payload: ResultMapBody, active: AISearchRuntime = Depends(runtime),
                     owner: QuotaSubject = Depends(subject)):
    return jsonable_encoder(await active.cards.map_result(owner, result_ref, payload.search.to_request()))
