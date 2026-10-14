"""Small hosted-Checkout integration; card details never reach this server."""

import hashlib
import hmac
import json
import time

import httpx
from fastapi import HTTPException

from ..core.config import get_settings
from ..models.payment_order import PaymentOrder


async def create_stripe_session(order: PaymentOrder, name: str, return_path: str) -> tuple[str, str]:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(503, "Stripe is not configured")
    # The SPA uses HashRouter, so Stripe must return to a route in the fragment.
    base = settings.frontend_app_url.rstrip("/")
    route_base = f"{base}/#"
    separator = "&" if "?" in return_path else "?"
    data = {
        "mode": "payment",
        "success_url": f"{route_base}{return_path}{separator}payment=return",
        "cancel_url": f"{route_base}{return_path}{separator}payment=cancelled",
        "client_reference_id": str(order.id),
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": str(order.amount_cents),
        "line_items[0][price_data][product_data][name]": name,
        "line_items[0][quantity]": "1",
        "metadata[order_id]": str(order.id),
    }
    if getattr(order, "kind", None) in {"advertisement", "homepage_hero"}:
        # Only immediate card payments can reserve this scarce inventory.
        data["allowed_payment_method_types[0]"] = "card"
        data["expires_at"] = str(int(time.time()) + 31 * 60)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                headers={
                    "Authorization": f"Bearer {settings.stripe_secret_key}",
                    "Idempotency-Key": str(order.id),
                },
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("id") or not payload.get("url"):
            raise ValueError("Stripe did not return a hosted Checkout URL")
        return payload["id"], payload["url"]
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Could not start Stripe Checkout") from exc


async def retrieve_stripe_session(session_id: str) -> dict:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
                headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
            )
        response.raise_for_status()
        payload = response.json()
        if (not isinstance(payload, dict) or payload.get("id") != session_id
                or payload.get("status") not in {"open", "complete", "expired"}):
            raise ValueError("Invalid Stripe Checkout session")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Could not verify Stripe Checkout") from exc


async def expire_stripe_session(session_id: str) -> dict:
    """Release inventory only when the provider confirms the session is closed."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(f"https://api.stripe.com/v1/checkout/sessions/{session_id}/expire",
                                         headers={"Authorization": f"Bearer {settings.stripe_secret_key}",
                                                  "Idempotency-Key": f"expire:{session_id}"})
        if response.status_code == 400:
            # Payment may have completed concurrently with the cancellation.
            return await retrieve_stripe_session(session_id)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("id") != session_id or payload.get("status") != "expired":
            raise ValueError("Stripe did not confirm expiry")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Could not cancel Stripe Checkout") from exc


def verified_stripe_event(body: bytes, signature: str) -> dict:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise HTTPException(503, "Stripe webhook is not configured")
    values: dict[str, list[str]] = {}
    for item in signature.split(","):
        key, _, value = item.strip().partition("=")
        values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(400, "Invalid Stripe signature") from exc
    if abs(time.time() - timestamp) > 300:
        raise HTTPException(400, "Expired Stripe signature")
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(digest, value) for value in values.get("v1", [])):
        raise HTTPException(400, "Invalid Stripe signature")
    try:
        event = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Invalid Stripe event") from exc
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise HTTPException(400, "Invalid Stripe event")
    return event
