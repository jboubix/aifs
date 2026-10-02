"""Events that move between modules. The wire protocol to the sim client is gateway/protocol.py."""

from typing import Literal

from pydantic import BaseModel, Field


def new_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


class AircraftState(BaseModel):
    session_id: str
    callsign: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_msl_ft: float = 0.0
    altitude_agl_ft: float = 0.0
    heading_true: float = 0.0
    ground_speed_kt: float = 0.0
    indicated_airspeed_kt: float = 0.0
    on_ground: bool = True
    frequency_mhz: float = 0.0
    transponder_code: int = 1200
    updated_unix: float = 0.0


class TranscriptFinal(BaseModel):
    exchange_id: str
    session_id: str
    callsign: str
    frequency_mhz: float
    text: str


class ParsedIntent(BaseModel):
    kind: Literal["altitude_request", "taxi_request", "say_again"]
    altitude_ft: int | None = None
    source_text: str


class IntentParsed(BaseModel):
    exchange_id: str
    session_id: str
    callsign: str
    frequency_mhz: float
    intent: ParsedIntent


InstructionKind = Literal[
    "climb_maintain",
    "descend_maintain",
    "maintain",
    "hold_position",
    "say_again",
    "altitude_correction",
]


class Instruction(BaseModel):
    exchange_id: str
    session_id: str
    callsign: str
    frequency_mhz: float
    kind: InstructionKind
    altitude_ft: int | None = None
    direction: Literal["high", "low"] | None = None


class PhraseReady(BaseModel):
    exchange_id: str
    session_id: str
    frequency_mhz: float
    text: str


class Clearance(BaseModel):
    id: str
    session_id: str
    kind: Literal["altitude"] = "altitude"
    target_ft: int
    tolerance_ft: float = Field(gt=0)


class Deviation(BaseModel):
    session_id: str
    callsign: str
    frequency_mhz: float
    clearance_id: str
    kind: Literal["altitude"] = "altitude"
    target_ft: int
    actual_ft: float
    direction: Literal["high", "low"]
