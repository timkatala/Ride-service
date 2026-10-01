import logging

from src.domain.models import Booking
from src.domain.models.base import utcnow
from src.domain.state_machine import BookingStatus, Decision, decide
from src.repositories.booking_repository import BookingRepository
from src.repositories.outbox_repository import OutboxRepository
from src.services.billing_service import BillingService

logger = logging.getLogger(__name__)


class BookingStatusService:
    """The single place where a booking changes status.

    Callbacks, the reconciler, the expirer and the submitter all go through
    change_status(), always with the booking row locked, so they can't race.
    """

    def __init__(
        self,
        booking_repository: BookingRepository,
        outbox_repository: OutboxRepository,
        billing_service: BillingService,
    ):
        self.booking_repository = booking_repository
        self.outbox_repository = outbox_repository
        self.billing_service = billing_service

    async def change_status(
        self,
        booking: Booking,
        target: BookingStatus,
        source: str,
        provider_event_id: str | None = None,
    ) -> Decision:
        """Move a *locked* booking to `target` and run the side effects of the new state.

        Runs inside the caller's transaction; the caller commits.
        """
        current = BookingStatus(booking.status)
        decision = decide(current, target)

        if decision != Decision.APPLY:
            level = logging.WARNING if decision == Decision.REJECT else logging.INFO
            logger.log(level, "booking %s: %s -> %s %s (source=%s)", booking.id, current, target, decision, source)
            return decision

        booking.status = target
        booking.status_changed_at = utcnow()
        self.booking_repository.add_status_change(booking, current, target, source, provider_event_id)
        logger.info("booking %s: %s -> %s (source=%s)", booking.id, current, target, source)

        if target == BookingStatus.COMPLETED:
            await self.billing_service.charge_for_ride(booking)
            self._publish(booking, "booking.completed")
        elif target == BookingStatus.EXPIRED:
            self._publish(booking, "booking.expired")
        elif target == BookingStatus.CANCELLED:
            self._publish(booking, "booking.cancelled")

        return decision

    def _publish(self, booking: Booking, event_type: str) -> None:
        self.outbox_repository.add_event(
            event_type,
            booking.id,
            {
                "booking_id": str(booking.id),
                "client_id": booking.client_id,
                "status": booking.status,
                "provider_order_id": booking.provider_order_id,
                "price_amount": booking.price_amount,
                "currency": booking.currency,
            },
        )
