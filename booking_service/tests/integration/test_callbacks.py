import asyncio
import uuid

from sqlalchemy import func, select

from src.core import security
from src.core.config import settings
from src.domain.models import BookingStatusHistory
from tests.helpers import callback_body, send_callback


async def get_booking(client, booking_id) -> dict:
    return (await client.get(f"/bookings/{booking_id}")).json()


async def test_rejects_invalid_signature(client, submitted_booking):
    response = await send_callback(client, submitted_booking["provider_order_id"], "accepted", secret="wrong")

    assert response.status_code == 401
    assert (await get_booking(client, submitted_booking["id"]))["status"] == "submitted"


async def test_rejects_missing_signature(client, submitted_booking):
    body = callback_body(submitted_booking["provider_order_id"], "accepted")
    response = await client.post("/provider/callbacks", content=body)
    assert response.status_code == 401


async def test_happy_path(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    for status in ("accepted", "driver_assigned", "completed"):
        response = await send_callback(client, order_id, status)
        assert response.json() == {"result": "applied"}

    booking = await get_booking(client, submitted_booking["id"])
    assert booking["status"] == "completed"
    assert [h["to_status"] for h in booking["history"]] == [
        "pending",
        "submitted",
        "accepted",
        "driver_assigned",
        "completed",
    ]


async def test_same_event_delivered_twice(client, submitted_booking, session_factory):
    order_id = submitted_booking["provider_order_id"]
    event_id = str(uuid.uuid4())

    first = await send_callback(client, order_id, "accepted", event_id=event_id)
    second = await send_callback(client, order_id, "accepted", event_id=event_id)

    assert first.json() == {"result": "applied"}
    assert second.status_code == 200
    assert second.json() == {"result": "duplicate_event"}
    async with session_factory() as session:
        accepted_entries = await session.scalar(
            select(func.count()).select_from(BookingStatusHistory).where(BookingStatusHistory.to_status == "accepted")
        )
    assert accepted_entries == 1


async def test_same_status_with_new_event_id_is_a_noop(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    await send_callback(client, order_id, "accepted")
    response = await send_callback(client, order_id, "accepted")

    assert response.json() == {"result": "duplicate"}
    assert len((await get_booking(client, submitted_booking["id"]))["history"]) == 3


async def test_parallel_duplicates_apply_once(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]
    event_id = str(uuid.uuid4())

    responses = await asyncio.gather(
        *(send_callback(client, order_id, "driver_assigned", event_id=event_id) for _ in range(10))
    )

    results = sorted(r.json()["result"] for r in responses)
    assert results == ["applied"] + ["duplicate_event"] * 9
    history = (await get_booking(client, submitted_booking["id"]))["history"]
    assert [h["to_status"] for h in history].count("driver_assigned") == 1


async def test_out_of_order_callbacks_do_not_move_booking_backwards(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    assert (await send_callback(client, order_id, "driver_assigned")).json() == {"result": "applied"}
    assert (await send_callback(client, order_id, "accepted")).json() == {"result": "stale"}

    booking = await get_booking(client, submitted_booking["id"])
    assert booking["status"] == "driver_assigned"


async def test_completed_before_earlier_statuses(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    await send_callback(client, order_id, "completed")
    late = [await send_callback(client, order_id, s) for s in ("driver_assigned", "accepted")]

    assert [r.json()["result"] for r in late] == ["stale", "stale"]
    assert (await get_booking(client, submitted_booking["id"]))["status"] == "completed"


async def test_late_accepted_after_cancel_is_ignored(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    await send_callback(client, order_id, "cancelled")
    response = await send_callback(client, order_id, "accepted")

    assert response.json() == {"result": "stale"}
    assert (await get_booking(client, submitted_booking["id"]))["status"] == "cancelled"


async def test_conflicting_terminal_state_is_rejected(client, submitted_booking):
    order_id = submitted_booking["provider_order_id"]

    await send_callback(client, order_id, "completed")
    response = await send_callback(client, order_id, "cancelled")

    assert response.status_code == 409
    assert (await get_booking(client, submitted_booking["id"]))["status"] == "completed"


async def test_callback_for_unknown_order_is_kept(client):
    response = await send_callback(client, "prov-does-not-exist", "accepted")

    assert response.status_code == 200
    assert response.json() == {"result": "queued"}


async def test_invalid_payload(client):
    body = callback_body("p1", "teleported")
    response = await client.post(
        "/provider/callbacks",
        content=body,
        headers={"X-Signature": security.sign(settings.callback_secret, body)},
    )
    assert response.status_code == 422
