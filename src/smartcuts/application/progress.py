"""Progreso global del pipeline a partir del avance de cada etapa.

Las etapas pesan distinto (transcribir es lo más lento), así que el progreso
global se calcula con pesos aproximados. El consumidor (CLI, worker SaaS)
recibe `(stage, overall)` con `overall` en 0..1 y siempre creciente.
"""

from __future__ import annotations

from collections.abc import Callable

ProgressCallback = Callable[[str, float], None]

# Orden y peso relativo de cada etapa.
STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 0.04,
    "audio": 0.03,
    "transcribe": 0.43,
    "signals": 0.03,
    "select": 0.17,
    "export": 0.30,
}


class ProgressReporter:
    def __init__(self, callback: ProgressCallback | None = None) -> None:
        self.callback = callback
        self._last = 0.0

    def report(self, stage: str, fraction: float = 0.0) -> None:
        if self.callback is None:
            return
        done = 0.0
        for name, weight in STAGE_WEIGHTS.items():
            if name == stage:
                done += weight * max(0.0, min(1.0, fraction))
                break
            done += weight
        overall = max(self._last, min(done, 1.0))
        self._last = overall
        self.callback(stage, round(overall, 4))

    def stage_callback(self, stage: str) -> Callable[[float], None]:
        """Callback de fracción para pasar a un componente (p. ej. el transcriptor)."""
        return lambda fraction: self.report(stage, fraction)
