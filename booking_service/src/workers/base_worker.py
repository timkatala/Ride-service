import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class PeriodicWorker:
    """Runs `run_once` in a loop.

    Every worker can run in several processes at the same time: rows are locked
    with FOR UPDATE SKIP LOCKED (and a lease), so no booking is processed twice.
    """

    name: str = "worker"
    interval_seconds: float = 1.0

    def __init__(self, session_factory: async_sessionmaker, batch_size: int):
        self.session_factory = session_factory
        self.batch_size = batch_size

    async def run_once(self) -> int:
        """Process one batch, return how many items were handled."""
        raise NotImplementedError

    async def run_forever(self, stop: asyncio.Event) -> None:
        logger.info("%s started", self.name)
        while not stop.is_set():
            try:
                processed = await self.run_once()
            except Exception:
                logger.exception("%s failed", self.name)
                processed = 0
            if processed >= self.batch_size:
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                pass
