"""Local text-to-speech with Kokoro-82M (hexgrad/Kokoro-82M).

The official `kokoro` package requires Python <3.13. This server runs the same v1.0 model
through pykokoro, which uses the ONNX export and works on Python 3.13. Weights download on
the first load.
"""

import asyncio
import logging
import os
import re
import threading

import numpy as np

log = logging.getLogger("atc.kokoro")


def _expose_torch_cuda_dlls() -> None:
    """ONNX Runtime looks for cublas/cudnn on PATH. PyTorch already ships them."""
    if os.name != "nt":
        return
    import importlib.util

    spec = importlib.util.find_spec("torch")
    if spec is None or not spec.origin:
        return
    lib = os.path.join(os.path.dirname(spec.origin), "lib")
    if not os.path.isdir(lib):
        return
    os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(lib)


_BELOW_20 = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _speak_int(n: int) -> str:
    """Say an integer the way a controller would, so Kokoro's word g2p can handle it."""
    if n < 0:
        return "minus " + _speak_int(-n)
    if n < 20:
        return _BELOW_20[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] if ones == 0 else f"{_TENS[tens]} {_BELOW_20[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = f"{_BELOW_20[hundreds]} hundred"
        return head if rest == 0 else f"{head} {_speak_int(rest)}"
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        head = f"{_speak_int(thousands)} thousand"
        return head if rest == 0 else f"{head} {_speak_int(rest)}"
    return " ".join(_BELOW_20[int(d)] for d in str(n))


def for_speech(text: str) -> str:
    """Lowercase and spell digits as words.

    Kokoro's grapheme-to-phoneme path asks for eSpeak NG whenever a token is a
    number. Without that binary, synthesis returns 500. Altitudes such as 5000
    are spoken as "five thousand".
    """
    spoken = " ".join(text.split()).lower()
    spoken = re.sub(r"\d+", lambda match: _speak_int(int(match.group())), spoken)
    if spoken and spoken[-1] not in ".!?":
        spoken += "."
    return spoken


class KokoroTts:
    sample_rate = 24000

    def __init__(
        self,
        voice: str = "am_michael",
        lang: str = "en-us",
        provider: str = "cuda",
        speed: float = 1.0,
    ) -> None:
        self._voice = voice
        self._lang = lang
        self._provider = provider
        self._speed = speed
        self._synth = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if self._synth is not None:
            return
        _expose_torch_cuda_dlls()
        import onnxruntime

        onnxruntime.set_default_logger_severity(3)
        from pykokoro import KokoroSynthesizer
        from pykokoro.generation_config import GenerationConfig
        from pykokoro.synthesis_config import SynthesisConfig

        providers = [self._provider] if self._provider == "cpu" else [self._provider, "cpu"]
        last_error: Exception | None = None
        for provider in providers:
            try:
                synth = KokoroSynthesizer(
                    SynthesisConfig(
                        voice=self._voice,
                        provider=provider,
                        model_quality="fp32",
                        generation=GenerationConfig(lang=self._lang, speed=self._speed),
                    )
                )
                result = synth.synthesize_text(
                    "Radio check.", language=self._lang, voice=self._voice
                )
                warmup = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                if warmup.size == 0 or not np.isfinite(warmup).any():
                    raise RuntimeError(f"{provider} produced no usable audio")
                self._synth = synth
                self.sample_rate = result.sample_rate
                log.info(
                    "Kokoro ready on %s, voice %s, %d Hz", provider, self._voice, self.sample_rate
                )
                return
            except Exception as exc:  # noqa: BLE001 - try the next ONNX provider
                last_error = exc
                log.warning("Kokoro provider %s failed: %s", provider, exc)
        raise RuntimeError("Kokoro failed to load") from last_error

    async def synthesize(self, text: str, voice: str | None = None):
        spoken = for_speech(text)
        if not spoken:
            return
        pcm = await asyncio.to_thread(self._synthesize_sync, spoken, voice or self._voice)
        if pcm:
            yield pcm

    def _synthesize_sync(self, text: str, voice: str) -> bytes:
        if self._synth is None:
            self.load()
        with self._lock:
            result = self._synth.synthesize_text(text, language=self._lang, voice=voice)
        audio = np.nan_to_num(
            np.asarray(result.audio, dtype=np.float32).reshape(-1), nan=0.0, posinf=0.0, neginf=0.0
        )
        if audio.size == 0 or float(np.max(np.abs(audio))) == 0.0:
            return b""
        self.sample_rate = result.sample_rate
        return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
