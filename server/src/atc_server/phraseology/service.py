from ..bus import INSTRUCTION, PHRASE, Bus
from ..contracts import Instruction, PhraseReady
from .render import render


class Phraseology:
    def __init__(self, bus: Bus) -> None:
        self._bus = bus
        bus.subscribe(INSTRUCTION, self.on_instruction)

    async def on_instruction(self, instruction: Instruction) -> None:
        await self._bus.publish(
            PHRASE,
            PhraseReady(
                exchange_id=instruction.exchange_id,
                session_id=instruction.session_id,
                frequency_mhz=instruction.frequency_mhz,
                text=render(instruction),
            ),
        )
