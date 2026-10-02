class StubAsr:
    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str:
        del pcm16, sample_rate, hint
        return self._text
