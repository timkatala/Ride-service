import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Row, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from src.domain.models import Booking, BookingStatusHistory
from src.domain.state_machine import IN_FLIGHT, WAITING_FOR_DRIVER, BookingStatus
from src.repositories.base_repository import BaseRepository


@dataclass
class NewBooking:
    idempotency_key: str
    client_id: str
    pickup: str
    dropoff: str
    price_amount: int
    currency: str


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    async def insert_if_absent(self, booking: NewBooking, expires_in: timedelta) -> uuid.UUID | None:
        """Insert a new pending booking. Returns None if the idempotency key is taken."""
        return await self.session.scalar(
            insert(Booking)
            .values(
                id=uuid.uuid4(),
                status=BookingStatus.PENDING,
                next_submit_at=func.now(),
                expires_at=func.now() + expires_in,
                **booking.__dict__,
            )
            .on_conflict_do_nothing(index_elements=[Booking.idempotency_key])
            .returning(Booking.id)
        )

    async def get_by_idempotency_key(self, idempotency_key: str) -> Booking | None:
        return await self.session.scalar(select(Booking).where(Booking.idempotency_key == idempotency_key))

    async def get_with_history(self, booking_id: uuid.UUID) -> Booking | None:
        return await self.session.scalar(
            select(Booking)
            .where(Booking.id == booking_id)
            .options(selectinload(Booking.history))
            .execution_options(populate_existing=True)
        )

    async def lock_by_id(self, booking_id: uuid.UUID) -> Booking | None:
        return await self.session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())

    async def lock_by_provider_order_id(self, provider_order_id: str) -> Booking | None:
        return await self.session.scalar(
            select(Booking).where(Booking.provider_order_id == provider_order_id).with_for_update()
        )

    def add_status_change(
        self,
        booking: Booking,
        from_status: str | None,
        to_status: str,
        source: str,
        provider_event_id: str | None = None,
    ) -> None:
        self.session.add(
            BookingStatusHistory(
                booking_id=booking.id,
                from_status=from_status,
                to_status=to_status,
                source=source,
                provider_event_id=provider_event_id,
            )
        )

    async def take_bookings_to_submit(self, limit: int, lease: timedelta) -> Sequence[Row]:
        """Pick due pending bookings and push next_submit_at forward, so no other
        worker takes them while we are calling the provider."""
        due = (
            select(Booking.id)
            .where(Booking.status == BookingStatus.PENDING, Booking.next_submit_at <= func.now())
            .order_by(Booking.next_submit_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(
            update(Booking)
            .where(Booking.id.in_(due.scalar_subquery()))
            .values(next_submit_at=func.now() + lease, submit_attempts=Booking.submit_attempts + 1)
            .returning(Booking.id, Booking.pickup, Booking.dropoff, Booking.submit_attempts)
            .execution_options(synchronize_session=False)
        )
        return result.all()

    async def schedule_submit_retry(self, booking_id: uuid.UUID, delay: timedelta) -> None:
        await self.session.execute(
            update(Booking)
            .where(Booking.id == booking_id, Booking.status == BookingStatus.PENDING)
            .values(next_submit_at=func.now() + delay)
        )

    async def lock_overdue(self, limit: int) -> Sequence[Booking]:
        result = await self.session.scalars(
            select(Booking)
            .where(Booking.status.in_(WAITING_FOR_DRIVER), Booking.expires_at <= func.now())
            .order_by(Booking.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return result.all()

    @staticmethod
    def _stuck_filter(stale_after: timedelta):
        return Booking.status.in_(IN_FLIGHT), Booking.status_changed_at < func.now() - stale_after

    async def lock_next_stuck(self, stale_after: timedelta, skip_ids: list[uuid.UUID]) -> Booking | None:
        return await self.session.scalar(
            select(Booking)
            .where(*self._stuck_filter(stale_after), Booking.id.not_in(skip_ids))
            .order_by(Booking.status_changed_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
