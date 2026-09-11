"""In-process event model and an async publish/subscribe bus.

Every notable thing that happens (detection, click, telemetry sample, ...) is a
plain dataclass event pushed into the bus. Consumers - console logger, JSONL
logger, and any future SSE/dashboard subscriber - just subscribe a queue. This
is the single extension point for streaming out events later.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "ts": self.ts, "data": self.data}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


class EventBus:
    def __init__(self, maxsize: int = 512) -> None:
        self._queues: list[asyncio.Queue[Event]] = []
        self._maxsize = maxsize

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._maxsize)
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    async def publish(self, event: Event) -> None:
        for queue in list(self._queues):
            if queue.full():
                with suppress(asyncio.QueueEmpty):  # pragma: no cover - defensive
                    queue.get_nowait()
            queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._queues)
