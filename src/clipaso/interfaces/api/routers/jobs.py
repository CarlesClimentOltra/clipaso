from __future__ import annotations

import zipfile
from collections.abc import Callable, Iterator

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from clipaso.application.pipeline import slugify
from clipaso.domain.ports import Storage
from clipaso.interfaces.api.deps import DispatcherDep, SessionDep, SettingsDep, StorageDep, UserDep
from clipaso.interfaces.api.schemas import (
    ArchiveOut,
    ClipOut,
    CoverOut,
    JobCreateIn,
    JobOptions,
    JobOut,
    JobSummary,
    MoreClipsIn,
    TaskOut,
    ThumbnailIn,
)
from clipaso.saas import editing, services, thumbnails
from clipaso.saas.db import utcnow
from clipaso.saas.dispatch import dispatch_job
from clipaso.saas.errors import AppError, NotFound, translate, user_message
from clipaso.saas.models import Clip, Job, TaskKind, User
from clipaso.saas.rendering import result_frame

router = APIRouter(prefix="/jobs", tags=["jobs"])


def clip_filename(job: Job, clip: Clip, ext: str) -> str:
    return f"{slugify(job.title)}-{clip.rank:02d}-{slugify(clip.title)}.{ext}"


def clip_out(clip: Clip, job: Job, storage: Storage, ttl: int) -> ClipOut:
    return ClipOut(
        id=clip.id, rank=clip.rank, title=clip.title, reason=clip.reason, description=clip.description or "",
        hashtags=list(clip.hashtags or []), rating=clip.rating, start=clip.start, end=clip.end,
        duration=round(clip.end - clip.start, 2), score=clip.score, status=clip.status,
        render_error=translate(clip.render_error), version=clip.version,
        # Las miniaturas hechas sin subir el vídeo no tienen vídeo.
        video_url=storage.signed_url(clip.video_key, expires=ttl) if clip.video_key else "",
        download_url=storage.signed_url(clip.video_key, expires=ttl, download_name=clip_filename(job, clip, "mp4"))
        if clip.video_key else "",
        thumbnail_url=storage.signed_url(clip.thumb_key, expires=ttl) if clip.thumb_key else None,
        cover=cover_out(clip, job, storage, ttl),
    )


def cover_out(clip: Clip, job: Job, storage: Storage, ttl: int) -> CoverOut | None:
    c = clip.cover
    if not c or not c.get("vertical"):
        return None
    base = clip_filename(job, clip, "jpg").removesuffix(".jpg")
    return CoverOut(
        text=c.get("text", ""), highlight=c.get("highlight"), template=c.get("template", "impacto"),
        time=c.get("time", clip.start), candidates=[x["time"] for x in c.get("candidates", [])],
        candidate_images=[storage.signed_url(x["key"], expires=ttl) if x.get("key") else None
                          for x in c.get("candidates", [])],
        vertical_url=storage.signed_url(c["vertical"], expires=ttl),
        horizontal_url=storage.signed_url(c["horizontal"], expires=ttl),
        vertical_download_url=storage.signed_url(c["vertical"], expires=ttl, download_name=f"{base}-portada-9x16.jpg"),
        horizontal_download_url=storage.signed_url(c["horizontal"], expires=ttl,
                                                   download_name=f"{base}-miniatura-16x9.jpg"),
        pending=bool(c.get("pending")),
    )


def _summary_fields(job: Job, storage: Storage, ttl: int) -> dict:
    covered = next((c for c in job.clips if (c.cover or {}).get("horizontal")), None)
    if (job.options or {}).get("mode") == "thumbnail" and covered is not None:
        return {**_summary_base(job, storage, ttl, None),
                "thumbnail_url": storage.signed_url(covered.cover["horizontal"], expires=ttl)}
    return _summary_base(job, storage, ttl, next((c for c in job.clips if c.thumb_key), None))


def _summary_base(job: Job, storage: Storage, ttl: int, first: Clip | None) -> dict:
    return dict(
        id=job.id, title=job.title, mode=(job.options or {}).get("mode", "clips"), status=job.status,
        stage=job.stage, progress=job.progress, video_minutes=job.video_minutes, clip_count=len(job.clips),
        thumbnail_url=storage.signed_url(first.thumb_key, expires=ttl) if first else None,
        created_at=job.created_at, finished_at=job.finished_at, expires_at=job.expires_at,
    )


def job_out(session: Session, job: Job, user: User, storage: Storage, ttl: int) -> JobOut:
    options = {k: v for k, v in (job.options or {}).items() if k in JobOptions.model_fields}
    can_edit = editing.source_available(session, job)
    task = editing.latest_task(session, job, TaskKind.MORE_CLIPS)
    return JobOut(
        **_summary_fields(job, storage, ttl),
        error_code=job.error_code,
        error_message=user_message(job.error_code),
        options=JobOptions.model_validate(options),
        clean_stats=(job.options or {}).get("clean_stats"),
        frame=result_frame(options),
        can_edit=can_edit,
        more_clips_available=editing.more_clips_available(job, user) if can_edit else 0,
        more_clips_task=TaskOut(status=task.status, error_message=user_message(task.error_code)) if task else None,
        clips=[clip_out(c, job, storage, ttl) for c in job.clips],
    )


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreateIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep, dispatcher: DispatcherDep,
) -> JobOut:
    now = utcnow()
    if body.mode == "thumbnail":  # las miniaturas no suben vídeo: van por POST /thumbnails
        raise AppError("validation_error")
    options = body.model_dump(include=set(JobOptions.model_fields))
    if options["caption_style"] is None:  # el estilo por defecto del usuario
        options["caption_style"] = editing.get_preferences(user)[0].model_dump()
    job = services.create_job(
        session, user, upload_id=body.upload_id, max_clips=body.max_clips, language=body.language, now=now,
        options=options, trim=(body.trim_start or 0.0, body.trim_end) if body.trim_end else None,
    )
    session.commit()  # el job debe existir antes de que un worker lo busque
    if dispatch_job(dispatcher, job, now):
        session.commit()
    return job_out(session, job, user, storage, settings.api.signed_url_ttl_seconds)


@router.post("/thumbnail", response_model=JobOut, status_code=201)
def create_thumbnail(
    body: ThumbnailIn, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep,
) -> JobOut:
    """Miniatura y portada de un vídeo sin subirlo: el navegador envía unos fotogramas y la IA elige y escribe."""
    job = thumbnails.create(
        session, storage, settings, user, filename=body.filename, topic=body.topic, language=body.language,
        branding=body.branding, frames=[(f.time, f.image) for f in body.frames], now=utcnow(),
    )
    return job_out(session, job, user, storage, settings.api.signed_url_ttl_seconds)


@router.get("", response_model=list[JobSummary])
def list_jobs(user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep) -> list[JobSummary]:
    ttl = settings.api.signed_url_ttl_seconds
    return [JobSummary(**_summary_fields(j, storage, ttl)) for j in services.list_jobs(session, user)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep) -> JobOut:
    job = services.get_job(session, user, job_id)
    return job_out(session, job, user, storage, settings.api.signed_url_ttl_seconds)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, user: UserDep, session: SessionDep, storage: StorageDep) -> Response:
    services.delete_job(session, storage, user, job_id, utcnow())
    return Response(status_code=204)


@router.post("/{job_id}/more", response_model=JobOut)
def more_clips(
    job_id: str, body: MoreClipsIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep, dispatcher: DispatcherDep,
) -> JobOut:
    """Busca más clips en el mismo vídeo (sin volver a subirlo ni gastar minutos)."""
    now = utcnow()
    job = services.get_job(session, user, job_id)
    task = editing.request_more_clips(session, user, job, count=body.count, topic=body.topic, now=now)
    session.commit()
    if dispatch_job(dispatcher, task, now):
        session.commit()
    return job_out(session, job, user, storage, settings.api.signed_url_ttl_seconds)


# --------------------------------------------------------------------------- descargar todo


@router.post("/{job_id}/archive", response_model=ArchiveOut)
def archive_link(job_id: str, user: UserDep, session: SessionDep, settings: SettingsDep) -> ArchiveOut:
    """Enlace temporal para descargar el ZIP (el navegador no puede enviar la cabecera de sesión en una descarga)."""
    job = services.get_job(session, user, job_id)
    if not job.clips:
        raise NotFound()
    token = editing.archive_token(settings.api.secret_key, job.id, user.id)
    return ArchiveOut(url=f"{settings.api.public_url.rstrip('/')}/jobs/{job.id}/archive?token={token}")


class _Sink:
    """Destino no «seekable» para zipfile: acumula lo escrito y lo entrega por trozos."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.pos = 0

    def write(self, data) -> int:
        self.chunks.append(bytes(data))
        self.pos += len(data)
        return len(data)

    def tell(self) -> int:
        return self.pos

    def flush(self) -> None:
        pass

    def drain(self) -> Iterator[bytes]:
        chunks, self.chunks = self.chunks, []
        yield from chunks


def _zip_stream(entries: list[tuple[str, Callable[[], Iterator[bytes]]]]) -> Iterator[bytes]:
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED) as zf:  # los MP4 ya van comprimidos
        for name, produce in entries:
            with zf.open(name, "w", force_zip64=True) as dst:
                for chunk in produce():
                    dst.write(chunk)
                    yield from sink.drain()
            yield from sink.drain()
    yield from sink.drain()


def _texts(job: Job) -> str:
    blocks = []
    for clip in job.clips:
        tags = " ".join(f"#{t}" for t in clip.hashtags or [])
        blocks.append(f"Clip {clip.rank:02d} — {clip.title}\n\n{clip.description}\n{tags}".strip())
    return ("\n\n" + "-" * 40 + "\n\n").join(blocks) + "\n"


@router.get("/{job_id}/archive", response_class=StreamingResponse, include_in_schema=False)
def archive(
    job_id: str, session: SessionDep, storage: StorageDep, settings: SettingsDep, token: str = Query(...),
) -> StreamingResponse:
    job = session.get(Job, job_id)
    if job is None or not editing.verify_archive_token(settings.api.secret_key, job.id, job.user_id, token):
        raise AppError("not_found", 404, key="archive_expired")
    entries: list[tuple[str, Callable[[], Iterator[bytes]]]] = []
    for clip in job.clips:
        entries.append((clip_filename(job, clip, "mp4"), lambda key=clip.video_key: storage.iter_bytes(key)))
        try:
            srt = editing.captions(storage, job, clip, "srt").encode("utf-8")
            entries.append((clip_filename(job, clip, "srt"), lambda data=srt: iter([data])))
        except AppError:
            pass  # proyectos antiguos sin transcripción guardada: solo los vídeos
    entries.append(("textos-para-publicar.txt", lambda: iter([_texts(job).encode("utf-8")])))
    filename = f"{slugify(job.title)}-clips.zip"
    return StreamingResponse(
        _zip_stream(entries), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
