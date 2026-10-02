"""Compare live altitude with the active clearance.

Airborne only. On the ground the breach timer resets so a parked aircraft is not told
to climb. One call per excursion: the latch clears when the aircraft is back in
tolerance or lands.
"""

import logging
import time
from collections.abc import Callable

from ..bus import DEVIATION, TELEMETRY, Bus
from ..config import Settings
from ..context import ClearanceRegistry
from ..contracts import AircraftState, Deviation

log = logging.getLogger("atc.monitor")


class ConformanceMonitor:
    def __init__(
        self,
        bus: Bus,
        clearances: ClearanceRegistry,
        settings: Settings,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._bus = bus
        self._clearances = clearances
        self._sustain_s = settings.deviation_sustain_s
        self._clock = clock or time.monotonic
        self._breach_since: dict[str, float] = {}
        self._latched: set[str] = set()
        bus.subscribe(TELEMETRY, self.on_telemetry)

    async def on_telemetry(self, state: AircraftState) -> None:
        clearances = await self._clearances.list(state.session_id)
        seen: set[str] = set()
        for clearance in clearances:
            if clearance.kind != "altitude":
                continue
            key = f"{state.session_id}:{clearance.id}"
            seen.add(key)
            await self._check(state, clearance, key)
        prefix = f"{state.session_id}:"
        stale = [key for key in self._breach_since if key.startswith(prefix) and key not in seen]
        for key in stale:
            self._forget(key)

    async def _check(self, state: AircraftState, clearance, key: str) -> None:
        if state.on_ground:
            self._forget(key)
            return
        error_ft = abs(state.altitude_msl_ft - clearance.target_ft)
        if error_ft <= clearance.tolerance_ft:
            self._forget(key)
            return
        now = self._clock()
        started = self._breach_since.setdefault(key, now)
        if key in self._latched or now - started < self._sustain_s:
            return
        self._latched.add(key)
        direction = "low" if state.altitude_msl_ft < clearance.target_ft else "high"
        log.info(
            "deviation session=%s target=%s actual=%.0f",
            state.session_id,
            clearance.target_ft,
            state.altitude_msl_ft,
        )
        await self._bus.publish(
            DEVIATION,
            Deviation(
                session_id=state.session_id,
                callsign=state.callsign,
                frequency_mhz=state.frequency_mhz,
                clearance_id=clearance.id,
                target_ft=clearance.target_ft,
                actual_ft=state.altitude_msl_ft,
                direction=direction,
            ),
        )

    def _forget(self, key: str) -> None:
        self._breach_since.pop(key, None)
        self._latched.discard(key)
