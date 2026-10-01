import asyncio
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update

from src.domain.models import Booking, LedgerEntry, OutboxEvent
from tests.helpers import create_booking, send_callback
from tests.integration.jobs import run_expiration, run_reconciliation, run_submission


async def shift_time(session_factory, booking_id, **columns_to_move_back):
    """Pretend some time has passed by moving timestamps into the past."""
    values = {
        column: getattr(Booking, column) - timedelta(seconds=seconds)
        for column, seconds in columns_to_move_back.items()
    }
    async with session_factory() as session, session.begin():
        await session.execute(update(Booking).where(Booking.id == uuid.UUID(booking_id)).values(**values))


async def load(session_factory, booking_id) -> Booking:
    async with session_factory() as session:
        return await session.get(Booking, uuid.UUID(booking_id))


async def events_of_type(session_factory, event_type) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == event_type)
        )


async def test_booking_without_driver_expires_and_provider_order_is_cancelled(
    client, submitted_booking, session_factory, provider
):
    await send_callback(client, submitted_booking["provider_order_id"], "accepted")
    await shift_time(session_factory, submitted_booking["id"], expires_at=601)

    assert await run_expiration(provider) == 1

    booking = await load(session_factory, submitted_booking["id"])
    assert booking.status == "expired"
    assert await events_of_type(session_factory, "booking.expired") == 1
    assert provider.cancelled == [submitted_booking["provider_order_id"]]

    response = await send_callback(client, submitted_booking["provider_order_id"], "cancelled")
    assert response.json() == {"result": "stale"}


async def test_booking_with_driver_does_not_expire(client, submitted_booking, session_factory, provider):
    await send_callback(client, submitted_booking["provider_order_id"], "driver_assigned")
    await shift_time(session_factory, submitted_booking["id"], expires_at=601)

    assert await run_expiration(provider) == 0
    assert (await load(session_factory, submitted_booking["id"])).status == "driver_assigned"


async def test_parallel_expirers_expire_booking_once(submitted_booking, session_factory, provider):
    await shift_time(session_factory, submitted_booking["id"], expires_at=601)

    results = await asyncio.gather(*(run_expiration(provider) for _ in range(5)))

    assert sum(results) == 1
    assert await events_of_type(session_factory, "booking.expired") == 1


async def test_expired_pending_booking_is_not_submitted(client, session_factory, provider):
    booking = await create_booking(client)
    await shift_time(session_factory, booking["id"], expires_at=601)
    await run_expiration(provider)

    await run_submission(provider)

    assert provider.create_calls == 0


async def test_reconciler_completes_booking_whose_callbacks_were_lost(submitted_booking, session_factory, provider):
    provider.order(submitted_booking["provider_order_id"]).status = "completed"
    await shift_time(session_factory, submitted_booking["id"], status_changed_at=121)

    assert await run_reconciliation(provider) == 1

    assert (await load(session_factory, submitted_booking["id"])).status == "completed"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LedgerEntry)) == 2
    assert await events_of_type(session_factory, "booking.completed") == 1


async def test_reconciler_skips_recently_updated_bookings(submitted_booking, session_factory, provider):
    provider.order(submitted_booking["provider_order_id"]).status = "completed"

    assert await run_reconciliation(provider) == 0
    assert (await load(session_factory, submitted_booking["id"])).status == "submitted"
