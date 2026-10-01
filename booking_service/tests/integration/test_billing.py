import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from src.domain.models import Booking, LedgerEntry, OutboxEvent
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository
from src.services.factory import build_status_service
from tests.helpers import send_callback
from tests.integration.jobs import run_outbox
from tests.stubs import StubPublisher


async def ledger_state(session_factory):
    async with session_factory() as session:
        entries = (await session.scalars(select(LedgerEntry).order_by(LedgerEntry.id))).all()
        completed_events = await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == "booking.completed")
        )
    return entries, completed_events


async def test_completed_arriving_several_times_charges_once(client, submitted_booking, session_factory):
    order_id = submitted_booking["provider_order_id"]
    duplicated_event = str(uuid.uuid4())

    await asyncio.gather(
        *(send_callback(client, order_id, "completed", event_id=duplicated_event) for _ in range(5)),
        *(send_callback(client, order_id, "completed") for _ in range(5)),
    )
    await send_callback(client, order_id, "completed")

    entries, completed_events = await ledger_state(session_factory)
    assert completed_events == 1

    assert [(e.account, e.direction, e.amount) for e in entries] == [
        ("client:client-42", "debit", 4500),
        ("revenue:rides", "credit", 4500),
    ]


async def test_ledger_constraint_blocks_second_charge(client, submitted_booking, session_factory):
    """Even if application logic were bypassed, the DB won't accept a second charge."""
    async with session_factory() as session, session.begin():
        booking = await session.get(Booking, uuid.UUID(submitted_booking["id"]))
        billing_service = build_status_service(session).billing_service
        assert await billing_service.charge_for_ride(booking) is True
        assert await billing_service.charge_for_ride(booking) is False

    entries, _ = await ledger_state(session_factory)
    assert len(entries) == 2


async def test_rolled_back_transaction_leaves_no_charge_and_no_event(submitted_booking, session_factory):
    with pytest.raises(RuntimeError):
        async with session_factory() as session, session.begin():
            booking = await BookingRepository(session).lock_by_id(uuid.UUID(submitted_booking["id"]))
            await build_status_service(session).change_status(booking, BookingStatus.COMPLETED, source="test")
            await session.flush()
            raise RuntimeError("crash before commit")

    entries, completed_events = await ledger_state(session_factory)
    assert entries == []
    assert completed_events == 0


async def test_completed_event_is_published_by_relay(client, submitted_booking, session_factory):
    await send_callback(client, submitted_booking["provider_order_id"], "completed")
    publisher = StubPublisher()

    assert await run_outbox(publisher, batch_size=10) == 1
    assert await run_outbox(publisher, batch_size=10) == 0

    [event] = publisher.published
    assert event.event_type == "booking.completed"
    assert event.payload["booking_id"] == submitted_booking["id"]
    assert event.payload["status"] == "completed"
