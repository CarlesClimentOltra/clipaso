"""Transcripción local con faster-whisper (CTranslate2).

Con `device="auto"` usa la GPU si CUDA está operativo y cae a CPU si no.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from smartcuts.domain.errors import TranscriptionError
from smartcuts.domain.models import Transcript, Word
from smartcuts.domain.segmentation import build_sentences
from smartcuts.infra.cuda import cuda_device_count, register_nvidia_dlls
from smartcuts.infra.logging import get_logger
from smartcuts.infra.registry import register

log = get_logger(__name__)


@register("transcribers", "faster_whisper")
class FasterWhisperTranscriber:
    name = "faster_whisper"

    def __init__(
        self,
        model: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "int8_float16",
        cpu_compute_type: str = "int8",
        beam_size: int = 5,
        vad_filter: bool = True,
        **_: Any,
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.cpu_compute_type = cpu_compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            self._model = self._create_model()
        return self._model

    def _create_model(self) -> Any:
        register_nvidia_dlls()
        from faster_whisper import WhisperModel

        attempts: list[tuple[str, str]] = []
        if self.device in ("auto", "cuda") and cuda_device_count() > 0:
            attempts.append(("cuda", self.compute_type))
        if self.device in ("auto", "cpu"):
            attempts.append(("cpu", self.cpu_compute_type))
        if not attempts:
            raise TranscriptionError("Se pidió device=cuda pero no hay GPU CUDA disponible")

        last_error: Exception | None = None
        for device, compute_type in attempts:
            try:
                model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
                log.info("whisper.loaded", model=self.model_name, device=device, compute_type=compute_type)
                return model
            except Exception as exc:  # CUDA mal instalado, sin VRAM, etc.
                log.warning("whisper.load_failed", device=device, error=str(exc))
                last_error = exc
        raise TranscriptionError("No se pudo cargar Whisper", detail=str(last_error))

    def transcribe(
        self, audio_path: Path, language: str | None, on_progress: Callable[[float], None] | None = None
    ) -> Transcript:
        model = self._load()
        t0 = time.monotonic()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=self.beam_size,
                word_timestamps=True,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,  # reduce alucinaciones repetitivas
            )
            words: list[Word] = []
            last_log = t0
            for seg in segments:  # generador: la transcripción ocurre al iterar
                for w in seg.words or []:
                    words.append(Word(text=w.word, start=w.start, end=w.end, probability=w.probability))
                if on_progress and info.duration:
                    on_progress(min(seg.end / info.duration, 1.0))
                if time.monotonic() - last_log > 15:
                    last_log = time.monotonic()
                    log.info("whisper.progress", at=f"{seg.end / 60:.1f} min",
                             total=f"{info.duration / 60:.1f} min")
        except Exception as exc:
            raise TranscriptionError("Falló la transcripción", detail=str(exc)) from exc

        elapsed = time.monotonic() - t0
        log.info("whisper.done", words=len(words), seconds=round(elapsed, 1),
                 speed=f"{info.duration / max(elapsed, 0.1):.1f}x", language=info.language)
        return Transcript(
            language=info.language,
            duration=info.duration,
            sentences=build_sentences(words),
        )
