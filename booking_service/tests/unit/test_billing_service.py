import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models import Booking
from src.services.billing_service import BillingService


@pytest.fixture
def ledger_repository():
    repository = MagicMock()
    repository.add_entry = AsyncMock(return_value=True)
    return repository


@pytest.fixture
def booking():
    return Booking(id=uuid.uuid4(), client_id="client-1", price_amount=4500, currency="EUR")


async def test_charge_writes_debit_and_credit(ledger_repository, booking):
    service = BillingService(ledger_repository, revenue_account="revenue:rides")

    assert await service.charge_for_ride(booking) is True

    entries = [c.args for c in ledger_repository.add_entry.call_args_list]
    assert entries == [
        (booking.id, "client:client-1", "debit", 4500, "EUR"),
        (booking.id, "revenue:rides", "credit", 4500, "EUR"),
    ]


async def test_second_charge_is_skipped(ledger_repository, booking):
    ledger_repository.add_entry.return_value = False
    service = BillingService(ledger_repository, revenue_account="revenue:rides")

    assert await service.charge_for_ride(booking) is False
    ledger_repository.add_entry.assert_awaited_once()
