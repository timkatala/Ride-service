import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from src.api.dependencies import get_booking_service
from src.api.schemas.booking_schema import BookingDetailsResponse, BookingResponse, CreateBookingRequest
from src.domain.exceptions.booking import BookingNotFoundException
from src.services.booking_service import BookingService

booking_router = APIRouter(prefix="/bookings", tags=["bookings"])


@booking_router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: CreateBookingRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=255),
    service: BookingService = Depends(get_booking_service),
):
    booking, created = await service.create_booking(idempotency_key, request)
    if not created:
        response.status_code = status.HTTP_200_OK
    return booking


@booking_router.get("/{booking_id}", response_model=BookingDetailsResponse)
async def get_booking(booking_id: uuid.UUID, service: BookingService = Depends(get_booking_service)):
    try:
        return await service.get_booking(booking_id)
    except BookingNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
