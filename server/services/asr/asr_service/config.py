from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["stub", "openai", "whisper_atc"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASR_", extra="ignore")

    provider: ProviderName = "stub"
    port: int = 8101
    stub_text: str = "request climb and maintain 5000"
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini-transcribe"
    whisper_model_id: str = "jacktol/whisper-large-v3-finetuned-for-ATC"
    whisper_device: str = "auto"
    whisper_num_beams: int = 1
    min_rms: float = 0.004


@lru_cache
def get_settings() -> Settings:
    return Settings()
