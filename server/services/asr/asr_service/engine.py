from .config import Settings
from .stub import StubAsr


def build_engine(settings: Settings):
    if settings.provider == "openai":
        from .openai_stt import OpenAiAsr

        return OpenAiAsr(settings.openai_api_key, settings.openai_model)
    if settings.provider == "whisper_atc":
        from .whisper_atc import WhisperAtcStt

        return WhisperAtcStt(
            settings.whisper_model_id,
            settings.whisper_device,
            settings.whisper_num_beams,
            settings.min_rms,
        )
    return StubAsr(settings.stub_text)
