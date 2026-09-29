"""Único punto de contacto con ffmpeg/ffprobe."""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from clipaso.domain.errors import ConfigurationError, RenderError
from clipaso.infra.logging import get_logger

log = get_logger(__name__)


@lru_cache
def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise ConfigurationError("No se encuentra ffmpeg en el PATH.")
    return path


@lru_cache
def ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise ConfigurationError("No se encuentra ffprobe en el PATH.")
    return path


def run(args: list[str], *, cwd: Path | None = None, what: str = "ffmpeg") -> None:
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args]
    log.debug("ffmpeg.run", cmd=" ".join(cmd), cwd=str(cwd) if cwd else None)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise RenderError(f"{what} falló (código {proc.returncode})", detail=tail)


def _label(path: Path | str) -> str:
    return Path(path).name if isinstance(path, Path) else "el vídeo"


def probe(path: Path | str) -> dict:
    """Acepta una ruta local o una URL (p. ej. firmada de R2): ffprobe solo lee las cabeceras."""
    cmd = [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RenderError(f"ffprobe no pudo leer {_label(path)}", detail=proc.stderr[-2000:])
    return json.loads(proc.stdout)


def video_info(path: Path | str) -> tuple[int, int, float, float]:
    """(ancho, alto, fps, duración) del primer stream de vídeo."""
    data = probe(path)
    stream = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    if stream is None:
        raise RenderError(f"{_label(path)} no contiene vídeo")
    num, _, den = stream.get("avg_frame_rate", "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    duration = float(stream.get("duration") or data["format"].get("duration") or 0.0)
    width, height = int(stream["width"]), int(stream["height"])
    # Vídeos grabados en vertical con metadato de rotación.
    rotation = abs(int(float(stream.get("tags", {}).get("rotate", 0) or 0)))
    for side in stream.get("side_data_list", []):
        rotation = abs(int(float(side.get("rotation", rotation) or 0)))
    if rotation in (90, 270):
        width, height = height, width
    return width, height, fps or 30.0, duration


def audio_duration(path: Path | str) -> float:
    """Duración de un archivo de audio (o del audio de un vídeo). Error si no tiene audio."""
    data = probe(path)
    stream = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if stream is None:
        raise RenderError(f"{_label(path)} no contiene audio")
    return float(stream.get("duration") or data["format"].get("duration") or 0.0)


def extract_audio(video: Path, dest: Path, sample_rate: int = 16000) -> Path:
    """WAV mono PCM16: lo que necesitan tanto Whisper como el análisis de energía."""
    run(
        ["-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(dest)],
        what="extracción de audio",
    )
    return dest


def thumbnail(video: Path, dest: Path, at: float = 1.0, width: int = 540) -> Path:
    run(
        ["-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(dest)],
        what="miniatura",
    )
    return dest


@lru_cache
def nvenc_available() -> bool:
    """Comprueba con un encode real de 1 frame; que el encoder aparezca listado no basta."""
    try:
        run(
            ["-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-frames:v", "1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            what="prueba NVENC",
        )
        return True
    except (RenderError, ConfigurationError):
        return False
