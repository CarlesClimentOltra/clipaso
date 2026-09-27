from __future__ import annotations

from pathlib import Path

import pytest

from smartcuts.domain.models import OutputProfile, Signal, SignalSet, SourceVideo, Transcript, Word
from smartcuts.domain.segmentation import build_sentences


def make_words(text: str, start: float = 0.0, wps: float = 2.5, gap_after_sentence: float = 0.3) -> list[Word]:
    """Palabras con tiempos sintéticos; añade una pausa tras cada fin de frase."""
    words, t = [], start
    for token in text.split():
        dur = 1 / wps
        words.append(Word(text=f" {token}", start=round(t, 3), end=round(t + dur * 0.9, 3)))
        t += dur
        if token.endswith((".", "?", "!")):
            t += gap_after_sentence
    return words


@pytest.fixture
def transcript() -> Transcript:
    parts = []
    for i in range(40):
        if i % 5 == 0:
            parts.append(f"¿Sabes qué pasó en la reunión número {i} del equipo?")
        else:
            parts.append(f"Esta es la frase {i} y cuenta algo interesante sobre el proyecto actual.")
    words = make_words(" ".join(parts))
    return Transcript(language="es", duration=words[-1].end + 1, sentences=build_sentences(words))


@pytest.fixture
def source(transcript: Transcript) -> SourceVideo:
    return SourceVideo(
        source_id="test", provider="local", uri="x.mp4", path=Path("x.mp4"),
        title="Prueba", duration=transcript.duration, width=1920, height=1080, fps=30,
    )


@pytest.fixture
def profile() -> OutputProfile:
    return OutputProfile(name="t", width=1080, height=1920, min_duration=15, max_duration=30, target_duration=20)


@pytest.fixture
def signals(transcript: Transcript) -> SignalSet:
    n = int(transcript.duration / 0.5) + 1
    # Pico de energía entre 60 s y 80 s.
    values = [1.0 if 60 <= i * 0.5 <= 80 else 0.2 for i in range(n)]
    return SignalSet(signals={"audio_energy": Signal(name="audio_energy", step=0.5, values=values)})
