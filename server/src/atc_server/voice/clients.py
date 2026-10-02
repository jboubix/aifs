"""HTTP clients for the ASR and TTS processes. Audio stays off the bus."""

import httpx


class AsrClient:
    def __init__(self, base_url: str, timeout_s: float = 120.0, http: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._http = http
        self._owned = http is None

    async def open(self) -> None:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
            self._owned = True

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def health(self) -> dict:
        response = await self._client().get("/health", timeout=5)
        response.raise_for_status()
        return response.json()

    async def transcribe(self, pcm16: bytes, sample_rate: int, hint: str = "") -> str:
        response = await self._client().post(
            "/v1/transcribe",
            content=pcm16,
            headers={"Content-Type": "application/octet-stream"},
            params={"sample_rate": sample_rate, "hint": hint},
        )
        response.raise_for_status()
        return str(response.json().get("text", "")).strip()

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("ASR client is not open")
        return self._http


class TtsClient:
    def __init__(self, base_url: str, timeout_s: float = 120.0, http: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._http = http
        self._owned = http is None

    async def open(self) -> None:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
            self._owned = True

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def health(self) -> dict:
        response = await self._client().get("/health", timeout=5)
        response.raise_for_status()
        return response.json()

    async def synthesize(self, text: str) -> tuple[int, bytes]:
        response = await self._client().post("/v1/synthesize", json={"text": text})
        response.raise_for_status()
        rate = int(response.headers.get("X-Sample-Rate", "24000"))
        return rate, response.content

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("TTS client is not open")
        return self._http
