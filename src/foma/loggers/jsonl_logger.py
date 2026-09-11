"""JSONL logger: every event appended as one JSON line per day.

This gives a persistent, replayable record (``logs/foma-YYYY-MM-DD.jsonl``)
with zero server, zero open ports. Any future SSE/dashboard feature streams
from the same event bus that feeds this file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import IO

from ..events import Event, EventBus


class JsonlLogger:
    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        self._fh: IO[str] | None = None
        self._day: str | None = None

    async def run(self, bus: EventBus) -> None:
        queue = bus.subscribe()
        try:
            while True:
                event = await queue.get()
                self._write(event)
                if event.type == "shutdown":
                    break
        finally:
            bus.unsubscribe(queue)
            self.close()

    def _write(self, event: Event) -> None:
        day = datetime.now().strftime("%Y-%m-%d")
        if self._fh is None or self._day != day:
            self.close()
            self._log_dir.mkdir(parents=True, exist_ok=True)
            path = self._log_dir / f"foma-{day}.jsonl"
            self._fh = path.open("a", encoding="utf-8")
            self._day = day
        assert self._fh is not None
        self._fh.write(json.dumps(event.to_dict(), separators=(",", ":")) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._day = None
