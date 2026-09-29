"""Selección sin LLM: ventanas de frases puntuadas con señales baratas.

Sirve como estrategia de coste cero y como respaldo cuando falla el LLM.
"""

from __future__ import annotations

import re
from typing import Any

from clipaso.domain.clips import clip_bounds, overlaps_any, pick_non_overlapping, sentence_windows, signal_score
from clipaso.domain.models import ClipCandidate, Selection
from clipaso.domain.ports import SelectionRequest
from clipaso.infra.registry import register

# Empezar con un conector suele indicar que falta contexto previo.
_WEAK_START = re.compile(r"^(y|e|pero|entonces|porque|que|o sea|bueno|pues|además|aunque)\b", re.IGNORECASE)


@register("selectors", "heuristic")
class HeuristicSelector:
    name = "heuristic"

    def __init__(self, weights: dict[str, float] | None = None, min_gap_seconds: float = 2.0, **_: Any) -> None:
        self.weights = weights or {"audio_energy": 0.6, "speech_rate": 0.4}
        self.min_gap = min_gap_seconds

    def select(self, request: SelectionRequest) -> Selection:
        sentences = request.transcript.sentences
        profile = request.profile
        exclude = request.excluded_ranges()
        candidates: list[ClipCandidate] = []

        for first, last in sentence_windows(
            sentences, min_duration=profile.min_duration, max_duration=profile.max_duration
        ):
            start, end = clip_bounds(sentences, first, last, request.source.duration)
            if overlaps_any(start, end, exclude, self.min_gap):
                continue
            base, parts = signal_score(request.signals, self.weights, start, end)
            opening = sentences[first].text.strip()
            closing = sentences[last].text.strip()

            bonus = 0.0
            if "?" in opening:
                bonus += 0.05
            if _WEAK_START.match(opening):
                bonus -= 0.08
            if closing.endswith((".", "!", "?")):
                bonus += 0.03
            bonus -= 0.1 * abs((end - start) - profile.target_duration) / profile.target_duration

            score = max(0.0, min(1.0, base + bonus))
            candidates.append(
                ClipCandidate(
                    start=start,
                    end=end,
                    first_sentence=first,
                    last_sentence=last,
                    score=round(score, 4),
                    title=opening[:70],
                    hook=opening[:140],
                    reason="Puntuación por señales de audio/audiencia",
                    scores={**parts, "bonus": round(bonus, 4)},
                )
            )

        chosen = pick_non_overlapping(candidates, request.max_clips, min_gap=self.min_gap)
        notes = [f"señales usadas: {', '.join(request.signals.signals) or 'ninguna'}"]
        return Selection(strategy=self.name, clips=sorted(chosen, key=lambda c: c.start), notes=notes)
