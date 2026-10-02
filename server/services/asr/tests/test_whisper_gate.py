import numpy as np
from asr_service.whisper_atc import WhisperAtcStt, _resample


def test_noise_gate_skips_silence_without_loading_model():
    stt = WhisperAtcStt("unused/model")
    assert stt._transcribe_sync(np.zeros(16000, dtype=np.float32)) == ""
    assert not stt.loaded

    out = _resample(np.ones(48000, dtype=np.float32), 48000, 16000)
    assert out.shape == (16000,)
