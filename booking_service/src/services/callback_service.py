import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.callback_schema import ProviderCallbackRequest
from src.domain.models import Booking, ProviderCallback
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository
from src.repositories.provider_callback_repository import ProviderCallbackRepository
from src.services.booking_status_service import BookingStatusService

logger = logging.getLogger(__name__)

DUPLICATE_EVENT = "duplicate_event"
QUEUED = "queued"


class CallbackService:
    def __init__(
        self,
        session: AsyncSession,
        callback_repository: ProviderCallbackRepository,
        booking_repository: BookingRepository,
        status_service: BookingStatusService,
    ):
        self.session = session
        self.callback_repository = callback_repository
        self.booking_repository = booking_repository
        self.status_service = status_service

    async def handle_callback(self, callback: ProviderCallbackRequest) -> str:
        async with self.session.begin():
            stored = await self.callback_repository.insert_if_new(
                event_id=callback.event_id,
                provider_order_id=callback.provider_order_id,
                status=callback.status,
                occurred_at=callback.occurred_at,
            )
            if stored is None:
                outcome = DUPLICATE_EVENT
            else:
                booking = await self.booking_repository.lock_by_provider_order_id(callback.provider_order_id)
                if booking is None:
                    logger.info(
                        "callback %s for unknown order %s, keeping it for later",
                        callback.event_id,
                        callback.provider_order_id,
                    )
                    outcome = QUEUED
                else:
                    outcome = await self._apply(booking, stored)

        return outcome

    async def replay_queued_callbacks(self, booking: Booking) -> int:
        """Apply callbacks that arrived before we knew the booking's provider_order_id.

        The booking must be locked by the caller, inside the caller's transaction.
        """
        callbacks = await self.callback_repository.lock_unprocessed_for_order(booking.provider_order_id)
        for callback in callbacks:
            await self._apply(booking, callback)
        return len(callbacks)

    async def _apply(self, booking: Booking, callback: ProviderCallback) -> str:
        decision = await self.status_service.change_status(
            booking,
            BookingStatus(callback.status),
            source="provider_callback",
            provider_event_id=callback.event_id,
        )
        self.callback_repository.mark_processed(callback)
        return decision.value
