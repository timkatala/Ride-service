import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.provider_client import ProviderClient
from src.domain.exceptions.provider import ProviderError
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository
from src.services.booking_status_service import BookingStatusService

logger = logging.getLogger(__name__)


class ExpirationService:
    def __init__(
        self,
        session: AsyncSession,
        booking_repository: BookingRepository,
        status_service: BookingStatusService,
        provider_client: ProviderClient,
    ):
        self.session = session
        self.booking_repository = booking_repository
        self.status_service = status_service
        self.provider_client = provider_client

    async def expire_overdue_bookings(self, limit: int) -> int:
        """Expire bookings that didn't get a driver in time and cancel their provider orders."""
        async with self.session.begin():
            overdue = await self.booking_repository.lock_overdue(limit)
            for booking in overdue:
                await self.status_service.change_status(booking, BookingStatus.EXPIRED, source="expirer")
            order_ids = [booking.provider_order_id for booking in overdue if booking.provider_order_id]

        for order_id in order_ids:
            try:
                await self.provider_client.cancel_order(order_id)
            except ProviderError as exc:
                logger.warning("could not cancel provider order %s: %s", order_id, exc)
        return len(overdue)
