"""Act like the MSFS client: send one push-to-talk transmission from a WAV file to the server.

    python scripts/send_wav.py path\\to\\16k_mono.wav [ws://localhost:8000/ws]
"""

import asyncio
import json
import sys
import wave

import websockets


async def main(path: str, url: str) -> None:
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2, (
            "need 16 kHz mono PCM16 WAV"
        )
        pcm = w.readframes(w.getnframes())

    async with websockets.connect(url) as ws:
        print("<-", json.loads(await ws.recv())["type"])
        await ws.send(json.dumps({"type": "hello", "callsign": "N123AB", "client_version": "test"}))
        await ws.send(json.dumps({"type": "telemetry", "com1_active_mhz": 121.9, "callsign": "N123AB"}))
        await ws.send(json.dumps({"type": "ptt_start", "radio": 1, "frequency_mhz": 121.9}))
        for i in range(0, len(pcm), 1600):  # 50 ms chunks, like the client
            await ws.send(pcm[i : i + 1600])
        await ws.send(json.dumps({"type": "ptt_end"}))

        audio_bytes = 0
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=60)
            if isinstance(msg, bytes):
                audio_bytes += len(msg)
                continue
            obj = json.loads(msg)
            print("<-", obj)
            if obj["type"] in ("audio_end", "error"):
                break
        print(f"received {audio_bytes} bytes of ATC audio")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8000/ws"))
