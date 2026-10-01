import uuid

from sqlalchemy.dialects.postgresql import insert

from src.domain.models import LedgerEntry
from src.repositories.base_repository import BaseRepository


class LedgerRepository(BaseRepository[LedgerEntry]):
    model = LedgerEntry

    async def add_entry(self, booking_id: uuid.UUID, account: str, direction: str, amount: int, currency: str) -> bool:
        """Returns False if this booking already has an entry in this direction."""
        entry_id = await self.session.scalar(
            insert(LedgerEntry)
            .values(booking_id=booking_id, account=account, direction=direction, amount=amount, currency=currency)
            .on_conflict_do_nothing(constraint="uq_ledger_entry_booking_direction")
            .returning(LedgerEntry.id)
        )
        return entry_id is not None
