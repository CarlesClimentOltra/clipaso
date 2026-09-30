"""Consumo real de cada proyecto y tarea: tiempo en el worker (por etapa), CPU y coste estimado.

Se guarda en `jobs.metrics` / `tasks.metrics` para el panel de administración y para ajustar los planes.
"""

from __future__ import annotations

import time

from clipaso.infra.config import CostSettings

try:
    import resource
except ImportError:  # Windows (desarrollo): solo se mide la CPU del propio proceso
    resource = None


def _cpu_seconds() -> float:
    """CPU del proceso y de sus hijos ya terminados (ffmpeg): lo que Modal cobra por núcleo."""
    if resource is None:
        return time.process_time()
    me, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime


class Meter:
    def __init__(self, costs: CostSettings) -> None:
        self.costs = costs
        self.t0 = self.t_stage = time.monotonic()
        self.cpu0 = _cpu_seconds()
        self.stage = "start"
        self.stages: dict[str, float] = {}

    def at(self, stage: str) -> None:
        """Empieza la etapa `stage` (cierra la anterior)."""
        if stage == self.stage:
            return
        now = time.monotonic()
        self.stages[self.stage] = self.stages.get(self.stage, 0.0) + now - self.t_stage
        self.stage, self.t_stage = stage, now

    def finish(self, **extra) -> dict:
        self.at("end")
        wall = time.monotonic() - self.t0
        cpu = max(0.0, _cpu_seconds() - self.cpu0)
        return {
            "worker_s": round(wall, 1),
            "cpu_s": round(cpu, 1),
            "stages": {k: round(v, 1) for k, v in self.stages.items() if k != "start" and v >= 0.05},
            "compute_usd": round(self.costs.compute_usd(wall, cpu), 5),
            **extra,
        }
