from asr_service.config import Settings
from asr_service.main import create_app
from fastapi.testclient import TestClient


def test_stub_transcribes_without_a_model():
    settings = Settings(_env_file=None, provider="stub", stub_text="request climb and maintain 5000")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["provider"] == "stub"
        response = client.post("/v1/transcribe", content=b"\x00\x00" * 1600, params={"sample_rate": 16000})
        assert response.status_code == 200
        assert response.json()["text"] == "request climb and maintain 5000"


def test_transcribe_rejects_bad_sample_rate():
    settings = Settings(_env_file=None, provider="stub", stub_text="x")
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/transcribe", content=b"\x00\x00", params={"sample_rate": 0})
        assert response.status_code == 400
