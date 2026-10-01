"""create booking tables

Revision ID: 0001
Revises:
Create Date: 2026-10-01 04:28:44.580268

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("pickup", sa.String(length=255), nullable=False),
        sa.Column("dropoff", sa.String(length=255), nullable=False),
        sa.Column("price_amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("provider_order_id", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submit_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_submit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_order_id"),
    )
    op.create_index("ix_bookings_status_changed", "bookings", ["status", "status_changed_at"], unique=False)
    op.create_index(
        "ix_bookings_to_submit",
        "bookings",
        ["next_submit_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_outbox_unpublished", "outbox", ["id"], unique=False, postgresql_where=sa.text("published_at IS NULL")
    )
    op.create_table(
        "provider_callbacks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("provider_order_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        op.f("ix_provider_callbacks_provider_order_id"), "provider_callbacks", ["provider_order_id"], unique=False
    )
    op.create_index(
        "ix_provider_callbacks_unprocessed",
        "provider_callbacks",
        ["received_at"],
        unique=False,
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_table(
        "booking_status_history",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_booking_status_history_booking_id"), "booking_status_history", ["booking_id"], unique=False
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("account", sa.String(length=128), nullable=False),
        sa.Column("direction", sa.String(length=6), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("direction IN ('debit', 'credit')", name="ck_ledger_direction"),
        sa.CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", "direction", name="uq_ledger_entry_booking_direction"),
    )
    op.create_index(op.f("ix_ledger_entries_account"), "ledger_entries", ["account"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ledger_entries_account"), table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(op.f("ix_booking_status_history_booking_id"), table_name="booking_status_history")
    op.drop_table("booking_status_history")
    op.drop_index(
        "ix_provider_callbacks_unprocessed",
        table_name="provider_callbacks",
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.drop_index(op.f("ix_provider_callbacks_provider_order_id"), table_name="provider_callbacks")
    op.drop_table("provider_callbacks")
    op.drop_index("ix_outbox_unpublished", table_name="outbox", postgresql_where=sa.text("published_at IS NULL"))
    op.drop_table("outbox")
    op.drop_index("ix_bookings_to_submit", table_name="bookings", postgresql_where=sa.text("status = 'pending'"))
    op.drop_index("ix_bookings_status_changed", table_name="bookings")
    op.drop_table("bookings")
