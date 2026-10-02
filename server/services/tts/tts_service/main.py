import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

from .config import Settings, get_settings
from .engine import build_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tts")


class SpeakRequest(BaseModel):
    text: str


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current = app.state.settings
        engine = build_engine(current)
        load = getattr(engine, "load", None)
        if callable(load):
            log.info("loading TTS provider %s", current.provider)
            await asyncio.to_thread(load)
        app.state.engine = engine
        yield

    app = FastAPI(title="ATC TTS", lifespan=lifespan)
    app.state.settings = settings or get_settings()

    @app.get("/health")
    async def health() -> dict:
        engine = getattr(app.state, "engine", None)
        rate = getattr(engine, "sample_rate", app.state.settings.sample_rate)
        return {"status": "ok", "provider": app.state.settings.provider, "sample_rate": rate}

    @app.post("/v1/synthesize")
    async def synthesize(body: SpeakRequest) -> Response:
        engine = app.state.engine
        parts: list[bytes] = []
        async for chunk in engine.synthesize(body.text):
            parts.append(chunk)
        audio = b"".join(parts)
        rate = int(getattr(engine, "sample_rate", app.state.settings.sample_rate))
        return Response(content=audio, media_type="application/octet-stream", headers={"X-Sample-Rate": str(rate)})

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("tts_service.main:app", host="0.0.0.0", port=get_settings().port, reload=False)


if __name__ == "__main__":
    run()
