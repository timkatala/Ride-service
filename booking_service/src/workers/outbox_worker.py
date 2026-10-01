from src.clients.event_publisher import EventPublisher
from src.services.factory import build_outbox_service
from src.workers.base_worker import PeriodicWorker


class OutboxWorker(PeriodicWorker):
    name = "outbox"

    def __init__(self, session_factory, batch_size: int, publisher: EventPublisher):
        super().__init__(session_factory, batch_size)
        self.publisher = publisher

    async def run_once(self) -> int:
        async with self.session_factory() as session:
            return await build_outbox_service(session, self.publisher).publish_pending(self.batch_size)
