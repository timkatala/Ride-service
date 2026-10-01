import asyncio
import itertools

from src.clients.provider_client import ProviderOrder
from src.domain.exceptions.provider import ProviderError, ProviderTimeoutError


class StubProvider:
    """In-memory provider with the same idempotency semantics as the mock container."""

    def __init__(self):
        self.orders_by_reference: dict[str, ProviderOrder] = {}
        self.create_calls = 0
        self.cancelled: list[str] = []
        self.latency = 0.0
        self.errors_before_create: list[Exception] = []
        self.timeouts_after_create = 0
        self.on_order_created = None
        self._ids = itertools.count(1)

    @property
    def orders(self) -> list[ProviderOrder]:
        return list(self.orders_by_reference.values())

    def order(self, provider_order_id: str) -> ProviderOrder:
        return next(o for o in self.orders if o.provider_order_id == provider_order_id)

    async def create_order(self, reference: str, pickup: str, dropoff: str) -> ProviderOrder:
        self.create_calls += 1
        if self.latency:
            await asyncio.sleep(self.latency)
        if self.errors_before_create:
            raise self.errors_before_create.pop(0)

        order = self.orders_by_reference.get(reference)
        if order is None:
            order = ProviderOrder(provider_order_id=f"prov-{next(self._ids)}", status="accepted")
            self.orders_by_reference[reference] = order
            if self.on_order_created:
                await self.on_order_created(order)

        if self.timeouts_after_create:
            self.timeouts_after_create -= 1
            raise ProviderTimeoutError("create_order: timed out")
        return ProviderOrder(order.provider_order_id, order.status)

    async def get_order(self, provider_order_id: str) -> ProviderOrder:
        order = self.order(provider_order_id)
        return ProviderOrder(order.provider_order_id, order.status)

    async def cancel_order(self, provider_order_id: str) -> ProviderOrder:
        order = self.order(provider_order_id)
        if order.status == "completed":
            raise ProviderError("order already completed")
        order.status = "cancelled"
        self.cancelled.append(provider_order_id)
        return ProviderOrder(order.provider_order_id, order.status)


class StubPublisher:
    def __init__(self, fail_on: int | None = None):
        self.published = []
        self._fail_on = fail_on

    async def publish(self, event) -> None:
        if self._fail_on is not None and len(self.published) == self._fail_on:
            raise ConnectionError("broker is down")
        self.published.append(event)
