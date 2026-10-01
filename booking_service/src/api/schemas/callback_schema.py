from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProviderStatus = Literal["accepted", "driver_assigned", "completed", "cancelled"]


class ProviderCallbackRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    provider_order_id: str = Field(min_length=1, max_length=64)
    status: ProviderStatus
    occurred_at: datetime
