"""Audio helpers: PCM16 <-> WAV and a cheap VHF-radio effect (numpy only)."""

import io
import wave

import numpy as np


def pcm16_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def pcm16_duration_s(pcm: bytes, sample_rate: int) -> float:
    return len(pcm) / 2 / sample_rate


def apply_radio_fx(
    pcm: bytes,
    sample_rate: int,
    low_hz: float = 300.0,
    high_hz: float = 3400.0,
    noise_level: float = 0.012,
    drive: float = 2.0,
    seed: int | None = None,
) -> bytes:
    """Bandpass (FFT brick-wall), soft clip, light noise and a short squelch tail."""
    if not pcm:
        return pcm
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0

    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / sample_rate)
    spec[(freqs < low_hz) | (freqs > high_hz)] = 0
    x = np.fft.irfft(spec, n=len(x)).astype(np.float32)

    peak = float(np.max(np.abs(x))) or 1.0
    x = np.tanh(drive * x / peak) / np.tanh(drive)  # soft clip + normalise
    x *= 0.8

    rng = np.random.default_rng(seed)
    x += rng.normal(0.0, noise_level, size=x.shape).astype(np.float32)

    # ~80 ms of noise after the voice, like a squelch tail.
    tail = rng.normal(0.0, noise_level * 2, size=int(sample_rate * 0.08)).astype(np.float32)
    tail *= np.linspace(1.0, 0.0, tail.shape[0], dtype=np.float32)
    x = np.concatenate([x, tail])

    return (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def chunk(data: bytes, size: int = 4800):
    """Yield fixed-size chunks (default 100 ms at 24 kHz PCM16)."""
    for i in range(0, len(data), size):
        yield data[i : i + size]
