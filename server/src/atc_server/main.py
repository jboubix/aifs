import asyncio
import contextlib
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect
from redis.asyncio import Redis

from . import __version__
from .bus import Bus
from .clearances import RedisClearanceRegistry
from .config import Settings, get_settings
from .context import AppContext, SessionRegistry
from .gateway.session import Session
from .radio import RadioDirectory
from .voice import AsrClient, TtsClient
from .weather import RedisWeatherCache
from .weather.ingest import run_weather_ingest
from .wiring import wire
from .world import RedisWorldStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("atc")


def _authorized(supplied: str, expected: str) -> bool:
    if len(supplied) != len(expected):
        return False
    return hmac.compare_digest(supplied, expected)


async def _build_context(app: FastAPI) -> tuple[AppContext, bool]:
    if app.state.ctx is not None:
        return app.state.ctx, False
    settings: Settings = app.state.settings or get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis.ping()
    ctx = AppContext(
        settings=settings,
        bus=Bus(),
        world=RedisWorldStore(redis),
        clearances=RedisClearanceRegistry(redis),
        weather=RedisWeatherCache(redis),
        asr=AsrClient(settings.asr_url, settings.voice_timeout_s),
        tts=TtsClient(settings.tts_url, settings.voice_timeout_s),
        sessions=SessionRegistry(),
        radio=RadioDirectory(),
        redis=redis,
    )
    return ctx, True


def create_app(settings: Settings | None = None, ctx: AppContext | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        built, owns_redis = await _build_context(app)
        app.state.ctx = built
        weather_task: asyncio.Task | None = None
        try:
            await built.asr.open()
            await built.tts.open()
            tts_health = await built.tts.health()
            await built.asr.health()
            rate = tts_health.get("sample_rate")
            built.output_sample_rate = int(rate or built.settings.output_sample_rate)
            wire(built)
            if built.settings.weather_ingest:
                weather_task = asyncio.create_task(run_weather_ingest(built))
            log.info("ready")
            yield
        finally:
            if weather_task is not None:
                weather_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await weather_task
            await built.asr.aclose()
            await built.tts.aclose()
            if owns_redis and built.redis is not None:
                await built.redis.aclose()

    app = FastAPI(title="MSFS AI ATC server", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.ctx = ctx

    @app.get("/health")
    async def health():
        current: AppContext = app.state.ctx
        redis_status = "memory"
        if current.redis is not None:
            try:
                await current.redis.ping()
                redis_status = "ok"
            except Exception:
                log.exception("redis health failed")
                redis_status = "down"
        asr_status, asr_provider = "down", ""
        tts_status, tts_provider = "down", ""
        try:
            body = await current.asr.health()
            asr_status = "ok"
            asr_provider = str(body.get("provider", ""))
        except Exception:
            log.exception("asr health failed")
        try:
            body = await current.tts.health()
            tts_status = "ok"
            tts_provider = str(body.get("provider", ""))
        except Exception:
            log.exception("tts health failed")
        ok = redis_status in ("ok", "memory") and asr_status == "ok" and tts_status == "ok"
        payload = {
            "status": "ok" if ok else "degraded",
            "version": __version__,
            "redis": redis_status,
            "asr": asr_status,
            "tts": tts_status,
            "asr_provider": asr_provider,
            "tts_provider": tts_provider,
            "reply": current.settings.reply_mode,
        }
        return JSONResponse(payload, status_code=200 if ok else 503)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        current: AppContext = app.state.ctx
        token = current.settings.auth_token
        if token:
            supplied = ws.query_params.get("token", "")
            if not _authorized(supplied, token):
                await ws.close(code=4401)
                return
        await ws.accept()
        session = Session(ws, current)
        current.sessions.add(session)
        log.info("[%s] connected", session.id)
        try:
            await session.run()
        except WebSocketDisconnect:
            pass
        finally:
            await session.shutdown()
            log.info("[%s] disconnected", session.id)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("atc_server.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
