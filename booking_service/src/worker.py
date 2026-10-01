import asyncio
import logging
import signal

from redis.asyncio import Redis

from src.clients.event_publisher import RedisStreamPublisher
from src.clients.provider_client import ProviderClient
from src.core.config import settings
from src.core.database import async_session, engine
from src.workers.expiration_worker import ExpirationWorker
from src.workers.outbox_worker import OutboxWorker
from src.workers.reconciliation_worker import ReconciliationWorker
from src.workers.submission_worker import SubmissionWorker

logger = logging.getLogger("worker")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    provider_client = ProviderClient(settings.provider_url, settings.provider_timeout_seconds)
    redis = Redis.from_url(settings.redis_url)
    batch = settings.batch_size

    workers = [
        SubmissionWorker(async_session, batch, provider_client, settings.submit_lease_seconds),
        OutboxWorker(async_session, batch, RedisStreamPublisher(redis, settings.events_stream)),
        ExpirationWorker(async_session, batch, provider_client),
        ReconciliationWorker(async_session, batch, provider_client),
    ]

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await asyncio.gather(*(worker.run_forever(stop) for worker in workers))

    logger.info("worker stopping")
    await provider_client.close()
    await redis.aclose()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
