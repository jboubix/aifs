"""Typed instruction to the sentence that is spoken. Templates are the authority."""

from ..contracts import Instruction


def render(instruction: Instruction) -> str:
    callsign = instruction.callsign.strip() or "aircraft"
    altitude = instruction.altitude_ft
    kind = instruction.kind
    if kind == "climb_maintain":
        return f"{callsign}, climb and maintain {altitude}"
    if kind == "descend_maintain":
        return f"{callsign}, descend and maintain {altitude}"
    if kind == "maintain":
        return f"{callsign}, maintain {altitude}"
    if kind == "altitude_correction":
        verb = "descend" if instruction.direction == "high" else "climb"
        return f"{callsign}, check your altitude, {verb} and maintain {altitude}"
    if kind == "hold_position":
        return f"{callsign}, hold position"
    return f"{callsign}, say again"
