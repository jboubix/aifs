"""Wire protocol between the MSFS client and this server.

Transport: one WebSocket at /ws.
  * Text frames carry JSON objects with a "type" field (models below).
  * Binary frames carry raw PCM16 little-endian mono audio:
      - client -> server: 16 kHz, only between ptt_start and ptt_end
      - server -> client: 24 kHz (see audio_start.sample_rate), between audio_start and audio_end
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Msg(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---- client -> server -------------------------------------------------------------------------


class Hello(_Msg):
    type: Literal["hello"] = "hello"
    client_version: str = ""
    callsign: str = ""


class Telemetry(_Msg):
    """Snapshot of sim state. Field names are snake_case on the wire."""

    type: Literal["telemetry"] = "telemetry"
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_msl_ft: float = 0.0
    altitude_agl_ft: float = 0.0
    heading_true: float = 0.0
    ground_speed_kt: float = 0.0
    indicated_airspeed_kt: float = 0.0
    on_ground: bool = True
    com1_active_mhz: float = 0.0
    com2_active_mhz: float = 0.0
    com_transmit_1: bool = True
    com_transmit_2: bool = False
    transponder_code: int = 1200
    avionics_on: bool = True
    callsign: str = ""
    aircraft_title: str = ""


class PttStart(_Msg):
    type: Literal["ptt_start"] = "ptt_start"
    radio: int = 1
    frequency_mhz: float = 0.0


class PttEnd(_Msg):
    type: Literal["ptt_end"] = "ptt_end"


# ---- server -> client -------------------------------------------------------------------------


class Welcome(_Msg):
    type: Literal["welcome"] = "welcome"
    session_id: str
    input_sample_rate: int
    output_sample_rate: int


class TranscriptMsg(_Msg):
    type: Literal["transcript"] = "transcript"
    speaker: Literal["pilot", "atc"]
    text: str
    frequency_mhz: float = 0.0


class AudioStart(_Msg):
    type: Literal["audio_start"] = "audio_start"
    sample_rate: int
    frequency_mhz: float = 0.0


class AudioEnd(_Msg):
    type: Literal["audio_end"] = "audio_end"


class ErrorMsg(_Msg):
    type: Literal["error"] = "error"
    message: str
