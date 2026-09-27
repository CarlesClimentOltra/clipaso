from __future__ import annotations

import numpy as np


def robust_normalize(values: np.ndarray, low_pct: float = 10, high_pct: float = 95) -> list[float]:
    """Escala a 0..1 usando percentiles, para que los picos aislados no aplasten el resto."""
    if values.size == 0:
        return []
    lo, hi = np.percentile(values, [low_pct, high_pct])
    if hi - lo < 1e-9:
        return [0.5] * int(values.size)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0).round(4).tolist()
