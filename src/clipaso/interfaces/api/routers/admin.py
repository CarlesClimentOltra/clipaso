"""Panel de costes (solo cuentas de desarrollo): lo que cuesta de verdad cada modo, para ajustar los planes."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from clipaso.interfaces.api.deps import SessionDep, SettingsDep, UserDep
from clipaso.interfaces.api.schemas import AdminDuplicateOut, AdminJobOut, AdminModeOut, AdminUsageOut
from clipaso.saas import services
from clipaso.saas.db import utcnow
from clipaso.saas.errors import NotFound
from clipaso.saas.models import Job, Task, User
from clipaso.saas.plans import DEFAULT_PLAN

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage", response_model=AdminUsageOut)
def usage(user: UserDep, session: SessionDep, settings: SettingsDep,
          days: int = Query(30, ge=1, le=365)) -> AdminUsageOut:
    if not services.is_admin(user):
        raise NotFound()  # para el resto de usuarios, esta ruta no existe
    since = utcnow() - timedelta(days=days)
    costs = settings.costs
    jobs = session.scalars(select(Job).where(Job.created_at >= since).order_by(Job.created_at.desc())).all()
    tasks = session.scalars(select(Task).where(Task.created_at >= since)).all()
    owners = {u.id: u for u in session.scalars(select(User).where(User.id.in_({j.user_id for j in jobs})))}
    emails = {uid: u.email for uid, u in owners.items()}

    modes: dict[str, dict] = {}
    rows: list[AdminJobOut] = []
    for job in jobs:
        m = job.metrics or {}
        mode = (job.options or {}).get("mode", "clips")
        compute, llm = float(m.get("compute_usd", 0.0)), float(job.llm_cost_usd or 0.0)
        agg = modes.setdefault(mode, {"mode": mode, "jobs": 0, "measured": 0, "minutes": 0.0, "worker_s": 0.0,
                                      "compute_usd": 0.0, "llm_usd": 0.0, "source_mb": 0.0})
        agg["jobs"] += 1
        agg["minutes"] += job.video_minutes or 0.0
        agg["llm_usd"] += llm
        if m:
            agg["measured"] += 1
            agg["worker_s"] += float(m.get("worker_s", 0.0))
            agg["compute_usd"] += compute
            agg["source_mb"] += float(m.get("source_mb", 0.0))
        rows.append(AdminJobOut(
            id=job.id, created_at=job.created_at, user=emails.get(job.user_id, ""), mode=mode, status=job.status,
            title=job.title, minutes=job.video_minutes or 0.0, source_mb=m.get("source_mb"),
            source_res=m.get("source_res"), worker_s=m.get("worker_s"), cpu_s=m.get("cpu_s"),
            compute_usd=compute if m else None, llm_usd=llm, stages=m.get("stages") or {},
        ))
    task_usd = sum(float((t.metrics or {}).get("compute_usd", 0.0)) for t in tasks)
    out_modes = []
    for agg in sorted(modes.values(), key=lambda a: -a["jobs"]):
        total = agg["compute_usd"] + agg["llm_usd"]
        per_min = total / agg["minutes"] if agg["minutes"] else None
        out_modes.append(AdminModeOut(**agg, usd_per_minute=round(per_min, 4) if per_min is not None else None))
    return AdminUsageOut(
        days=days, jobs=len(jobs), tasks=len(tasks),
        compute_usd=round(sum(a["compute_usd"] for a in modes.values()) + task_usd, 4),
        llm_usd=round(sum(a["llm_usd"] for a in modes.values()), 4), task_compute_usd=round(task_usd, 4),
        modes=out_modes, recent=rows[:100], duplicates=duplicates(jobs, owners), rates=costs.model_dump(),
    )


def duplicates(jobs: list[Job], owners: dict[str, User]) -> list[AdminDuplicateOut]:
    """Mismo vídeo (peso y duración) procesado por varias cuentas gratis: posible abuso del plan gratis."""
    groups: dict[str, list[Job]] = {}
    for job in jobs:
        fp = (job.options or {}).get("source_fp")
        owner = owners.get(job.user_id)
        if fp and owner is not None and owner.plan_code == DEFAULT_PLAN:
            groups.setdefault(fp, []).append(job)
    out = []
    for group in groups.values():
        users = sorted({owners[j.user_id].email for j in group})
        if len(users) >= 2:
            out.append(AdminDuplicateOut(title=group[0].title, minutes=group[0].video_minutes or 0.0, users=users,
                                         jobs=len(group), last_at=max(j.created_at for j in group)))
    return sorted(out, key=lambda d: d.last_at, reverse=True)
