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
    data = {
        "mode": "payment",
        "success_url": f"{route_base}{return_path}?payment=return",
        "cancel_url": f"{route_base}{return_path}?payment=cancelled",
        "client_reference_id": str(order.id),
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": str(order.amount_cents),
        "line_items[0][price_data][product_data][name]": name,
        "line_items[0][quantity]": "1",
        "metadata[order_id]": str(order.id),
    }
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
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Invalid Stripe event") from exc
