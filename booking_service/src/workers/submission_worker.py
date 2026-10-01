import asyncio
from datetime import timedelta

from src.clients.provider_client import ProviderClient
from src.services.factory import build_submission_service
from src.services.submission_service import BookingToSubmit
from src.workers.base_worker import PeriodicWorker


class SubmissionWorker(PeriodicWorker):
    name = "submission"

    def __init__(self, session_factory, batch_size: int, provider_client: ProviderClient, lease_seconds: int):
        super().__init__(session_factory, batch_size)
        self.provider_client = provider_client
        self.lease = timedelta(seconds=lease_seconds)

    async def run_once(self) -> int:
        async with self.session_factory() as session:
            service = build_submission_service(session, self.provider_client)
            bookings = await service.take_bookings_to_submit(self.batch_size, self.lease)

        await asyncio.gather(*(self._submit(booking) for booking in bookings))
        return len(bookings)

    async def _submit(self, booking: BookingToSubmit) -> None:
        async with self.session_factory() as session:
            await build_submission_service(session, self.provider_client).submit(booking)
