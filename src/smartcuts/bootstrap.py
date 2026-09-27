"""Composition root: traduce la configuración en componentes concretos.

Es el único sitio que sabe qué implementación va detrás de cada puerto.
La CLI, la API y el worker llaman a `build_pipeline()` / `build_storage()` y nada más.
"""

from __future__ import annotations

import smartcuts.adapters  # noqa: F401  (registra todos los adaptadores)
from smartcuts.application.cost import CostTracker
from smartcuts.application.pipeline import Components, Pipeline
from smartcuts.domain.ports import Storage, Transcriber
from smartcuts.infra import registry
from smartcuts.infra.config import Settings


def build_components(
    settings: Settings, strategy: str | None = None, transcriber: Transcriber | None = None
) -> Components:
    cost = CostTracker(budget_usd=settings.budget.max_usd_per_job, pricing=settings.budget.pricing)

    # Versión comercial: solo archivos subidos por el usuario (sin descargas de plataformas).
    sources = [registry.create("sources", "local")]

    t = settings.transcription
    transcriber_params = t.model_dump(exclude={"provider"})
    # Un worker de larga vida reutiliza el transcriptor (y el modelo Whisper ya cargado en memoria).
    transcriber = transcriber or registry.create("transcribers", t.provider, **transcriber_params)

    signals = [registry.create("signals", name) for name in settings.selection.signals]

    sel = settings.selection
    strategy = strategy or sel.strategy
    selector_kwargs = {"weights": sel.weights, "llm_weight": sel.llm_weight, "min_gap_seconds": sel.min_gap_seconds}
    selector_params = dict(selector_kwargs)
    if strategy != "heuristic":
        llm = registry.create("llm", settings.llm.provider, **settings.llm.model_dump(exclude={"provider"}))
        selector_kwargs |= {"llm": llm, "cost": cost}
        selector_params |= {"llm_provider": settings.llm.provider, "llm_model": llm.model,
                            "effort": settings.llm.effort}
    selector = registry.create("selectors", strategy, **selector_kwargs)
    fallback = (
        registry.create("selectors", sel.fallback_strategy, weights=sel.weights, min_gap_seconds=sel.min_gap_seconds)
        if sel.fallback_strategy
        else None
    )

    def reframer_factory(mode: str):
        return registry.create(
            "reframers", mode, fallback_to_blur=(mode == "auto"), model_dir=settings.data_dir / "models"
        )

    def exporter_factory(name: str):
        return registry.create("exporters", name)

    return Components(
        sources=sources,
        transcriber=transcriber,
        transcriber_params=transcriber_params,
        signals=signals,
        selector=selector,
        selector_params=selector_params,
        fallback_selector=fallback,
        reframer_factory=reframer_factory,
        exporter_factory=exporter_factory,
        cost=cost,
    )


def build_pipeline(
    settings: Settings, strategy: str | None = None, transcriber: Transcriber | None = None
) -> Pipeline:
    return Pipeline(build_components(settings, strategy, transcriber), settings.jobs_dir(), settings.output_dir)


def build_storage(settings: Settings) -> Storage:
    s = settings.storage
    if s.backend == "local":
        return registry.create(
            "storage", "local", root=settings.storage_root(), public_url=settings.api.public_url,
            secret_key=settings.api.secret_key,
        )
    return registry.create(
        "storage", "r2", account_id=s.r2_account_id, access_key_id=s.r2_access_key_id,
        secret_access_key=s.r2_secret_access_key, bucket=s.r2_bucket, jurisdiction=s.r2_jurisdiction,
    )
