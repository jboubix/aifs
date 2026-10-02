import logging

from ..bus import INTENT, TRANSCRIPT, Bus
from ..contracts import IntentParsed, TranscriptFinal
from .parse import parse_intent

log = logging.getLogger("atc.intent")


class IntentService:
    def __init__(self, bus: Bus) -> None:
        self._bus = bus
        bus.subscribe(TRANSCRIPT, self.on_transcript)

    async def on_transcript(self, event: TranscriptFinal) -> None:
        intent = parse_intent(event.text)
        log.info("intent session=%s kind=%s", event.session_id, intent.kind)
        await self._bus.publish(
            INTENT,
            IntentParsed(
                exchange_id=event.exchange_id,
                session_id=event.session_id,
                callsign=event.callsign,
                frequency_mhz=event.frequency_mhz,
                intent=intent,
            ),
        )
