import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.provider_client import ProviderClient
from src.domain.exceptions.provider import ProviderError
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository
from src.services.booking_status_service import BookingStatusService

logger = logging.getLogger(__name__)


class ReconciliationService:
    def __init__(
        self,
        session: AsyncSession,
        booking_repository: BookingRepository,
        status_service: BookingStatusService,
        provider_client: ProviderClient,
        stale_after: timedelta,
    ):
        self.session = session
        self.booking_repository = booking_repository
        self.status_service = status_service
        self.provider_client = provider_client
        self.stale_after = stale_after

    async def reconcile_stuck_bookings(self, limit: int) -> int:
        """Ask the provider about bookings that got no status update for too long.

        Each booking is handled in its own transaction and stays locked while we
        wait for the provider, so another worker instance skips it.
        """
        checked = []
        for _ in range(limit):
            async with self.session.begin():
                booking = await self.booking_repository.lock_next_stuck(self.stale_after, skip_ids=checked)
                if booking is None:
                    break
                checked.append(booking.id)
                try:
                    order = await self.provider_client.get_order(booking.provider_order_id)
                except ProviderError as exc:
                    logger.warning("could not reconcile booking %s: %s", booking.id, exc)
                    continue
                await self.status_service.change_status(booking, BookingStatus(order.status), source="reconciler")
        return len(checked)
