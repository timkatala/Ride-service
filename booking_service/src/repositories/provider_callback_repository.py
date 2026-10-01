from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.domain.models import ProviderCallback
from src.domain.models.base import utcnow
from src.repositories.base_repository import BaseRepository


class ProviderCallbackRepository(BaseRepository[ProviderCallback]):
    model = ProviderCallback

    async def insert_if_new(self, event_id: str, provider_order_id: str, status: str, occurred_at):
        """Store the callback. Returns None if an event with this id was already stored."""
        callback_id = await self.session.scalar(
            insert(ProviderCallback)
            .values(
                event_id=event_id,
                provider_order_id=provider_order_id,
                status=status,
                occurred_at=occurred_at,
            )
            .on_conflict_do_nothing(index_elements=[ProviderCallback.event_id])
            .returning(ProviderCallback.id)
        )
        if callback_id is None:
            return None
        return await self.get_by_id(callback_id)

    async def lock_unprocessed_for_order(self, provider_order_id: str) -> Sequence[ProviderCallback]:
        result = await self.session.scalars(
            select(ProviderCallback)
            .where(
                ProviderCallback.provider_order_id == provider_order_id,
                ProviderCallback.processed_at.is_(None),
            )
            .order_by(ProviderCallback.occurred_at, ProviderCallback.id)
            .with_for_update(skip_locked=True)
        )
        return result.all()

    @staticmethod
    def mark_processed(callback: ProviderCallback) -> None:
        callback.processed_at = utcnow()
