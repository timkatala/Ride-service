import asyncio
import uuid

from sqlalchemy import func, select

from src.domain.models import Booking, OutboxEvent
from src.repositories.outbox_repository import OutboxRepository
from tests.integration.jobs import run_outbox
from tests.stubs import StubPublisher


async def add_events(session_factory, booking_id, count):
    async with session_factory() as session, session.begin():
        booking = await session.get(Booking, uuid.UUID(booking_id))
        for _ in range(count):
            OutboxRepository(session).add_event("booking.test", booking.id, {"booking_id": booking_id})


async def unpublished(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        )


async def test_broker_failure_keeps_unsent_events(submitted_booking, session_factory):
    await add_events(session_factory, submitted_booking["id"], 3)
    publisher = StubPublisher(fail_on=1)

    assert await run_outbox(publisher, batch_size=10) == 1
    assert await unpublished(session_factory) == 2

    healthy = StubPublisher()
    assert await run_outbox(healthy, batch_size=10) == 2
    assert await unpublished(session_factory) == 0


async def test_concurrent_relays_publish_each_event_once(submitted_booking, session_factory):
    await add_events(session_factory, submitted_booking["id"], 30)
    publisher = StubPublisher()

    await asyncio.gather(*(run_outbox(publisher, batch_size=5) for _ in range(10)))
    while await run_outbox(publisher, batch_size=5):
        pass

    ids = [e.event_id for e in publisher.published]
    assert len(ids) == 30
    assert len(set(ids)) == 30
