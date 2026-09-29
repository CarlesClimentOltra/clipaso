"""Agrupa palabras con marca de tiempo en frases cortables.

Whisper devuelve segmentos de hasta ~30 s que no respetan frases. Aquí se
reconstruyen frases usando la puntuación y las pausas, para que cualquier
clip empiece y termine en un límite natural del habla.
"""

from __future__ import annotations

from collections.abc import Iterable

from clipaso.domain.models import Sentence, Word

SENTENCE_END = (".", "?", "!", "…")


def _join(words: list[Word]) -> str:
    return "".join(w.text if w.text.startswith(" ") else f" {w.text}" for w in words).strip()


def build_sentences(
    words: Iterable[Word],
    *,
    pause_split: float = 0.7,
    max_duration: float = 14.0,
    min_duration: float = 1.0,
) -> list[Sentence]:
    groups: list[list[Word]] = []
    current: list[Word] = []

    for word in words:
        if current:
            gap = word.start - current[-1].end
            too_long = word.end - current[0].start > max_duration
            long_enough = current[-1].end - current[0].start >= min_duration
            ended = current[-1].text.strip().endswith(SENTENCE_END)
            if (ended and long_enough) or gap >= pause_split or too_long:
                groups.append(current)
                current = []
        current.append(word)
    if current:
        groups.append(current)

    return [
        Sentence(index=i, start=g[0].start, end=g[-1].end, text=_join(g), words=g)
        for i, g in enumerate(groups)
    ]
