import asyncio

from atc_server.bus import PHRASE, TELEMETRY, TRANSCRIPT, Bus
from atc_server.clearances import MemoryClearanceRegistry
from atc_server.config import Settings
from atc_server.contracts import AircraftState, TranscriptFinal
from atc_server.controller import Controller
from atc_server.intent import IntentService, parse_intent
from atc_server.monitor import ConformanceMonitor
from atc_server.phraseology import Phraseology
from atc_server.world import MemoryWorldStore


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "altitude_tolerance_ft": 200,
        "deviation_sustain_s": 0,
    }
    values.update(overrides)
    return Settings(**values)


def _chain(settings: Settings, clock=None):
    bus = Bus()
    world = MemoryWorldStore()
    clearances = MemoryClearanceRegistry()
    IntentService(bus)
    Controller(bus, world, clearances, settings)
    Phraseology(bus)
    ConformanceMonitor(bus, clearances, settings, clock=clock)
    phrases = []

    async def grab(event):
        phrases.append(event)

    bus.subscribe(PHRASE, grab)
    return bus, world, clearances, phrases


def test_parser_known_requests():
    climb = parse_intent("request climb and maintain 5000")
    assert climb.kind == "altitude_request" and climb.altitude_ft == 5000
    assert parse_intent("descend and maintain 3000").altitude_ft == 3000
    assert parse_intent("request taxi to runway 28").kind == "taxi_request"
    assert parse_intent("good morning").kind == "say_again"
    assert parse_intent("climb and maintain 5").kind == "say_again"


def test_altitude_clearance_and_airborne_deviation():
    bus, world, clearances, phrases = _chain(_settings())

    async def run():
        await world.upsert(
            AircraftState(session_id="s1", callsign="N123AB", altitude_msl_ft=1500, on_ground=False)
        )
        await bus.publish(
            TRANSCRIPT,
            TranscriptFinal(
                exchange_id="e1",
                session_id="s1",
                callsign="N123AB",
                frequency_mhz=121.9,
                text="request climb and maintain 5000",
            ),
        )
        assert phrases[-1].text == "N123AB, climb and maintain 5000"
        stored = await clearances.list("s1")
        assert stored[0].target_ft == 5000

        await bus.publish(
            TELEMETRY,
            AircraftState(
                session_id="s1",
                callsign="N123AB",
                altitude_msl_ft=100,
                on_ground=True,
                frequency_mhz=121.9,
            ),
        )
        assert len(phrases) == 1

        await bus.publish(
            TELEMETRY,
            AircraftState(
                session_id="s1",
                callsign="N123AB",
                altitude_msl_ft=1500,
                on_ground=False,
                frequency_mhz=121.9,
            ),
        )
        assert phrases[-1].text == "N123AB, check your altitude, climb and maintain 5000"
        assert len(phrases) == 2

        await bus.publish(
            TELEMETRY,
            AircraftState(
                session_id="s1",
                callsign="N123AB",
                altitude_msl_ft=1600,
                on_ground=False,
                frequency_mhz=121.9,
            ),
        )
        assert len(phrases) == 2

    asyncio.run(run())


def test_deviation_waits_for_sustain():
    now = [0.0]
    bus, _, _, phrases = _chain(_settings(deviation_sustain_s=10), clock=lambda: now[0])

    async def run():
        await bus.publish(
            TRANSCRIPT,
            TranscriptFinal(
                exchange_id="e1",
                session_id="s1",
                callsign="N123AB",
                frequency_mhz=121.9,
                text="request climb and maintain 5000",
            ),
        )
        off = AircraftState(
            session_id="s1",
            callsign="N123AB",
            altitude_msl_ft=1500,
            on_ground=False,
            frequency_mhz=121.9,
        )
        await bus.publish(TELEMETRY, off)
        assert len(phrases) == 1
        now[0] = 10
        await bus.publish(TELEMETRY, off)
        assert "check your altitude" in phrases[-1].text

    asyncio.run(run())


def test_taxi_and_unknown_do_not_invent_a_clearance():
    bus, _, clearances, phrases = _chain(_settings())

    async def run():
        await bus.publish(
            TRANSCRIPT,
            TranscriptFinal(
                exchange_id="e1",
                session_id="s1",
                callsign="N123AB",
                frequency_mhz=121.9,
                text="request taxi",
            ),
        )
        assert phrases[-1].text == "N123AB, hold position"
        assert await clearances.list("s1") == []
        await bus.publish(
            TRANSCRIPT,
            TranscriptFinal(
                exchange_id="e2",
                session_id="s1",
                callsign="N123AB",
                frequency_mhz=121.9,
                text="hello tower",
            ),
        )
        assert phrases[-1].text == "N123AB, say again"

    asyncio.run(run())
