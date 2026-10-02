"""End-to-end check against the Compose stack (Redis, ASR, TTS, app).

From server/:

    docker compose up -d --build --wait
    python -m pytest tests/integration -q
    docker compose down
"""

import asyncio
import json
import os

import httpx
import numpy as np
import pytest
import redis
import websockets

APP = os.environ.get("ATC_APP_URL", "http://127.0.0.1:8000")
WS = os.environ.get("ATC_WS_URL", "ws://127.0.0.1:8000/ws")
REDIS = "redis://127.0.0.1:6379/0"


def _tone(rate: int = 16000) -> bytes:
    t = np.arange(rate) / rate
    return (np.sin(2 * np.pi * 440 * t) * 8000).astype("<i2").tobytes()


async def _until_audio_end(ws) -> dict:
    atc = None
    while True:
        msg = await asyncio.wait_for(ws.recv(), 15)
        if isinstance(msg, bytes):
            continue
        obj = json.loads(msg)
        if obj["type"] == "error":
            raise AssertionError(obj["message"])
        if obj["type"] == "transcript" and obj["speaker"] == "pilot":
            continue
        if obj["type"] == "transcript" and obj["speaker"] == "atc":
            atc = obj
        elif obj["type"] == "audio_end":
            assert atc is not None
            return atc


async def _scenario() -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        health = await client.get(f"{APP}/health")
        assert health.status_code == 200, health.text
        body = health.json()
        assert body["status"] == "ok"
        assert body["redis"] == "ok"
        assert body["asr"] == "ok" and body["asr_provider"] == "stub"
        assert body["tts"] == "ok" and body["tts_provider"] == "stub"
        asr = (await client.get("http://127.0.0.1:8101/health")).json()
        assert asr["provider"] == "stub"

    store = redis.Redis.from_url(REDIS, decode_responses=True)
    try:
        async with websockets.connect(WS, open_timeout=5) as ws:
            welcome = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert welcome["type"] == "welcome"
            session_id = welcome["session_id"]

            await ws.send(json.dumps({"type": "hello", "callsign": "N123AB"}))
            await ws.send(
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
            await ws.send(json.dumps({"type": "ptt_start", "radio": 1, "frequency_mhz": 121.9}))
            audio = _tone()
            for i in range(0, len(audio), 3200):
                await ws.send(audio[i : i + 3200])
            await ws.send(json.dumps({"type": "ptt_end"}))

            # Pilot transcript is the ASR service's stub text, not an in-process guess.
            pilot = None
            while pilot is None:
                msg = await asyncio.wait_for(ws.recv(), 15)
                if isinstance(msg, str):
                    obj = json.loads(msg)
                    if obj["type"] == "transcript" and obj["speaker"] == "pilot":
                        pilot = obj
            assert pilot["text"] == "request climb and maintain 5000"
            clearance = await _until_audio_end(ws)
            assert clearance["text"] == "N123AB, climb and maintain 5000"

            raw = store.get(f"atc:clearance:{session_id}")
            assert raw and "5000" in raw

            await ws.send(
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
            correction = await _until_audio_end(ws)
            assert correction["text"] == "N123AB, check your altitude, climb and maintain 5000"
            aircraft = store.get(f"atc:aircraft:{session_id}")
            assert aircraft and "1500" in aircraft
            await ws.close()

        gone = False
        for _ in range(40):
            if store.get(f"atc:clearance:{session_id}") is None:
                gone = True
                break
            await asyncio.sleep(0.05)
        assert gone
    finally:
        store.close()


def test_compose_stack():
    try:
        asyncio.run(_scenario())
    except (httpx.ConnectError, OSError) as exc:
        pytest.fail(
            "Compose stack is not reachable. From server/: "
            f"docker compose up -d --build --wait ({exc})"
        )
