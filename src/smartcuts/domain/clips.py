"""Reglas de negocio sobre clips, compartidas por todas las estrategias."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from smartcuts.domain.models import ClipCandidate, Sentence, SignalSet

# Margen alrededor de la primera/última palabra para no cortar sílabas.
LEAD_IN = 0.15
TAIL_OUT = 0.35


def clip_bounds(sentences: list[Sentence], first: int, last: int, duration: float) -> tuple[float, float]:
    start = max(0.0, sentences[first].start - LEAD_IN)
    if first > 0:
        start = max(start, sentences[first - 1].end)
    end = min(duration, sentences[last].end + TAIL_OUT)
    if last + 1 < len(sentences):
        end = min(end, sentences[last + 1].start)
    return start, max(end, sentences[last].end)


def sentence_windows(
    sentences: list[Sentence], *, min_duration: float, max_duration: float
) -> Iterator[tuple[int, int]]:
    """Todos los rangos [i, j] de frases cuya duración cae dentro de los límites."""
    for i in range(len(sentences)):
        for j in range(i, len(sentences)):
            span = sentences[j].end - sentences[i].start
            if span > max_duration:
                break
            if span >= min_duration:
                yield i, j


def signal_score(
    signals: SignalSet, weights: dict[str, float], start: float, end: float
) -> tuple[float, dict[str, float]]:
    """Media ponderada de las señales disponibles; renormaliza si falta alguna."""
    parts: dict[str, float] = {}
    total_w = 0.0
    acc = 0.0
    for name, weight in weights.items():
        signal = signals.signals.get(name)
        if signal is None or weight <= 0:
            continue
        value = signal.mean_between(start, end)
        if value is None:
            continue
        parts[name] = round(value, 4)
        acc += weight * value
        total_w += weight
    return (acc / total_w if total_w else 0.0), parts


def overlaps_any(start: float, end: float, ranges: list[tuple[float, float]], gap: float = 0.0) -> bool:
    return any(start < b + gap and a < end + gap for a, b in ranges)


def pick_non_overlapping(
    candidates: Iterable[ClipCandidate], limit: int, *, min_gap: float = 0.0
) -> list[ClipCandidate]:
    """Greedy por puntuación: el mejor primero, descartando los que solapan."""
    chosen: list[ClipCandidate] = []
    for cand in sorted(candidates, key=lambda c: c.score, reverse=True):
        if any(cand.start < c.end + min_gap and c.start < cand.end + min_gap for c in chosen):
            continue
        chosen.append(cand)
        if len(chosen) >= limit:
            break
    return chosen
