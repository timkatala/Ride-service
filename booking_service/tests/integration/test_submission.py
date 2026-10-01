import asyncio

from sqlalchemy import select, update

from src.domain.exceptions.provider import ProviderError
from src.domain.models import Booking
from tests.helpers import create_booking, send_callback
from tests.integration.jobs import run_submission


async def load(session_factory, booking_id) -> Booking:
    async with session_factory() as session:
        return await session.scalar(select(Booking).where(Booking.id == booking_id))


async def make_due_again(session_factory, booking_id):
    """Skip the backoff delay instead of sleeping in tests."""
    async with session_factory() as session, session.begin():
        await session.execute(update(Booking).where(Booking.id == booking_id).values(next_submit_at=Booking.created_at))


async def test_provider_timeout_after_order_was_created(client, session_factory, provider):
    booking = await create_booking(client)
    provider.timeouts_after_create = 1

    await run_submission(provider)

    stored = await load(session_factory, booking["id"])
    assert stored.status == "pending"
    assert stored.provider_order_id is None
    assert stored.submit_attempts == 1
    assert len(provider.orders) == 1

    await make_due_again(session_factory, booking["id"])
    await run_submission(provider)

    stored = await load(session_factory, booking["id"])
    assert stored.status == "submitted"
    assert stored.provider_order_id == provider.orders[0].provider_order_id
    assert provider.create_calls == 2
    assert len(provider.orders) == 1


async def test_provider_5xx_is_retried(client, session_factory, provider):
    booking = await create_booking(client)
    provider.errors_before_create = [ProviderError("503"), ProviderError("503")]

    for _ in range(3):
        await run_submission(provider)
        await make_due_again(session_factory, booking["id"])

    stored = await load(session_factory, booking["id"])
    assert stored.status == "submitted"
    assert stored.submit_attempts == 3
    assert len(provider.orders) == 1


async def test_backoff_keeps_booking_out_of_next_run(client, session_factory, provider):
    await create_booking(client)
    provider.errors_before_create = [ProviderError("503")]

    await run_submission(provider)
    await run_submission(provider)

    assert provider.create_calls == 1


async def test_concurrent_workers_do_not_submit_the_same_booking(client, session_factory, provider):
    for _ in range(5):
        await create_booking(client)
    provider.latency = 0.2

    await asyncio.gather(*(run_submission(provider) for _ in range(4)))

    assert provider.create_calls == 5
    assert len(provider.orders) == 5


async def test_callback_arriving_before_provider_order_id_is_stored(client, session_factory, provider):
    booking = await create_booking(client)

    async def provider_calls_back_immediately(order):
        response = await send_callback(client, order.provider_order_id, "accepted")
        assert response.json() == {"result": "queued"}

    provider.on_order_created = provider_calls_back_immediately
    await run_submission(provider)

    body = (await client.get(f"/bookings/{booking['id']}")).json()
    assert body["status"] == "accepted"
    assert [h["to_status"] for h in body["history"]] == ["pending", "submitted", "accepted"]
