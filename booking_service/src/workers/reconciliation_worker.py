from src.clients.provider_client import ProviderClient
from src.services.factory import build_reconciliation_service
from src.workers.base_worker import PeriodicWorker


class ReconciliationWorker(PeriodicWorker):
    name = "reconciliation"
    interval_seconds = 10

    def __init__(self, session_factory, batch_size: int, provider_client: ProviderClient):
        super().__init__(session_factory, batch_size)
        self.provider_client = provider_client

    async def run_once(self) -> int:
        async with self.session_factory() as session:
            service = build_reconciliation_service(session, self.provider_client)
            return await service.reconcile_stuck_bookings(self.batch_size)
