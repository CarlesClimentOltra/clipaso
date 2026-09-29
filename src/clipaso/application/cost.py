"""Control de costes de servicios externos.

Todo adaptador que llame a un servicio de pago debe pasar por aquí: primero
`check()` con una estimación (bloquea si se superaría el presupuesto) y luego
`record()` con el consumo real. Es la base para facturación/cuotas futuras.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from clipaso.domain.errors import BudgetExceededError
from clipaso.domain.ports import LLMUsage
from clipaso.infra.logging import get_logger

log = get_logger(__name__)


@dataclass
class CostEntry:
    service: str
    detail: str
    usd: float


@dataclass
class CostTracker:
    budget_usd: float
    pricing: dict[str, tuple[float, float]]
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def spent(self) -> float:
        return sum(e.usd for e in self.entries)

    def llm_cost(
        self, model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0
    ) -> float:
        price_in, price_out = self.pricing.get(model, max(self.pricing.values()))
        return (
            input_tokens * price_in
            + cache_write * price_in * 1.25
            + cache_read * price_in * 0.1
            + output_tokens * price_out
        ) / 1_000_000

    def check(self, service: str, estimated_usd: float) -> None:
        if self.spent + estimated_usd > self.budget_usd:
            raise BudgetExceededError(
                f"{service}: coste estimado ${estimated_usd:.3f} superaría el presupuesto "
                f"(${self.spent:.3f} gastado de ${self.budget_usd:.2f})"
            )

    def record_llm(self, usage: LLMUsage) -> float:
        if not usage.billable:
            log.info("cost.llm", model=usage.model, input_tokens=usage.input_tokens,
                     output_tokens=usage.output_tokens, usd=0, billing="suscripción")
            self.entries.append(CostEntry("llm", f"{usage.model} (suscripción)", 0.0))
            return 0.0
        usd = self.llm_cost(
            usage.model, usage.input_tokens, usage.output_tokens, usage.cache_read_tokens, usage.cache_write_tokens
        )
        self.entries.append(
            CostEntry("llm", f"{usage.model} in={usage.input_tokens} out={usage.output_tokens}", usd)
        )
        log.info("cost.llm", model=usage.model, input_tokens=usage.input_tokens,
                 output_tokens=usage.output_tokens, usd=round(usd, 4), total_usd=round(self.spent, 4))
        return usd
