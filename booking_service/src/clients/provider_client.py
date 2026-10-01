from dataclasses import dataclass

import httpx

from src.domain.exceptions.provider import ProviderError, ProviderTimeoutError


@dataclass
class ProviderOrder:
    provider_order_id: str
    status: str


class ProviderClient:
    def __init__(self, base_url: str, timeout: float, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def close(self) -> None:
        await self._http.aclose()

    async def create_order(self, reference: str, pickup: str, dropoff: str) -> ProviderOrder:
        data = await self._request(
            "create_order",
            "POST",
            "/provider/orders",
            headers={"Idempotency-Key": reference},
            json={"reference": reference, "pickup": pickup, "dropoff": dropoff},
        )
        return ProviderOrder(provider_order_id=data["provider_order_id"], status=data["status"])

    async def get_order(self, provider_order_id: str) -> ProviderOrder:
        data = await self._request("get_order", "GET", f"/provider/orders/{provider_order_id}")
        return ProviderOrder(provider_order_id=data["provider_order_id"], status=data["status"])

    async def cancel_order(self, provider_order_id: str) -> None:
        await self._request("cancel_order", "POST", f"/provider/orders/{provider_order_id}/cancel")

    async def _request(self, operation: str, method: str, url: str, **kwargs) -> dict:
        try:
            response = await self._http.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"{operation}: timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderError(f"{operation}: {exc!r}") from exc

        if response.status_code >= 400:
            raise ProviderError(f"{operation}: provider returned {response.status_code}")
        return response.json()
