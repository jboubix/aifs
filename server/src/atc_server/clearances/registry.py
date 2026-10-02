"""Active constraints per session. One clearance per kind. A new altitude replaces the old one."""

from pydantic import TypeAdapter

from ..contracts import Clearance

TTL_S = 6 * 60 * 60
_LIST = TypeAdapter(list[Clearance])


def clearance_key(session_id: str) -> str:
    return f"atc:clearance:{session_id}"


class MemoryClearanceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, list[Clearance]] = {}

    async def put(self, clearance: Clearance) -> None:
        current = [c for c in self._items.get(clearance.session_id, []) if c.kind != clearance.kind]
        current.append(clearance)
        self._items[clearance.session_id] = current

    async def list(self, session_id: str) -> list[Clearance]:
        return list(self._items.get(session_id, []))

    async def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)


class RedisClearanceRegistry:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def put(self, clearance: Clearance) -> None:
        current = [c for c in await self.list(clearance.session_id) if c.kind != clearance.kind]
        current.append(clearance)
        raw = _LIST.dump_json(current).decode()
        await self._redis.set(clearance_key(clearance.session_id), raw, ex=TTL_S)

    async def list(self, session_id: str) -> list[Clearance]:
        raw = await self._redis.get(clearance_key(session_id))
        if not raw:
            return []
        return _LIST.validate_json(raw)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(clearance_key(session_id))
