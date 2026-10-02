from dataclasses import dataclass, field
from typing import Any, Protocol

from .bus import Bus
from .config import Settings
from .contracts import AircraftState, Clearance
from .radio import RadioDirectory


class WorldStore(Protocol):
    async def upsert(self, state: AircraftState) -> None: ...

    async def get(self, session_id: str) -> AircraftState | None: ...

    async def delete(self, session_id: str) -> None: ...


class ClearanceRegistry(Protocol):
    async def put(self, clearance: Clearance) -> None: ...

    async def list(self, session_id: str) -> list[Clearance]: ...

    async def delete(self, session_id: str) -> None: ...


class WeatherCache(Protocol):
    async def put(self, icao: str, raw: str, observed_unix: float) -> None: ...

    async def get(self, icao: str) -> str | None: ...


class AsrClient(Protocol):
    async def open(self) -> None: ...

    async def aclose(self) -> None: ...

    async def health(self) -> dict: ...

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str: ...


class TtsClient(Protocol):
    async def open(self) -> None: ...

    async def aclose(self) -> None: ...

    async def health(self) -> dict: ...

    async def synthesize(self, text: str) -> tuple[int, bytes]: ...


@dataclass
class SessionRegistry:
    _sessions: dict[str, Any] = field(default_factory=dict)

    def add(self, session: Any) -> None:
        self._sessions[session.id] = session

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> Any:
        return self._sessions.get(session_id)


@dataclass
class AppContext:
    settings: Settings
    bus: Bus
    world: WorldStore
    clearances: ClearanceRegistry
    weather: WeatherCache
    asr: AsrClient
    tts: TtsClient
    sessions: SessionRegistry
    radio: RadioDirectory
    output_sample_rate: int = 24000
    redis: Any = None
    wired: bool = False
