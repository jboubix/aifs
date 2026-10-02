"""Speaks a ready phrase on the frequency. This is the only module that calls TTS."""

import logging

from ..bus import PHRASE
from ..context import AppContext
from ..contracts import PhraseReady
from .audio import apply_radio_fx

log = logging.getLogger("atc.hub")


class Hub:
    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        ctx.bus.subscribe(PHRASE, self.on_phrase)

    async def on_phrase(self, phrase: PhraseReady) -> None:
        rate, audio = await self._ctx.tts.synthesize(phrase.text)
        if self._ctx.settings.radio_fx and audio:
            audio = apply_radio_fx(audio, rate)
        targets = self._ctx.radio.listeners(phrase.frequency_mhz)
        if phrase.session_id not in targets:
            targets.append(phrase.session_id)
        for session_id in targets:
            session = self._ctx.sessions.get(session_id)
            if session is None:
                continue
            await session.play(phrase, audio, rate)
        origin = self._ctx.sessions.get(phrase.session_id)
        if origin is not None:
            origin.complete(phrase.exchange_id)
        log.info("spoke session=%s %r", phrase.session_id, phrase.text)
