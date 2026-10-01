import asyncio
import uuid

from sqlalchemy import func, select

from src.domain.models import Booking, BookingStatusHistory
from tests.helpers import BOOKING_REQUEST, create_booking


async def count(session_factory, model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_parallel_requests_with_same_key_create_one_booking(client, session_factory):
    key = str(uuid.uuid4())

    responses = await asyncio.gather(
        *(client.post("/bookings", json=BOOKING_REQUEST, headers={"Idempotency-Key": key}) for _ in range(30))
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [200] * 29 + [201]
    assert len({r.json()["id"] for r in responses}) == 1
    assert await count(session_factory, Booking) == 1
    assert await count(session_factory, BookingStatusHistory) == 1


async def test_retry_with_same_key_returns_original_booking(client):
    key = str(uuid.uuid4())
    first = await create_booking(client, key=key)

    retry = await client.post("/bookings", json=BOOKING_REQUEST, headers={"Idempotency-Key": key})

    assert retry.status_code == 200
    assert retry.json()["id"] == first["id"]


async def test_idempotency_key_is_required(client):
    response = await client.post("/bookings", json=BOOKING_REQUEST)
    assert response.status_code == 422


async def test_new_booking_is_pending_and_provider_is_not_called_inline(client, provider):
    booking = await create_booking(client)

    assert booking["status"] == "pending"
    assert booking["provider_order_id"] is None
    assert provider.create_calls == 0


async def test_get_booking_returns_status_history(client, submitted_booking):
    response = await client.get(f"/bookings/{submitted_booking['id']}")

    assert response.status_code == 200
    history = [(h["from_status"], h["to_status"]) for h in response.json()["history"]]
    assert history == [(None, "pending"), ("pending", "submitted")]


async def test_get_unknown_booking_returns_404(client):
    response = await client.get(f"/bookings/{uuid.uuid4()}")
    assert response.status_code == 404
