"""In-process bus. Handlers run to completion before publish returns, including nested publishes.

Replace this module with NATS (same topic names) when a module moves to its own process.
Handlers must not wait on the WebSocket read loop.
"""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

log = logging.getLogger("atc.bus")

TRANSCRIPT = "transcript.final"
INTENT = "intent.parsed"
INSTRUCTION = "instruction.issued"
PHRASE = "phrase.ready"
TELEMETRY = "telemetry.updated"
DEVIATION = "deviation.detected"

Handler = Callable[[BaseModel], Awaitable[None]]


class Bus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    async def publish(self, topic: str, event: BaseModel) -> None:
        for handler in list(self._handlers.get(topic, ())):
            try:
                await handler(event)
            except Exception:
                log.exception("handler failed topic=%s", topic)
                raise
