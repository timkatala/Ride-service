import json
import uuid
from datetime import UTC, datetime

from src.core import security
from src.core.config import settings

BOOKING_REQUEST = {
    "client_id": "client-42",
    "pickup": "LHR Terminal 5",
    "dropoff": "10 Downing St",
    "price_amount": 4500,
    "currency": "GBP",
}


async def create_booking(client, key: str | None = None, **overrides) -> dict:
    response = await client.post(
        "/bookings",
        json={**BOOKING_REQUEST, **overrides},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


def callback_body(provider_order_id: str, status: str, event_id: str | None = None) -> bytes:
    return json.dumps(
        {
            "event_id": event_id or str(uuid.uuid4()),
            "provider_order_id": provider_order_id,
            "status": status,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
    ).encode()


async def send_callback(client, provider_order_id: str, status: str, event_id: str | None = None, *, secret=None):
    body = callback_body(provider_order_id, status, event_id)
    signature = security.sign(secret or settings.callback_secret, body)
    return await client.post(
        "/provider/callbacks",
        content=body,
        headers={"X-Signature": signature, "Content-Type": "application/json"},
    )
