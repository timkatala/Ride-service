import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from src.domain.models import OutboxEvent
from src.repositories.base_repository import BaseRepository


class OutboxRepository(BaseRepository[OutboxEvent]):
    model = OutboxEvent

    def add_event(self, event_type: str, aggregate_id: uuid.UUID, payload: dict) -> OutboxEvent:
        return self.add(
            OutboxEvent(event_id=uuid.uuid4(), event_type=event_type, aggregate_id=aggregate_id, payload=payload)
        )

    async def lock_unpublished(self, limit: int) -> Sequence[OutboxEvent]:
        result = await self.session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return result.all()

    @staticmethod
    def mark_published(event: OutboxEvent) -> None:
        event.published_at = func.now()
