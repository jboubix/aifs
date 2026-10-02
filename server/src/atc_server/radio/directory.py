"""Who is tuned where. Party-line delivery uses this. Range limits are not modelled yet."""

from dataclasses import dataclass, field


@dataclass
class RadioDirectory:
    """session id -> frequency in MHz, rounded to 1 kHz (3 decimal places)."""

    _freq: dict[str, float] = field(default_factory=dict)

    def tune(self, session_id: str, frequency_mhz: float) -> None:
        self._freq[session_id] = round(float(frequency_mhz), 3)

    def drop(self, session_id: str) -> None:
        self._freq.pop(session_id, None)

    def listeners(self, frequency_mhz: float) -> list[str]:
        key = round(float(frequency_mhz), 3)
        return [sid for sid, freq in self._freq.items() if freq == key]
