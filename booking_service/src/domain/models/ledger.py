import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, created_at_column


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"))
    account: Mapped[str] = mapped_column(String(128), index=True)
    direction: Mapped[str] = mapped_column(String(6))
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        UniqueConstraint("booking_id", "direction", name="uq_ledger_entry_booking_direction"),
        CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        CheckConstraint("direction IN ('debit', 'credit')", name="ck_ledger_direction"),
    )
