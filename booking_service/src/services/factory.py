from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.event_publisher import EventPublisher
from src.clients.provider_client import ProviderClient
from src.core.config import settings
from src.repositories.booking_repository import BookingRepository
from src.repositories.ledger_repository import LedgerRepository
from src.repositories.outbox_repository import OutboxRepository
from src.repositories.provider_callback_repository import ProviderCallbackRepository
from src.services.billing_service import BillingService
from src.services.booking_service import BookingService
from src.services.booking_status_service import BookingStatusService
from src.services.callback_service import CallbackService
from src.services.expiration_service import ExpirationService
from src.services.outbox_service import OutboxService
from src.services.reconciliation_service import ReconciliationService
from src.services.submission_service import SubmissionService


def build_booking_service(session: AsyncSession) -> BookingService:
    return BookingService(
        session,
        BookingRepository(session),
        expire_after=timedelta(seconds=settings.driver_assignment_timeout_seconds),
    )


def build_status_service(session: AsyncSession) -> BookingStatusService:
    return BookingStatusService(
        booking_repository=BookingRepository(session),
        outbox_repository=OutboxRepository(session),
        billing_service=BillingService(LedgerRepository(session), settings.revenue_account),
    )


def build_callback_service(session: AsyncSession) -> CallbackService:
    return CallbackService(
        session,
        callback_repository=ProviderCallbackRepository(session),
        booking_repository=BookingRepository(session),
        status_service=build_status_service(session),
    )


def build_submission_service(session: AsyncSession, provider_client: ProviderClient) -> SubmissionService:
    return SubmissionService(
        session,
        booking_repository=BookingRepository(session),
        status_service=build_status_service(session),
        callback_service=build_callback_service(session),
        provider_client=provider_client,
        max_backoff_seconds=settings.submit_max_backoff_seconds,
    )


def build_expiration_service(session: AsyncSession, provider_client: ProviderClient) -> ExpirationService:
    return ExpirationService(
        session,
        booking_repository=BookingRepository(session),
        status_service=build_status_service(session),
        provider_client=provider_client,
    )


def build_reconciliation_service(session: AsyncSession, provider_client: ProviderClient) -> ReconciliationService:
    return ReconciliationService(
        session,
        booking_repository=BookingRepository(session),
        status_service=build_status_service(session),
        provider_client=provider_client,
        stale_after=timedelta(seconds=settings.reconcile_stale_after_seconds),
    )


def build_outbox_service(session: AsyncSession, publisher: EventPublisher) -> OutboxService:
    return OutboxService(session, OutboxRepository(session), publisher)
