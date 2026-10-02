from openai import AsyncOpenAI

from .wav import pcm16_to_wav

_PROMPT = (
    "Aviation radio communication with air traffic control. Phonetic alphabet, "
    "callsigns such as 'November one two three alpha bravo', runways, taxiways, "
    "altimeter settings, squawk codes, 'niner', 'tree', 'fife'. {hint}"
)


class OpenAiAsr:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai ASR provider")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str:
        wav = pcm16_to_wav(pcm16, sample_rate)
        result = await self._client.audio.transcriptions.create(
            model=self._model,
            file=("ptt.wav", wav, "audio/wav"),
            prompt=_PROMPT.format(hint=hint),
            language="en",
        )
        return result.text.strip()
