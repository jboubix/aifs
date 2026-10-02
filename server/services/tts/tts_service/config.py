from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["stub", "openai", "kokoro"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TTS_", extra="ignore")

    provider: ProviderName = "stub"
    port: int = 8102
    sample_rate: int = 24000
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini-tts"
    openai_voice: str = "onyx"
    kokoro_voice: str = "am_michael"
    kokoro_lang: str = "en-us"
    kokoro_provider: str = "cuda"
    kokoro_speed: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
