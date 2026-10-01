import logging

from fastapi import FastAPI

from src.api.booking_router import booking_router
from src.api.callback_router import callback_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Ride booking service")
app.include_router(booking_router)
app.include_router(callback_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
