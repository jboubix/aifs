"""Rule parser. Unknown speech becomes say_again. It never becomes a clearance."""

import re

from ..contracts import ParsedIntent

# "climb and maintain 5000", "descend and maintain 3000".
_ALTITUDE = re.compile(r"(?:climb|descend|maintain)\D{0,40}(\d{3,5})", re.IGNORECASE)
_MAX_ALTITUDE_FT = 60000


def parse_intent(text: str) -> ParsedIntent:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ParsedIntent(kind="say_again", source_text=text)
    if "taxi" in cleaned.lower():
        return ParsedIntent(kind="taxi_request", source_text=cleaned)
    match = _ALTITUDE.search(cleaned)
    if match:
        altitude = int(match.group(1))
        if 0 < altitude <= _MAX_ALTITUDE_FT:
            return ParsedIntent(kind="altitude_request", altitude_ft=altitude, source_text=cleaned)
    return ParsedIntent(kind="say_again", source_text=cleaned)
