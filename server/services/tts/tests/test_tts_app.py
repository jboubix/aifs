from fastapi.testclient import TestClient
from tts_service.config import Settings
from tts_service.kokoro_tts import for_speech
from tts_service.main import create_app


def test_stub_returns_pcm():
    settings = Settings(_env_file=None, provider="stub", sample_rate=24000)
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
        assert health["provider"] == "stub"
        assert health["sample_rate"] == 24000
        response = client.post("/v1/synthesize", json={"text": "climb and maintain 5000"})
        assert response.status_code == 200
        assert response.headers["x-sample-rate"] == "24000"
        assert len(response.content) > 0 and len(response.content) % 2 == 0


def test_kokoro_speech_text_is_lowercase():
    assert for_speech("TOWER NOVEMBER ONE") == "tower november one."
    assert for_speech("  already done.  ") == "already done."
    assert for_speech("   ") == ""
    assert for_speech("climb and maintain 5000") == "climb and maintain five thousand."
