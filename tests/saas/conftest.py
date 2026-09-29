"""Fixtures de la API: vídeo de prueba real, configuración aislada y cliente HTTP."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clipaso.infra.config import Settings
from clipaso.interfaces.api.app import create_app


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """Vídeo real de 3 s (para que ffprobe lea su duración)."""
    path = tmp_path_factory.mktemp("media") / "charla.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264", "-c:a", "aac",
         str(path)],
        check=True,
    )
    return path


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


class FakeCoverLLM:
    """IA de portadas de mentira: elige el segundo candidato y un texto fijo (sin red)."""

    name, model, billable, supports_images = "fake", "claude-haiku-4-5", True, True

    def __init__(self):
        self.calls: list[dict] = []

    def estimate_input_tokens(self, text):
        return len(text) // 3

    def complete_json(self, *, system, user, schema, max_tokens=None, images=None):
        from clipaso.domain.ports import LLMResponse, LLMUsage

        self.calls.append({"system": system, "user": user, "images": len(images or [])})
        return LLMResponse(data={"frame": 1, "text": "Esto lo cambia todo", "highlight": 3},
                           usage=LLMUsage(model=self.model, input_tokens=1200, output_tokens=20))


@pytest.fixture(autouse=True)
def cover_llm(monkeypatch):
    """Las portadas no descargan el detector de caras ni llaman a la IA de verdad en los tests."""
    import clipaso.bootstrap
    from clipaso.saas import covers

    fake = FakeCoverLLM()
    monkeypatch.setattr(clipaso.bootstrap, "build_fast_llm", lambda settings: fake)
    monkeypatch.setattr(covers, "face_detector", lambda model_dir: None)
    return fake
