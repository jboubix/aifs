"""One WebSocket connection: one pilot. Decisions are not made here."""

import asyncio
import json
import logging
import time
import uuid

from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

from ..bus import PHRASE, TELEMETRY, TRANSCRIPT
from ..context import AppContext
from ..contracts import AircraftState, PhraseReady, TranscriptFinal, new_id
from . import protocol as p
from .audio import chunk, pcm16_duration_s

log = logging.getLogger("atc.session")

MIN_PTT_SECONDS = 0.3


def transmit_frequency_mhz(telemetry: p.Telemetry) -> float:
    """COM1, unless COM2 is the only radio set to transmit."""
    if telemetry.com_transmit_2 and not telemetry.com_transmit_1:
        return telemetry.com2_active_mhz
    return telemetry.com1_active_mhz


class Session:
    def __init__(self, ws: WebSocket, ctx: AppContext) -> None:
        self.id = uuid.uuid4().hex[:8]
        self._ws = ws
        self._ctx = ctx
        self.hello = p.Hello()
        self.telemetry: p.Telemetry | None = None
        self._ptt: p.PttStart | None = None
        self._ptt_buf = bytearray()
        self._pipeline_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._send_lock = asyncio.Lock()
        self._waiters: dict[str, asyncio.Future] = {}

    async def run(self) -> None:
        await self.send(
            p.Welcome(
                session_id=self.id,
                input_sample_rate=self._ctx.settings.input_sample_rate,
                output_sample_rate=self._ctx.output_sample_rate,
            )
        )
        try:
            while True:
                msg = await self._ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    self._on_audio(msg["bytes"])
                elif msg.get("text") is not None:
                    await self.on_text(msg["text"])
        finally:
            for task in self._tasks:
                task.cancel()

    async def shutdown(self) -> None:
        self._ctx.radio.drop(self.id)
        self._ctx.sessions.remove(self.id)
        try:
            await self._ctx.world.delete(self.id)
            await self._ctx.clearances.delete(self.id)
        except Exception:
            log.exception("[%s] failed to drop session state", self.id)

    async def send(self, model: BaseModel) -> None:
        async with self._send_lock:
            await self._ws.send_text(model.model_dump_json())

    async def play(self, phrase: PhraseReady, audio: bytes, sample_rate: int) -> None:
        await self.send(p.TranscriptMsg(speaker="atc", text=phrase.text, frequency_mhz=phrase.frequency_mhz))
        await self.send(p.AudioStart(sample_rate=sample_rate, frequency_mhz=phrase.frequency_mhz))
        for part in chunk(audio):
            async with self._send_lock:
                await self._ws.send_bytes(part)
        await self.send(p.AudioEnd())

    def expect(self, exchange_id: str) -> None:
        loop = asyncio.get_running_loop()
        self._waiters[exchange_id] = loop.create_future()

    def complete(self, exchange_id: str) -> None:
        fut = self._waiters.get(exchange_id)
        if fut is not None and not fut.done():
            fut.set_result(None)

    def discard(self, exchange_id: str) -> None:
        fut = self._waiters.pop(exchange_id, None)
        if fut is not None and not fut.done():
            fut.cancel()

    async def wait(self, exchange_id: str) -> None:
        fut = self._waiters[exchange_id]
        try:
            await asyncio.wait_for(fut, self._ctx.settings.exchange_timeout_s)
        finally:
            self._waiters.pop(exchange_id, None)

    async def on_text(self, raw: str) -> None:
        try:
            obj = json.loads(raw)
            kind = obj.get("type")
            if kind == "hello":
                self.hello = p.Hello.model_validate(obj)
                log.info("[%s] hello callsign=%s", self.id, self.hello.callsign)
            elif kind == "telemetry":
                await self._on_telemetry(p.Telemetry.model_validate(obj))
            elif kind == "ptt_start":
                self._ptt = p.PttStart.model_validate(obj)
                self._ptt_buf.clear()
            elif kind == "ptt_end":
                self._finish_ptt()
            else:
                await self.send(p.ErrorMsg(message=f"unknown message type: {kind!r}"))
        except (json.JSONDecodeError, ValidationError, AttributeError) as exc:
            await self.send(p.ErrorMsg(message=f"bad message: {exc}"))

    async def _on_telemetry(self, telemetry: p.Telemetry) -> None:
        self.telemetry = telemetry
        state = self._snapshot(telemetry, transmit_frequency_mhz(telemetry))
        self._ctx.radio.tune(self.id, state.frequency_mhz)
        await self._ctx.world.upsert(state)
        # Inline so this sample is judged before the next message on the socket.
        # A corrective call speaks before the read loop continues.
        try:
            await self._ctx.bus.publish(TELEMETRY, state)
        except Exception:
            log.exception("[%s] telemetry handling failed", self.id)

    def _on_audio(self, data: bytes) -> None:
        if self._ptt is None:
            return
        settings = self._ctx.settings
        max_bytes = int(settings.max_ptt_seconds * settings.input_sample_rate * 2)
        if len(self._ptt_buf) + len(data) <= max_bytes:
            self._ptt_buf.extend(data)

    def _finish_ptt(self) -> None:
        ptt, pcm = self._ptt, bytes(self._ptt_buf)
        self._ptt = None
        self._ptt_buf.clear()
        if ptt is None:
            return
        if pcm16_duration_s(pcm, self._ctx.settings.input_sample_rate) < MIN_PTT_SECONDS:
            log.info("[%s] ignoring very short transmission", self.id)
            return
        task = asyncio.create_task(self._exchange(ptt, pcm))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _exchange(self, ptt: p.PttStart, pcm: bytes) -> None:
        async with self._pipeline_lock:
            try:
                await self._run_exchange(ptt, pcm)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("[%s] exchange failed", self.id)
                await self.send(p.ErrorMsg(message=f"{type(exc).__name__}: {exc}"))

    async def _run_exchange(self, ptt: p.PttStart, pcm: bytes) -> None:
        telemetry = self.telemetry
        freq = ptt.frequency_mhz or (transmit_frequency_mhz(telemetry) if telemetry else 0.0)
        self._ctx.radio.tune(self.id, freq)
        callsign = (telemetry.callsign if telemetry and telemetry.callsign else self.hello.callsign) or ""
        hint = f"Callsign: {callsign}." if callsign else ""
        text = await self._ctx.asr.transcribe(pcm, self._ctx.settings.input_sample_rate, hint)
        log.info("[%s] pilot: %s", self.id, text)
        await self.send(p.TranscriptMsg(speaker="pilot", text=text, frequency_mhz=freq))
        if not text:
            return

        exchange_id = new_id()
        self.expect(exchange_id)
        try:
            if self._ctx.settings.reply_mode == "echo":
                await self._ctx.bus.publish(
                    PHRASE,
                    PhraseReady(
                        exchange_id=exchange_id,
                        session_id=self.id,
                        frequency_mhz=freq,
                        text=text,
                    ),
                )
            else:
                await self._ctx.bus.publish(
                    TRANSCRIPT,
                    TranscriptFinal(
                        exchange_id=exchange_id,
                        session_id=self.id,
                        callsign=callsign,
                        frequency_mhz=freq,
                        text=text,
                    ),
                )
            await self.wait(exchange_id)
        except Exception:
            self.discard(exchange_id)
            raise

    def _snapshot(self, telemetry: p.Telemetry, frequency_mhz: float) -> AircraftState:
        callsign = telemetry.callsign or self.hello.callsign
        return AircraftState(
            session_id=self.id,
            callsign=callsign,
            latitude=telemetry.latitude,
            longitude=telemetry.longitude,
            altitude_msl_ft=telemetry.altitude_msl_ft,
            altitude_agl_ft=telemetry.altitude_agl_ft,
            heading_true=telemetry.heading_true,
            ground_speed_kt=telemetry.ground_speed_kt,
            indicated_airspeed_kt=telemetry.indicated_airspeed_kt,
            on_ground=telemetry.on_ground,
            frequency_mhz=frequency_mhz,
            transponder_code=telemetry.transponder_code,
            updated_unix=time.time(),
        )
