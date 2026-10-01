import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.event_publisher import EventPublisher
from src.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxService:
    def __init__(self, session: AsyncSession, outbox_repository: OutboxRepository, publisher: EventPublisher):
        self.session = session
        self.outbox_repository = outbox_repository
        self.publisher = publisher

    async def publish_pending(self, limit: int) -> int:
        """Publish one batch of events. SKIP LOCKED lets several workers do this in
        parallel without sending the same row twice (unless one crashes between
        publish and commit: that's the at-least-once window)."""
        published = 0
        async with self.session.begin():
            for event in await self.outbox_repository.lock_unpublished(limit):
                try:
                    await self.publisher.publish(event)
                except Exception:
                    logger.exception("failed to publish outbox event %s", event.event_id)
                    break
                self.outbox_repository.mark_published(event)
                published += 1
        return published
