import logging

from src.domain.models import Booking
from src.repositories.ledger_repository import LedgerRepository

logger = logging.getLogger(__name__)


def client_account(client_id: str) -> str:
    return f"client:{client_id}"


class BillingService:
    def __init__(self, ledger_repository: LedgerRepository, revenue_account: str):
        self.ledger_repository = ledger_repository
        self.revenue_account = revenue_account

    async def charge_for_ride(self, booking: Booking) -> bool:
        """Write the double-entry charge for a completed ride.

        Returns False if this booking was already charged. The unique constraint on
        (booking_id, direction) makes this safe even if two transactions both decide
        to charge the same booking.
        """
        amount, currency = booking.price_amount, booking.currency

        debited = await self.ledger_repository.add_entry(
            booking.id, client_account(booking.client_id), "debit", amount, currency
        )
        if not debited:
            logger.warning("booking %s is already charged, skipping", booking.id)
            return False

        await self.ledger_repository.add_entry(booking.id, self.revenue_account, "credit", amount, currency)
        return True
