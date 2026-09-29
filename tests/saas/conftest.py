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
