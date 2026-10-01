from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.services.booking_service import BookingService
from src.services.callback_service import CallbackService
from src.services.factory import build_booking_service, build_callback_service


async def get_booking_service(session: AsyncSession = Depends(get_session)) -> BookingService:
    return build_booking_service(session)


async def get_callback_service(session: AsyncSession = Depends(get_session)) -> CallbackService:
    return build_callback_service(session)
