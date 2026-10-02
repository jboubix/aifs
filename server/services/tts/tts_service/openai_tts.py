from collections.abc import AsyncIterator

from openai import AsyncOpenAI

_INSTRUCTIONS = (
    "You are an air traffic controller on a VHF radio. Speak briskly, calmly and "
    "professionally with standard ICAO phraseology. Say digits individually, "
    "and 9 as 'niner'."
)


class OpenAiTts:
    sample_rate = 24000  # OpenAI "pcm" format is 24 kHz PCM16 mono

    def __init__(self, api_key: str, model: str, voice: str) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai TTS provider")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._voice = voice

    async def synthesize(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        async with self._client.audio.speech.with_streaming_response.create(
            model=self._model,
            voice=voice or self._voice,
            input=text,
            instructions=_INSTRUCTIONS,
            response_format="pcm",
        ) as response:
            carry = b""
            async for data in response.iter_bytes(4800):
                data = carry + data
                if len(data) % 2:
                    data, carry = data[:-1], data[-1:]
                else:
                    carry = b""
                if data:
                    yield data
            if carry:
                yield carry + b"\x00"
