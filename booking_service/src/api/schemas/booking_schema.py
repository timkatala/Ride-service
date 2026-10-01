import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateBookingRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    pickup: str = Field(min_length=1, max_length=255)
    dropoff: str = Field(min_length=1, max_length=255)
    price_amount: int = Field(gt=0, description="Price in minor units (cents)")
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class StatusHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    source: str
    created_at: datetime


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: str
    pickup: str
    dropoff: str
    price_amount: int
    currency: str
    status: str
    provider_order_id: str | None
    created_at: datetime
    expires_at: datetime


class BookingDetailsResponse(BookingResponse):
    history: list[StatusHistoryItem]
