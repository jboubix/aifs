from collections.abc import AsyncIterator

import numpy as np


class StubTts:
    """One short tone per word. No model and no network."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate

    async def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        del voice
        words = max(1, len(text.split()))
        t = np.arange(int(self.sample_rate * 0.08)) / self.sample_rate
        beep = 0.3 * np.sin(2 * np.pi * 600 * t)
        gap = np.zeros(int(self.sample_rate * 0.04))
        wave = np.tile(np.concatenate([beep, gap]), min(words, 40))
        yield (wave * 32767).astype("<i2").tobytes()
