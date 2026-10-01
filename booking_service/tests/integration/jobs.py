from src.core.database import async_session
from src.workers.expiration_worker import ExpirationWorker
from src.workers.outbox_worker import OutboxWorker
from src.workers.reconciliation_worker import ReconciliationWorker
from src.workers.submission_worker import SubmissionWorker

BATCH_SIZE = 20


async def run_submission(provider) -> int:
    return await SubmissionWorker(async_session, BATCH_SIZE, provider, lease_seconds=30).run_once()


async def run_expiration(provider) -> int:
    return await ExpirationWorker(async_session, BATCH_SIZE, provider).run_once()


async def run_reconciliation(provider) -> int:
    return await ReconciliationWorker(async_session, BATCH_SIZE, provider).run_once()


async def run_outbox(publisher, batch_size: int = BATCH_SIZE) -> int:
    return await OutboxWorker(async_session, batch_size, publisher).run_once()
