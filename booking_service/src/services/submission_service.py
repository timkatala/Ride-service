import logging
import random
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.provider_client import ProviderClient
from src.domain.exceptions.provider import ProviderError, ProviderTimeoutError
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository
from src.services.booking_status_service import BookingStatusService
from src.services.callback_service import CallbackService

logger = logging.getLogger(__name__)


@dataclass
class BookingToSubmit:
    id: uuid.UUID
    pickup: str
    dropoff: str
    attempt: int


class SubmissionService:
    def __init__(
        self,
        session: AsyncSession,
        booking_repository: BookingRepository,
        status_service: BookingStatusService,
        callback_service: CallbackService,
        provider_client: ProviderClient,
        max_backoff_seconds: int,
    ):
        self.session = session
        self.booking_repository = booking_repository
        self.status_service = status_service
        self.callback_service = callback_service
        self.provider_client = provider_client
        self.max_backoff_seconds = max_backoff_seconds

    async def take_bookings_to_submit(self, limit: int, lease: timedelta) -> list[BookingToSubmit]:
        async with self.session.begin():
            rows = await self.booking_repository.take_bookings_to_submit(limit, lease)
        return [BookingToSubmit(*row) for row in rows]

    async def submit(self, booking: BookingToSubmit) -> None:
        try:
            order = await self.provider_client.create_order(str(booking.id), booking.pickup, booking.dropoff)
        except ProviderTimeoutError:
            logger.warning("create order for booking %s timed out, outcome unknown", booking.id)
            await self._schedule_retry(booking)
        except ProviderError as exc:
            logger.warning("create order for booking %s failed: %s", booking.id, exc)
            await self._schedule_retry(booking)
        else:
            await self.save_provider_order(booking.id, order.provider_order_id)

    async def save_provider_order(self, booking_id: uuid.UUID, provider_order_id: str) -> None:
        async with self.session.begin():
            booking = await self.booking_repository.lock_by_id(booking_id)

            if booking.provider_order_id is None:
                booking.provider_order_id = provider_order_id
            elif booking.provider_order_id != provider_order_id:
                logger.error(
                    "booking %s already has provider order %s, got %s",
                    booking_id,
                    booking.provider_order_id,
                    provider_order_id,
                )
                return

            booking.next_submit_at = None
            if booking.status == BookingStatus.PENDING:
                await self.status_service.change_status(booking, BookingStatus.SUBMITTED, source="submitter")

            await self.callback_service.replay_queued_callbacks(booking)

    async def _schedule_retry(self, booking: BookingToSubmit) -> None:
        delay = min(2**booking.attempt, self.max_backoff_seconds) * random.uniform(0.5, 1.0)
        async with self.session.begin():
            await self.booking_repository.schedule_submit_retry(booking.id, timedelta(seconds=delay))
        logger.info("booking %s: retry #%d in %.1fs", booking.id, booking.attempt + 1, delay)
