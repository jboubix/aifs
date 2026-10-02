"""METAR text keyed by ICAO. The ingest loop is opt-in. See weather/ingest.py."""

TTL_S = 6 * 60 * 60


def weather_key(icao: str) -> str:
    return f"atc:weather:{icao.strip().upper()}"


class MemoryWeatherCache:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    async def put(self, icao: str, raw: str, observed_unix: float) -> None:
        del observed_unix
        self._items[icao.strip().upper()] = raw

    async def get(self, icao: str) -> str | None:
        return self._items.get(icao.strip().upper())


class RedisWeatherCache:
    def __init__(self, redis) -> None:
        self._redis = redis

    async def put(self, icao: str, raw: str, observed_unix: float) -> None:
        del observed_unix
        await self._redis.set(weather_key(icao), raw, ex=TTL_S)

    async def get(self, icao: str) -> str | None:
        return await self._redis.get(weather_key(icao))
