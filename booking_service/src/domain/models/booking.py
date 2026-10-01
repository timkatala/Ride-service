import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base, created_at_column, utcnow


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)

    client_id: Mapped[str] = mapped_column(String(64))
    pickup: Mapped[str] = mapped_column(String(255))
    dropoff: Mapped[str] = mapped_column(String(255))
    price_amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))

    status: Mapped[str] = mapped_column(String(32))
    status_changed_at: Mapped[datetime] = created_at_column()
    provider_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    submit_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_submit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utcnow)

    history: Mapped[list["BookingStatusHistory"]] = relationship(order_by="BookingStatusHistory.id", lazy="raise")

    __table_args__ = (
        Index("ix_bookings_to_submit", "next_submit_at", postgresql_where=text("status = 'pending'")),
        Index("ix_bookings_status_changed", "status", "status_changed_at"),
    )


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))
    provider_event_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_column()
