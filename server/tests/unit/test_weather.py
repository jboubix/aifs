import asyncio

import httpx

from atc_server.weather.cache import MemoryWeatherCache
from atc_server.weather.ingest import fetch_metar, ingest_once, parse_icaos


def test_parse_icaos():
    assert parse_icaos(" ksfo, ,Kjfk ") == ["KSFO", "KJFK"]
    assert parse_icaos("") == []


def test_ingest_once_stores_reports_and_skips_blanks():
    cache = MemoryWeatherCache()

    async def fetch(icao: str) -> str | None:
        if icao == "KJFK":
            return None
        return f"{icao} 011200Z"

    async def run():
        stored = await ingest_once(["KSFO", "KJFK"], cache, fetch, now=1.0)
        assert stored == 1
        assert await cache.get("ksfo") == "KSFO 011200Z"
        assert await cache.get("KJFK") is None

    asyncio.run(run())


def test_fetch_metar_reads_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ids"] == "KSFO"
        assert request.url.params["format"] == "raw"
        return httpx.Response(200, text="KSFO 011200Z CAVOK")

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            text = await fetch_metar(client, "http://weather.example/metar", "KSFO")
        assert text == "KSFO 011200Z CAVOK"

    asyncio.run(run())
