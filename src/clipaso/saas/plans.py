"""Catálogo de planes.

Los precios son provisionales: todavía no se cobra. Cuando se integre Stripe
se rellenará `stripe_price_id` y el webhook actualizará `users.plan_code`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from clipaso.saas.models import Plan

PLANS: list[dict] = [
    {
        "code": "free", "name": "Gratis", "price_eur_cents": 0, "sort_order": 0,
        "monthly_minutes": 30, "max_video_minutes": 20, "max_clips_per_job": 3,
        "max_concurrent_jobs": 1, "max_upload_mb": 2048, "retention_days": 7,
        "watermark": False,  # todavía sin decidir en qué planes va la marca de agua
    },
    {
        "code": "creator", "name": "Creator", "price_eur_cents": 1900, "sort_order": 1,
        "monthly_minutes": 300, "max_video_minutes": 90, "max_clips_per_job": 8,
        "max_concurrent_jobs": 2, "max_upload_mb": 10240, "retention_days": 30, "watermark": False,
    },
    {
        "code": "pro", "name": "Pro", "price_eur_cents": 4900, "sort_order": 2,
        "monthly_minutes": 1200, "max_video_minutes": 180, "max_clips_per_job": 15,
        "max_concurrent_jobs": 3, "max_upload_mb": 20480, "retention_days": 60, "watermark": False,
    },
]

DEFAULT_PLAN = "free"


def sync_plans(session: Session) -> None:
    """Crea o actualiza los planes del catálogo (idempotente; se ejecuta al arrancar)."""
    for data in PLANS:
        plan = session.get(Plan, data["code"])
        if plan is None:
            session.add(Plan(**data))
        else:
            for key, value in data.items():
                setattr(plan, key, value)
