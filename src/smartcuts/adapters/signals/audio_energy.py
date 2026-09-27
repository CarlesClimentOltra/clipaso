"""Energía (volumen RMS en dB) del audio: picos de intensidad/emoción."""

from __future__ import annotations

import wave
from typing import Any

import numpy as np

from smartcuts.adapters.signals._util import robust_normalize
from smartcuts.domain.models import Signal
from smartcuts.domain.ports import AnalysisContext
from smartcuts.infra.registry import register


@register("signals", "audio_energy")
class AudioEnergySignal:
    name = "audio_energy"

    def __init__(self, step: float = 0.5, **_: Any) -> None:
        self.step = step

    def extract(self, ctx: AnalysisContext) -> Signal | None:
        with wave.open(str(ctx.audio_path), "rb") as wav:
            rate = wav.getframerate()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        if samples.size == 0:
            return None
        window = int(rate * self.step)
        n = samples.size // window
        frames = samples[: n * window].astype(np.float32).reshape(n, window) / 32768.0
        rms = np.sqrt(np.mean(frames**2, axis=1))
        db = 20 * np.log10(np.maximum(rms, 1e-5))
        return Signal(name=self.name, step=self.step, values=robust_normalize(db))
