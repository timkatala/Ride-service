import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s provider: %(message)s")
log = logging.getLogger("provider")

CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8000/provider/callbacks")
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "dev-secret")

SLOW_RATE = 0.3
MAX_DELAY_SECONDS = 5
FAILURE_RATE = 0.2
TIMEOUT_AFTER_CREATE_RATE = 0.1
HANG_SECONDS = 10

STEP_DELAY_SECONDS = (2, 6)
CANCEL_RATE = 0.1
CALLBACK_MAX_DELAY_SECONDS = 8
DUPLICATE_RATE = 0.2


@dataclass
class Order:
    id: str
    status: str = "accepted"


class CreateOrder(BaseModel):
    reference: str
    pickup: str
    dropoff: str


app = FastAPI(title="Mock ride provider")
orders: dict[str, Order] = {}
orders_by_key: dict[str, Order] = {}
background_tasks: set[asyncio.Task] = set()
http = httpx.AsyncClient(timeout=5)


def run_in_background(coro) -> None:
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


def order_json(order: Order) -> dict:
    return {"provider_order_id": order.id, "status": order.status}


@app.post("/provider/orders", status_code=201)
async def create_order(payload: CreateOrder, idempotency_key: str | None = Header(default=None)):
    if random.random() < SLOW_RATE:
        await asyncio.sleep(random.uniform(0, MAX_DELAY_SECONDS))
    if random.random() < FAILURE_RATE:
        return JSONResponse({"error": "temporarily unavailable"}, status_code=503)

    key = idempotency_key or payload.reference
    order = orders_by_key.get(key)
    if order is None:
        order = Order(id=f"prv_{uuid.uuid4().hex[:12]}")
        orders[order.id] = order
        orders_by_key[key] = order
        run_in_background(drive_order(order))
        log.info("new order %s for %s", order.id, payload.reference)

    if random.random() < TIMEOUT_AFTER_CREATE_RATE:
        log.info("order %s created, hanging for %ss", order.id, HANG_SECONDS)
        await asyncio.sleep(HANG_SECONDS)

    return order_json(order)


@app.get("/provider/orders/{order_id}")
async def get_order(order_id: str):
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order_json(order)


@app.post("/provider/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if order.status == "completed":
        raise HTTPException(status_code=409, detail="order is already completed")
    if order.status != "cancelled":
        order.status = "cancelled"
        send_callback(order)
    return order_json(order)


async def drive_order(order: Order) -> None:
    send_callback(order)

    next_statuses = ["driver_assigned", "completed"]
    if random.random() < CANCEL_RATE:
        next_statuses = next_statuses[: random.randint(0, 1)] + ["cancelled"]

    for status in next_statuses:
        await asyncio.sleep(random.uniform(*STEP_DELAY_SECONDS))
        if order.status in ("completed", "cancelled"):
            return
        order.status = status
        send_callback(order)


def send_callback(order: Order) -> None:
    event = {
        "event_id": str(uuid.uuid4()),
        "provider_order_id": order.id,
        "status": order.status,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    copies = 2 if random.random() < DUPLICATE_RATE else 1
    for _ in range(copies):
        run_in_background(deliver(event, delay=random.uniform(0, CALLBACK_MAX_DELAY_SECONDS)))


async def deliver(event: dict, delay: float) -> None:
    await asyncio.sleep(delay)
    body = json.dumps(event).encode()
    signature = hmac.new(CALLBACK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    try:
        response = await http.post(
            CALLBACK_URL,
            content=body,
            headers={"Content-Type": "application/json", "X-Signature": signature},
        )
        log.info("callback %s %s -> %s", event["provider_order_id"], event["status"], response.status_code)
    except httpx.HTTPError as exc:
        log.info("callback %s %s failed: %r", event["provider_order_id"], event["status"], exc)
