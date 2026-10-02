from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ReplyMode = Literal["brain", "echo"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATC_", extra="ignore")

    auth_token: str = ""

    # "echo" speaks the pilot's words back and does not touch the controller.
    # "brain" runs intent -> controller -> phraseology.
    reply_mode: ReplyMode = "brain"

    redis_url: str = "redis://localhost:6379/0"
    asr_url: str = "http://localhost:8101"
    tts_url: str = "http://localhost:8102"
    voice_timeout_s: float = 120.0
    exchange_timeout_s: float = 30.0

    radio_fx: bool = True

    # Audio contract with the client. TTS health can override the output rate at startup.
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    max_ptt_seconds: float = 30.0

    # Altitude conformance. Sustain 0 fires on the first out-of-tolerance airborne sample.
    altitude_tolerance_ft: float = 200.0
    deviation_sustain_s: float = 5.0

    # Weather ingest stays off until a URL is set. The aviationweather.gov path is TODO(verify).
    weather_ingest: bool = False
    weather_metar_url: str = ""
    weather_icaos: str = ""
    weather_interval_s: float = 300.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
