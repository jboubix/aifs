import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from atc_server.bus import Bus
from atc_server.clearances import MemoryClearanceRegistry
from atc_server.config import Settings
from atc_server.context import AppContext, SessionRegistry
from atc_server.gateway.audio import apply_radio_fx
from atc_server.main import create_app
from atc_server.radio import RadioDirectory
from atc_server.weather import MemoryWeatherCache
from atc_server.world import MemoryWorldStore


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "auth_token": "",
        "radio_fx": False,
        "reply_mode": "brain",
        "altitude_tolerance_ft": 200,
        "deviation_sustain_s": 0,
        "exchange_timeout_s": 5,
        "weather_ingest": False,
    }
    values.update(overrides)
    return Settings(**values)


class _Asr:
    async def open(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def health(self) -> dict:
        return {"status": "ok", "provider": "stub"}

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str:
        del pcm16, sample_rate, hint
        return "request climb and maintain 5000"


class _Tts:
    async def open(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def health(self) -> dict:
        return {"status": "ok", "provider": "stub", "sample_rate": 24000}

    async def synthesize(self, text: str) -> tuple[int, bytes]:
        del text
        return 24000, b"\x01\x00" * 200


def _app(settings: Settings | None = None) -> TestClient:
    settings = settings or _settings()
    ctx = AppContext(
        settings=settings,
        bus=Bus(),
        world=MemoryWorldStore(),
        clearances=MemoryClearanceRegistry(),
        weather=MemoryWeatherCache(),
        asr=_Asr(),
        tts=_Tts(),
        sessions=SessionRegistry(),
        radio=RadioDirectory(),
    )
    return TestClient(create_app(settings, ctx))


def _tone(rate: int = 16000) -> bytes:
    t = np.arange(rate) / rate
    return (np.sin(2 * np.pi * 440 * t) * 8000).astype("<i2").tobytes()


def _exchange(ws, altitude_ft: float = 1500):
    welcome = json.loads(ws.receive_text())
    assert welcome["type"] == "welcome"
    assert welcome["output_sample_rate"] == 24000
    ws.send_text(json.dumps({"type": "hello", "callsign": "N123AB"}))
    ws.send_text(
        json.dumps(
            {
                "type": "telemetry",
                "callsign": "N123AB",
                "altitude_msl_ft": altitude_ft,
                "on_ground": False,
                "com1_active_mhz": 121.9,
            }
        )
    )
    ws.send_text(json.dumps({"type": "ptt_start", "radio": 1, "frequency_mhz": 121.9}))
    audio = _tone()
    for i in range(0, len(audio), 3200):
        ws.send_bytes(audio[i : i + 3200])
    ws.send_text(json.dumps({"type": "ptt_end"}))
    return welcome


def _read_spoken(ws) -> list[dict]:
    transcripts = []
    total = 0
    while True:
        msg = ws.receive()
        if msg.get("bytes") is not None:
            total += len(msg["bytes"])
            continue
        obj = json.loads(msg["text"])
        if obj["type"] == "transcript":
            transcripts.append(obj)
        elif obj["type"] == "audio_end":
            break
        elif obj["type"] == "error":
            raise AssertionError(obj["message"])
    assert transcripts and total > 0 and total % 2 == 0
    return transcripts


def test_health_reports_memory_without_redis():
    with _app() as client:
        body = client.get("/health")
        assert body.status_code == 200
        payload = body.json()
        assert payload["status"] == "ok"
        assert payload["redis"] == "memory"
        assert payload["asr"] == "ok" and payload["tts"] == "ok"


def test_ptt_assigns_altitude_and_deviation_is_spoken():
    with _app() as client, client.websocket_connect("/ws") as ws:
        _exchange(ws)
        spoken = _read_spoken(ws)
        assert spoken[0]["text"] == "request climb and maintain 5000"
        assert spoken[1]["text"] == "N123AB, climb and maintain 5000"

        ws.send_text(
            json.dumps(
                {
                    "type": "telemetry",
                    "callsign": "N123AB",
                    "altitude_msl_ft": 1500,
                    "on_ground": False,
                    "com1_active_mhz": 121.9,
                }
            )
        )
        correction = _read_spoken(ws)
        assert correction[0]["text"] == "N123AB, check your altitude, climb and maintain 5000"


def test_echo_skips_the_controller():
    with _app(_settings(reply_mode="echo")) as client, client.websocket_connect("/ws") as ws:
        _exchange(ws)
        spoken = _read_spoken(ws)
        assert spoken[1]["text"] == spoken[0]["text"]


def test_short_ptt_is_ignored_and_bad_json_reports_error():
    with _app() as client, client.websocket_connect("/ws") as ws:
        ws.receive_text()
        ws.send_text(json.dumps({"type": "ptt_start"}))
        ws.send_bytes(b"\x00\x00" * 100)
        ws.send_text(json.dumps({"type": "ptt_end"}))
        ws.send_text("not json")
        assert json.loads(ws.receive_text())["type"] == "error"


def test_auth_token_rejects_bad_token():
    with _app(_settings(auth_token="secret")) as client:
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?token=wrong"):
            pass
        with client.websocket_connect("/ws?token=secret") as ws:
            assert json.loads(ws.receive_text())["type"] == "welcome"


def test_radio_fx_preserves_format():
    pcm = _tone(24000)
    out = apply_radio_fx(pcm, 24000, seed=1)
    assert len(out) % 2 == 0 and len(out) > len(pcm)
