import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.booking_schema import CreateBookingRequest
from src.domain.exceptions.booking import BookingNotFoundException
from src.domain.models import Booking
from src.domain.state_machine import BookingStatus
from src.repositories.booking_repository import BookingRepository, NewBooking


class BookingService:
    def __init__(self, session: AsyncSession, booking_repository: BookingRepository, expire_after: timedelta):
        self.session = session
        self.booking_repository = booking_repository
        self.expire_after = expire_after

    async def create_booking(self, idempotency_key: str, request: CreateBookingRequest) -> tuple[Booking, bool]:
        """Create a booking or return the one already created with this key.

        Parallel requests are handled by the unique index on idempotency_key: one
        insert wins, the others hit ON CONFLICT DO NOTHING and read the winner's row.
        The provider is called later by the submission worker.
        """
        async with self.session.begin():
            booking_id = await self.booking_repository.insert_if_absent(
                NewBooking(idempotency_key=idempotency_key, **request.model_dump()),
                expires_in=self.expire_after,
            )
            created = booking_id is not None
            if created:
                booking = await self.booking_repository.get_by_id(booking_id)
                self.booking_repository.add_status_change(booking, None, BookingStatus.PENDING, source="api")
            else:
                booking = await self.booking_repository.get_by_idempotency_key(idempotency_key)

        return await self.get_booking(booking.id), created

    async def get_booking(self, booking_id: uuid.UUID) -> Booking:
        booking = await self.booking_repository.get_with_history(booking_id)
        if booking is None:
            raise BookingNotFoundException(f"Booking {booking_id} not found")
        return booking
