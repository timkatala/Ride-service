import json
from typing import Protocol

from redis.asyncio import Redis

from src.domain.models import OutboxEvent


class EventPublisher(Protocol):
    async def publish(self, event: OutboxEvent) -> None: ...


class RedisStreamPublisher:
    def __init__(self, redis: Redis, stream: str):
        self._redis = redis
        self._stream = stream

    async def publish(self, event: OutboxEvent) -> None:
        await self._redis.xadd(
            self._stream,
            {
                "event_id": str(event.event_id),
                "type": event.event_type,
                "payload": json.dumps(event.payload),
            },
        )
