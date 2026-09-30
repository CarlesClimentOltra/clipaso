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
        "watermark": True, "max_export_quality": "1080p", "daily_thumbnails": 5,
    },
    {
        "code": "pro", "name": "Pro", "price_eur_cents": 1900, "sort_order": 1,
        "monthly_minutes": 300, "max_video_minutes": 90, "max_clips_per_job": 10,
        "max_concurrent_jobs": 2, "max_upload_mb": 10240, "retention_days": 30,
        "watermark": False, "max_export_quality": "1080p", "daily_thumbnails": 40,
    },
    {
        "code": "ultra", "name": "Ultra", "price_eur_cents": 4900, "sort_order": 2,
        "monthly_minutes": 1000, "max_video_minutes": 180, "max_clips_per_job": 20,
        "max_concurrent_jobs": 4, "max_upload_mb": 25600, "retention_days": 60,
        "watermark": False, "max_export_quality": "2160p", "daily_thumbnails": 150,
    },
    {
        # Cuenta de desarrollo (no se vende): sin cuota ni límites, para probarlo todo. Se asigna a los emails
        # de `CLIPASO_ADMIN_EMAILS`, que además ven el panel de costes.
        "code": "dev", "name": "Desarrollador", "price_eur_cents": 0, "sort_order": 99, "is_public": False,
        "monthly_minutes": 100_000, "max_video_minutes": 600, "max_clips_per_job": 50,
        "max_concurrent_jobs": 10, "max_upload_mb": 51200, "retention_days": 90,
        "watermark": False, "max_export_quality": "2160p", "daily_thumbnails": 10_000, "unlimited": True,
    },
]

DEFAULT_PLAN = "free"
DEV_PLAN = "dev"


def sync_plans(session: Session) -> None:
    """Crea o actualiza los planes del catálogo (idempotente; se ejecuta al arrancar)."""
    codes = {data["code"] for data in PLANS}
    for plan in session.query(Plan).filter(Plan.code.not_in(codes)):
        plan.is_public = False  # planes retirados (p. ej. «creator»): quien lo tenga lo conserva, pero no se ofrece
    for data in PLANS:
        data = {"is_public": True, "unlimited": False, **data}
        plan = session.get(Plan, data["code"])
        if plan is None:
            session.add(Plan(**data))
        else:
            for key, value in data.items():
                setattr(plan, key, value)
