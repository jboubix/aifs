"""Deterministic ATC decisions. Phraseology chooses the words. This module chooses the constraint."""

import logging

from ..bus import DEVIATION, INSTRUCTION, INTENT, Bus
from ..config import Settings
from ..context import ClearanceRegistry, WorldStore
from ..contracts import Clearance, Deviation, Instruction, InstructionKind, IntentParsed, new_id

log = logging.getLogger("atc.controller")

# Feet. Inside this band the aircraft is already at the assigned altitude.
_LEVEL_BAND_FT = 50


class Controller:
    def __init__(
        self,
        bus: Bus,
        world: WorldStore,
        clearances: ClearanceRegistry,
        settings: Settings,
    ) -> None:
        self._bus = bus
        self._world = world
        self._clearances = clearances
        self._tolerance_ft = settings.altitude_tolerance_ft
        bus.subscribe(INTENT, self.on_intent)
        bus.subscribe(DEVIATION, self.on_deviation)

    async def on_intent(self, event: IntentParsed) -> None:
        intent = event.intent
        if intent.kind == "altitude_request" and intent.altitude_ft is not None:
            await self._assign_altitude(event, intent.altitude_ft)
            return
        if intent.kind == "taxi_request":
            await self._instruct(event, "hold_position")
            return
        await self._instruct(event, "say_again")

    async def on_deviation(self, event: Deviation) -> None:
        log.info(
            "correction session=%s target=%s actual=%.0f %s",
            event.session_id,
            event.target_ft,
            event.actual_ft,
            event.direction,
        )
        await self._bus.publish(
            INSTRUCTION,
            Instruction(
                exchange_id=new_id(),
                session_id=event.session_id,
                callsign=event.callsign,
                frequency_mhz=event.frequency_mhz,
                kind="altitude_correction",
                altitude_ft=event.target_ft,
                direction=event.direction,
            ),
        )

    async def _assign_altitude(self, event: IntentParsed, target_ft: int) -> None:
        state = await self._world.get(event.session_id)
        current = state.altitude_msl_ft if state is not None else None
        if current is None or target_ft > current + _LEVEL_BAND_FT:
            kind = "climb_maintain"
        elif target_ft < current - _LEVEL_BAND_FT:
            kind = "descend_maintain"
        else:
            kind = "maintain"
        clearance = Clearance(
            id=new_id(),
            session_id=event.session_id,
            kind="altitude",
            target_ft=target_ft,
            tolerance_ft=self._tolerance_ft,
        )
        await self._clearances.put(clearance)
        log.info("clearance session=%s altitude=%s (%s)", event.session_id, target_ft, kind)
        await self._instruct(event, kind, altitude_ft=target_ft)

    async def _instruct(
        self,
        event: IntentParsed,
        kind: InstructionKind,
        altitude_ft: int | None = None,
    ) -> None:
        await self._bus.publish(
            INSTRUCTION,
            Instruction(
                exchange_id=event.exchange_id,
                session_id=event.session_id,
                callsign=event.callsign,
                frequency_mhz=event.frequency_mhz,
                kind=kind,
                altitude_ft=altitude_ft,
            ),
        )
