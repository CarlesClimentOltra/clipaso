"""Ritmo del habla (palabras/segundo) a partir de la transcripción.

Un ritmo alto y sin silencios suele indicar un momento animado; los huecos
sin voz puntúan 0.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from clipaso.adapters.signals._util import robust_normalize
from clipaso.domain.models import Signal
from clipaso.domain.ports import AnalysisContext
from clipaso.infra.registry import register


@register("signals", "speech_rate")
class SpeechRateSignal:
    name = "speech_rate"

    def __init__(self, step: float = 0.5, **_: Any) -> None:
        self.step = step

    def extract(self, ctx: AnalysisContext) -> Signal | None:
        sentences = ctx.transcript.sentences
        if not sentences:
            return None
        n = int(np.ceil(ctx.source.duration / self.step)) + 1
        rate = np.zeros(n, dtype=np.float32)
        for s in sentences:
            wps = len(s.words) / max(s.duration, 0.3)
            rate[int(s.start / self.step) : int(s.end / self.step) + 1] = wps
        return Signal(name=self.name, step=self.step, values=robust_normalize(rate, low_pct=5, high_pct=97))
