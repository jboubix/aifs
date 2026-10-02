"""Transcribe a 16 kHz mono PCM16 WAV with the local ATC Whisper model.

Run from server/ with the ASR tree on PYTHONPATH:

    $env:PYTHONPATH = "services\\asr"
    python scripts/transcribe_wav.py path\\to\\file.wav
"""

import asyncio
import logging
import sys
import wave

from asr_service.config import Settings
from asr_service.whisper_atc import WhisperAtcStt

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main(path: str) -> None:
    with wave.open(path, "rb") as handle:
        assert handle.getnchannels() == 1 and handle.getsampwidth() == 2, "need mono PCM16 WAV"
        rate, pcm = handle.getframerate(), handle.readframes(handle.getnframes())
    settings = Settings()
    stt = WhisperAtcStt(
        settings.whisper_model_id,
        settings.whisper_device,
        settings.whisper_num_beams,
        settings.min_rms,
    )
    stt.load()
    print("TRANSCRIPT:", await stt.transcribe(pcm, rate))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
