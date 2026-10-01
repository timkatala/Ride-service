from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from src.api.dependencies import get_callback_service
from src.api.schemas.callback_schema import ProviderCallbackRequest
from src.core.config import settings
from src.core.security import is_valid_signature
from src.domain.state_machine import Decision
from src.services.callback_service import CallbackService

callback_router = APIRouter(prefix="/provider", tags=["provider"])


@callback_router.post("/callbacks")
async def receive_callback(request: Request, service: CallbackService = Depends(get_callback_service)):
    body = await request.body()
    if not is_valid_signature(settings.callback_secret, body, request.headers.get("X-Signature")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        callback = ProviderCallbackRequest.model_validate_json(body)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=e.errors(include_url=False)
        ) from None

    outcome = await service.handle_callback(callback)

    if outcome == Decision.REJECT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transition to '{callback.status}' is not allowed for this booking",
        )
    return {"result": outcome}
