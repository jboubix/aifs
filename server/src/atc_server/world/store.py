"""Live aircraft picture. Redis is the hot copy. MemoryWorldStore is for tests."""

from pydantic import TypeAdapter

from ..contracts import AircraftState

TTL_S = 6 * 60 * 60
_STATE = TypeAdapter(AircraftState)


def aircraft_key(session_id: str) -> str:
    return f"atc:aircraft:{session_id}"


class MemoryWorldStore:
    def __init__(self) -> None:
        self._items: dict[str, AircraftState] = {}

    async def upsert(self, state: AircraftState) -> None:
        self._items[state.session_id] = state

    async def get(self, session_id: str) -> AircraftState | None:
        return self._items.get(session_id)

    async def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)


class RedisWorldStore:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def upsert(self, state: AircraftState) -> None:
        await self._redis.set(aircraft_key(state.session_id), state.model_dump_json(), ex=TTL_S)

    async def get(self, session_id: str) -> AircraftState | None:
        raw = await self._redis.get(aircraft_key(session_id))
        if not raw:
            return None
        return _STATE.validate_json(raw)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(aircraft_key(session_id))
