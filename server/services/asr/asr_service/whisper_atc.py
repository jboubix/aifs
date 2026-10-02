"""Local speech-to-text using jacktol/whisper-large-v3-finetuned-for-ATC (Hugging Face transformers).

The model is a Whisper large-v3 fine-tune for ATC radio. It expects 16 kHz mono audio, which is
exactly what the client sends, so no resampling is needed. Loading is heavy (several GB), so
call `load()` once at startup; `transcribe` runs inference in a worker thread.
"""

import asyncio
import logging
import threading
import time

import numpy as np

log = logging.getLogger("atc.whisper")

WHISPER_SAMPLE_RATE = 16000


class WhisperAtcStt:
    def __init__(
        self,
        model_id: str,
        device: str = "auto",
        num_beams: int = 1,
        min_rms: float = 0.004,
    ) -> None:
        self._model_id = model_id
        self._device_pref = device
        self._num_beams = num_beams
        self._min_rms = min_rms
        self._model = None
        self._processor = None
        self._device = "cpu"
        self._dtype = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()  # one GPU inference at a time

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        """Download (first run) and load the model. Safe to call more than once."""
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            from transformers import WhisperForConditionalGeneration, WhisperProcessor

            device = self._device_pref
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("whisper_device=cuda but CUDA is not available in this torch build")
            dtype = torch.float16 if device == "cuda" else torch.float32

            t0 = time.perf_counter()
            log.info("Loading %s on %s (%s) ...", self._model_id, device, str(dtype).split(".")[-1])
            processor = WhisperProcessor.from_pretrained(self._model_id)
            model = WhisperForConditionalGeneration.from_pretrained(
                self._model_id, torch_dtype=dtype, low_cpu_mem_usage=True
            )
            model.to(device).eval()
            self._processor, self._model = processor, model
            self._device, self._dtype = device, dtype
            log.info("Whisper ATC model ready in %.1fs", time.perf_counter() - t0)

            # Warm up kernels so the first real transmission isn't slow.
            self._transcribe_sync(np.zeros(WHISPER_SAMPLE_RATE, dtype=np.float32), skip_gate=True)

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str:
        audio = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        if sample_rate != WHISPER_SAMPLE_RATE:
            audio = _resample(audio, sample_rate, WHISPER_SAMPLE_RATE)
        return await asyncio.to_thread(self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: np.ndarray, skip_gate: bool = False) -> str:
        if not skip_gate:
            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            if rms < self._min_rms:
                log.info("Audio below noise gate (rms=%.5f); skipping transcription", rms)
                return ""
        if self._model is None:
            self.load()

        import torch

        with self._infer_lock:
            t0 = time.perf_counter()
            features = self._processor(
                audio, sampling_rate=WHISPER_SAMPLE_RATE, return_tensors="pt"
            ).input_features.to(self._device, dtype=self._dtype)
            with torch.inference_mode():
                ids = self._model.generate(
                    features,
                    language="en",
                    task="transcribe",
                    num_beams=self._num_beams,
                    max_new_tokens=128,
                )
            text = self._processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
            log.info("Transcribed %.1fs of audio in %.2fs", audio.size / WHISPER_SAMPLE_RATE,
                     time.perf_counter() - t0)
            return text


def _resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    n = round(audio.size * dst / src)
    return np.interp(np.linspace(0, audio.size - 1, n), np.arange(audio.size), audio).astype(
        np.float32
    )
