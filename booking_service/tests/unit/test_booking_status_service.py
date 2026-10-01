import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models import Booking
from src.domain.state_machine import BookingStatus, Decision
from src.services.booking_status_service import BookingStatusService


def make_booking(status: BookingStatus, **kwargs) -> Booking:
    defaults = dict(
        id=uuid.uuid4(),
        client_id="client-1",
        price_amount=1000,
        currency="EUR",
        provider_order_id="prv_1",
        submit_attempts=1,
    )
    return Booking(status=status, **{**defaults, **kwargs})


@pytest.fixture
def service():
    billing_service = MagicMock()
    billing_service.charge_for_ride = AsyncMock(return_value=True)
    return BookingStatusService(
        booking_repository=MagicMock(),
        outbox_repository=MagicMock(),
        billing_service=billing_service,
    )


def published_events(service) -> list[str]:
    return [c.args[0] for c in service.outbox_repository.add_event.call_args_list]


async def test_completed_charges_and_publishes_event(service):
    booking = make_booking(BookingStatus.DRIVER_ASSIGNED)

    decision = await service.change_status(booking, BookingStatus.COMPLETED, source="test")

    assert decision == Decision.APPLY
    assert booking.status == BookingStatus.COMPLETED
    service.billing_service.charge_for_ride.assert_awaited_once_with(booking)
    assert published_events(service) == ["booking.completed"]
    service.booking_repository.add_status_change.assert_called_once_with(
        booking, BookingStatus.DRIVER_ASSIGNED, BookingStatus.COMPLETED, "test", None
    )


async def test_duplicate_has_no_side_effects(service):
    booking = make_booking(BookingStatus.COMPLETED)

    decision = await service.change_status(booking, BookingStatus.COMPLETED, source="test")

    assert decision == Decision.DUPLICATE
    service.billing_service.charge_for_ride.assert_not_awaited()
    service.outbox_repository.add_event.assert_not_called()
    service.booking_repository.add_status_change.assert_not_called()


async def test_expired_publishes_event(service):
    booking = make_booking(BookingStatus.ACCEPTED)

    await service.change_status(booking, BookingStatus.EXPIRED, source="expirer")

    assert booking.status == BookingStatus.EXPIRED
    assert published_events(service) == ["booking.expired"]
