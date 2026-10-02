# ATC server

The sim client stays thin. This folder is the ATC side.

- **App** (`src/atc_server/`): WebSocket gateway, intent, controller, phraseology, live aircraft state, clearances, and the altitude monitor. One process. Modules talk through an in-process bus.
- **ASR** (`services/asr/`): speech to text. Own process.
- **TTS** (`services/tts/`): text to speech. Own process.
- **Redis**: aircraft, clearances, and cached METAR.

The layout and the scale-out path are in [`docs/architecture.md`](../docs/architecture.md).

Supported sim: MSFS 2024 on PC, via the existing .NET client. The server does not run the sim. Xbox cannot run this external server.

## Run the stack

From `server/`:

```powershell
docker compose up -d --build --wait
```

- App WebSocket: `ws://127.0.0.1:8000/ws` (what `client` already uses). If something else is already on 8000, start Compose with `$env:ATC_HOST_PORT = "18000"` and point the client at that port.
- Health: `http://127.0.0.1:8000/health`
- ASR: `http://127.0.0.1:8101`  TTS: `http://127.0.0.1:8102`  Redis: `127.0.0.1:6379`

Compose runs ASR and TTS in **stub** mode: a fixed transcript (`request climb and maintain 5000`) and a tone, no GPU and no API key. `ATC_DEVIATION_SUSTAIN_S` is `0` in Compose so the integration test hears a correction on the first off-altitude sample. For a real session, set it to `5`.

`docker compose down` stops it.

ASR, TTS, and Redis are published on localhost so you can debug. Do not expose them on a public host. Set `ATC_AUTH_TOKEN` when the app port is not only for you.

## Tests

Unit tests do not need Docker:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

Integration test, against the Compose services:

```powershell
docker compose up -d --build --wait
.\.venv\Scripts\python -m pytest tests/integration -q
docker compose down
```

That test connects like the sim client, checks the pilot transcript came from the ASR service, checks the clearance landed in Redis, then sends an airborne altitude of 1500 ft against the assigned 5000 ft and expects "check your altitude".

## Real speech models

Not in the default images.

ASR `whisper_atc` (local ATC Whisper, multi-GB, CUDA recommended):

```powershell
.\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python -m pip install transformers
$env:PYTHONPATH = "services\asr"
$env:ASR_PROVIDER = "whisper_atc"
.\.venv\Scripts\python -m asr_service.main
.\.venv\Scripts\python scripts\transcribe_wav.py some_16k_mono.wav
```

`ASR_WHISPER_MODEL_ID`, `ASR_WHISPER_DEVICE` (`auto`/`cuda`/`cpu`), `ASR_WHISPER_NUM_BEAMS`, `ASR_MIN_RMS` (noise gate).

TTS `kokoro` (Kokoro-82M via pykokoro):

```powershell
.\.venv\Scripts\python -m pip install "pykokoro>=0.10" "onnxruntime-gpu>=1.20,<1.24"
$env:PYTHONPATH = "services\tts"
$env:TTS_PROVIDER = "kokoro"
.\.venv\Scripts\python -m tts_service.main
```

`TTS_KOKORO_VOICE` defaults to `am_michael`. `TTS_KOKORO_PROVIDER` is `cuda` or `cpu`.

`openai` on either service needs `OPENAI_API_KEY` plus `pip install openai` in that environment. `ASR_OPENAI_MODEL` / `TTS_OPENAI_MODEL` / `TTS_OPENAI_VOICE`.

Point the app at those processes with `ATC_ASR_URL` and `ATC_TTS_URL`.

`scripts/send_wav.py` sends one WAV through the app WebSocket (16 kHz mono PCM16).

## What the controller does today

- "climb/descend/maintain" plus an altitude in feet becomes an altitude clearance, stored in Redis, and a climb, descend, or maintain call from the aircraft's current altitude.
- "taxi" is hold position. There is no taxi graph yet.
- Anything else is "say again". Free text does not become a clearance.
- Airborne only: if altitude stays outside the tolerance for the sustain time, one "check your altitude" call. The latch clears on the ground or back inside tolerance.

## Manual check in the sim

Unit tests and the Compose test do not start MSFS.

1. `docker compose up -d --build --wait`, then the .NET client with `Sim:Mode=Auto` and the sim running.
2. Speak a climb request. Confirm the reply assigns an altitude and the client plays it on the radio.
3. Level off away from that altitude for longer than `ATC_DEVIATION_SUSTAIN_S`. Confirm one correction, and none while parked.
4. Quit the sim mid-session and start again. The server should drop the old session and accept a new one.
