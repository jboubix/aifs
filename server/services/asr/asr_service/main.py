import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .config import Settings, get_settings
from .engine import build_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("asr")


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        current = app.state.settings
        engine = build_engine(current)
        load = getattr(engine, "load", None)
        if callable(load):
            log.info("loading ASR provider %s", current.provider)
            await asyncio.to_thread(load)
        app.state.engine = engine
        yield

    app = FastAPI(title="ATC ASR", lifespan=lifespan)
    app.state.settings = settings or get_settings()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "provider": app.state.settings.provider}

    @app.post("/v1/transcribe")
    async def transcribe(request: Request, sample_rate: int = 16000, hint: str = "") -> dict:
        if sample_rate <= 0:
            raise HTTPException(status_code=400, detail="sample_rate must be positive")
        pcm = await request.body()
        engine = app.state.engine
        text = await engine.transcribe(pcm, sample_rate, hint)
        return {"text": text}

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("asr_service.main:app", host="0.0.0.0", port=get_settings().port, reload=False)


if __name__ == "__main__":
    run()
