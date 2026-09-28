"""Archivos que acompañan a un proyecto además de sus clips.

- `transcript.json` y `signals.json`: el análisis del vídeo. Permiten editar subtítulos, descargar
  SRT/VTT y pedir más clips sin volver a transcribir.
- `preview.mp4`: versión ligera (360p) del vídeo original para el editor del navegador. Solo existe
  si el usuario decide conservar el original.
- `brand/<usuario>/logo.png`: logo de la marca personal.

Todo vive bajo el prefijo del proyecto (o del usuario), así que se borra junto con él.
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

from smartcuts.domain.errors import SmartCutsError
from smartcuts.domain.models import SignalSet, Transcript, Word
from smartcuts.domain.ports import Storage
from smartcuts.infra import ffmpeg
from smartcuts.infra.logging import get_logger
from smartcuts.saas.services import job_prefix, user_folder

log = get_logger(__name__)

PREVIEW_HEIGHT = 360


def transcript_key(user_id: str, job_id: str) -> str:
    return job_prefix(user_id, job_id) + "transcript.json"


def signals_key(user_id: str, job_id: str) -> str:
    return job_prefix(user_id, job_id) + "signals.json"


def preview_key(user_id: str, job_id: str) -> str:
    return job_prefix(user_id, job_id) + "preview.mp4"


def logo_key(user_id: str) -> str:
    return f"brand/{user_folder(user_id)}/logo.png"


def save_analysis(storage: Storage, user_id: str, job_id: str, transcript: Transcript, signals: SignalSet) -> None:
    storage.put_bytes(transcript_key(user_id, job_id), transcript.model_dump_json().encode(), "application/json")
    storage.put_bytes(signals_key(user_id, job_id), signals.model_dump_json().encode(), "application/json")


@lru_cache(maxsize=16)
def _cached_transcript(storage: Storage, key: str) -> Transcript | None:
    raw = storage.read_bytes(key)
    return Transcript.model_validate_json(raw) if raw else None


def load_transcript(storage: Storage, user_id: str, job_id: str) -> Transcript | None:
    """La transcripción de un proyecto no cambia nunca: se cachea en memoria."""
    return _cached_transcript(storage, transcript_key(user_id, job_id))


def load_signals(storage: Storage, user_id: str, job_id: str) -> SignalSet | None:
    raw = storage.read_bytes(signals_key(user_id, job_id))
    return SignalSet.model_validate_json(raw) if raw else None


def edit_key(start: float) -> str:
    """Clave estable de una palabra: su inicio en milisegundos."""
    return str(int(round(start * 1000)))


def word_keys(transcript: Transcript) -> dict[int, str]:
    """Clave de cada palabra (por `id`): su inicio en ms; si varias empiezan a la vez, «ms.1», «ms.2»…"""
    keys: dict[int, str] = {}
    seen: dict[str, int] = {}
    for s in transcript.sentences:
        for w in s.words:
            base = edit_key(w.start)
            n = seen.get(base, 0)
            seen[base] = n + 1
            keys[id(w)] = base if n == 0 else f"{base}.{n}"
    return keys


def apply_edits(transcript: Transcript, edits: dict[str, str]) -> Transcript:
    """Copia de la transcripción con las palabras corregidas por el usuario (texto vacío = quitarla)."""
    if not edits:
        return transcript
    keys = word_keys(transcript)
    sentences = []
    for s in transcript.sentences:
        words: list[Word] = []
        for w in s.words:
            text = edits.get(keys[id(w)], w.text)
            if text.strip():
                words.append(w.model_copy(update={"text": text if text.startswith(" ") else f" {text.strip()}"}))
        sentences.append(s.model_copy(update={"words": words}))
    return transcript.model_copy(update={"sentences": sentences})


def make_preview(source: Path, dest: Path) -> Path | None:
    """Vídeo ligero para el editor. Si falla, el editor funciona igual con los clips (sin previsualizar el corte)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-i", str(source), "-vf", f"scale=-2:{PREVIEW_HEIGHT}", "-r", "24",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(dest),
    ]
    try:
        ffmpeg.run(args, what="vista previa para el editor")
        return dest
    except SmartCutsError as exc:
        log.warning("preview.failed", error=str(exc))
        dest.unlink(missing_ok=True)
        return None


class SourceCache:
    """Guarda en disco los últimos originales descargados: editar varios clips seguidos del mismo
    proyecto (mismo contenedor de Modal) no vuelve a descargar un vídeo de varios GB."""

    def __init__(self, root: Path, keep: int = 2) -> None:
        self.root = root
        self.keep = keep

    def get(self, storage: Storage, key: str, suffix: str) -> Path:
        local = storage.local_path(key)
        if local is not None:
            return local
        self.root.mkdir(parents=True, exist_ok=True)
        name = key.replace("/", "_")
        path = self.root / f"{name}{suffix}"
        if not path.exists():
            partial = path.with_suffix(".part")
            storage.download_to(key, partial)
            partial.replace(path)
        path.touch()
        others = sorted((p for p in self.root.iterdir() if p != path), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in others[self.keep - 1:]:
            if old.is_dir():
                shutil.rmtree(old, ignore_errors=True)
            else:
                old.unlink(missing_ok=True)
        return path
