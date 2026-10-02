"""Pull METAR text into the weather cache.

The HTTP path is not built in. Set ATC_WEATHER_METAR_URL to the feed you have checked.
TODO(verify): aviationweather.gov current METAR path and query parameters.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

import httpx

from ..context import AppContext, WeatherCache

log = logging.getLogger("atc.weather")

Fetch = Callable[[str], Awaitable[str | None]]


def parse_icaos(raw: str) -> list[str]:
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


async def ingest_once(icaos: list[str], cache: WeatherCache, fetch: Fetch, now: float) -> int:
    stored = 0
    for icao in icaos:
        try:
            raw = await fetch(icao)
        except Exception:
            log.exception("METAR fetch failed icao=%s", icao)
            continue
        if not raw:
            continue
        await cache.put(icao, raw.strip(), now)
        stored += 1
    return stored


async def fetch_metar(client: httpx.AsyncClient, url: str, icao: str) -> str | None:
    response = await client.get(url, params={"ids": icao, "format": "raw"})
    if response.status_code != 200:
        log.warning("METAR HTTP %s for %s", response.status_code, icao)
        return None
    text = response.text.strip()
    return text or None


async def run_weather_ingest(ctx: AppContext) -> None:
    icaos = parse_icaos(ctx.settings.weather_icaos)
    url = ctx.settings.weather_metar_url.strip()
    if not icaos or not url:
        log.warning("weather ingest enabled but ATC_WEATHER_ICAOS or ATC_WEATHER_METAR_URL is empty")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            count = await ingest_once(
                icaos,
                ctx.weather,
                lambda icao, c=client, u=url: fetch_metar(c, u, icao),
                now=time.time(),
            )
            log.info("weather ingest stored %s report(s)", count)
            await asyncio.sleep(ctx.settings.weather_interval_s)
