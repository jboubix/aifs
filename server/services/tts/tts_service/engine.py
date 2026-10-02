from .config import Settings
from .stub import StubTts


def build_engine(settings: Settings):
    if settings.provider == "openai":
        from .openai_tts import OpenAiTts

        return OpenAiTts(settings.openai_api_key, settings.openai_model, settings.openai_voice)
    if settings.provider == "kokoro":
        from .kokoro_tts import KokoroTts

        return KokoroTts(
            settings.kokoro_voice,
            settings.kokoro_lang,
            settings.kokoro_provider,
            settings.kokoro_speed,
        )
    return StubTts(settings.sample_rate)
