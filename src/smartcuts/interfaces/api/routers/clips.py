"""Acciones sobre un clip: textos, valoración, subtítulos descargables y editor."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from smartcuts.interfaces.api.deps import DispatcherDep, SessionDep, SettingsDep, StorageDep, UserDep
from smartcuts.interfaces.api.routers.jobs import clip_filename, clip_out
from smartcuts.interfaces.api.schemas import (
    ClipOut,
    ClipUpdateIn,
    EditorOut,
    EditorWordOut,
    ExportIn,
    ExportOut,
    ExportsOut,
    RatingIn,
    RenderIn,
)
from smartcuts.saas import editing, exports
from smartcuts.saas.artifacts import preview_key
from smartcuts.saas.db import utcnow
from smartcuts.saas.dispatch import dispatch_job
from smartcuts.saas.errors import user_message
from smartcuts.saas.models import Clip, Job, Upload
from smartcuts.saas.rendering import result_frame

router = APIRouter(prefix="/clips", tags=["clips"])


@router.patch("/{clip_id}", response_model=ClipOut)
def update_clip(
    clip_id: str, body: ClipUpdateIn, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep,
) -> ClipOut:
    """Edita el título y los textos para publicar (no hace falta volver a renderizar)."""
    clip, job = editing.get_owned_clip(session, user, clip_id)
    editing.update_texts(clip, title=body.title, description=body.description, hashtags=body.hashtags)
    return clip_out(clip, job, storage, settings.api.signed_url_ttl_seconds)


@router.put("/{clip_id}/rating", response_model=ClipOut)
def rate_clip(
    clip_id: str, body: RatingIn, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep,
) -> ClipOut:
    clip, job = editing.get_owned_clip(session, user, clip_id)
    editing.set_rating(clip, body.value)
    return clip_out(clip, job, storage, settings.api.signed_url_ttl_seconds)


@router.get("/{clip_id}/captions", response_class=PlainTextResponse)
def clip_captions(
    clip_id: str, user: UserDep, session: SessionDep, storage: StorageDep,
    format: Literal["srt", "vtt"] = Query("srt"),
) -> PlainTextResponse:
    """Subtítulos del clip (con las correcciones del usuario) para editarlos en CapCut, Premiere…"""
    clip, job = editing.get_owned_clip(session, user, clip_id)
    text = editing.captions(storage, job, clip, format)
    media = "application/x-subrip" if format == "srt" else "text/vtt"
    return PlainTextResponse(
        text, media_type=f"{media}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{clip_filename(job, clip, format)}"'},
    )


@router.get("/{clip_id}/editor", response_model=EditorOut)
def clip_editor(
    clip_id: str, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep,
) -> EditorOut:
    """Todo lo que necesita el editor: tramo del original con contexto, palabras y estilo."""
    clip, job = editing.get_owned_clip(session, user, clip_id)
    upload = session.get(Upload, job.upload_id) if job.upload_id else None
    duration = (upload.duration_seconds if upload else None) or clip.end
    window = editing.editor_window(clip, duration)
    can_render = editing.source_available(session, job)
    preview = preview_key(job.user_id, job.id)
    ttl = settings.api.signed_url_ttl_seconds
    energy, energy_step = editing.editor_energy(storage, job, window)
    return EditorOut(
        clip=clip_out(clip, job, storage, ttl),
        project_title=job.title,
        format=result_frame(job.options or {}),
        source_duration=duration,
        window_start=window[0],
        window_end=window[1],
        preview_url=storage.signed_url(preview, expires=ttl) if can_render and storage.size(preview) else None,
        words=[EditorWordOut(**w.__dict__) for w in editing.editor_words(storage, job, clip, window)],
        caption_style=editing.effective_style(job, clip),
        can_render=can_render,
        energy=energy,
        energy_step=energy_step,
    )


@router.post("/{clip_id}/render", response_model=ClipOut, status_code=202)
def render_clip(
    clip_id: str, body: RenderIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep, dispatcher: DispatcherDep,
) -> ClipOut:
    """Guarda las ediciones (recorte, palabras, estilo) y vuelve a generar el clip."""
    now = utcnow()
    clip, job = editing.get_owned_clip(session, user, clip_id)
    task = editing.request_render(
        session, user, clip, job, start=body.start, end=body.end, word_edits=body.word_edits,
        caption_style=body.caption_style, now=now,
    )
    session.commit()
    if dispatch_job(dispatcher, task, now):
        session.commit()
    return clip_out(clip, job, storage, settings.api.signed_url_ttl_seconds)


# --------------------------------------------------------------------------- otras calidades y MP3


def _exports_out(session, storage, job: Job, clip: Clip, ttl: int) -> ExportsOut:
    items = []
    for e in exports.states(session, job, clip):
        name = clip_filename(job, clip, e.format)
        if e.quality and e.quality != exports.BASE_QUALITY:
            name = name.replace(".mp4", f"-{e.quality}.mp4")
        url = storage.signed_url(e.key, expires=ttl, download_name=name) if e.status == "ready" and e.key else None
        items.append(ExportOut(format=e.format, quality=e.quality, status=e.status, url=url, size_bytes=e.size,
                               error_message=user_message(e.error_code)))
    return ExportsOut(items=items)


@router.get("/{clip_id}/exports", response_model=ExportsOut)
def clip_exports(
    clip_id: str, user: UserDep, session: SessionDep, storage: StorageDep, settings: SettingsDep,
) -> ExportsOut:
    """Descargas disponibles del clip: MP4 en varias calidades y el audio en MP3."""
    clip, job = editing.get_owned_clip(session, user, clip_id)
    return _exports_out(session, storage, job, clip, settings.api.signed_url_ttl_seconds)


@router.post("/{clip_id}/exports", response_model=ExportsOut)
def request_export(
    clip_id: str, body: ExportIn, user: UserDep, session: SessionDep, storage: StorageDep,
    settings: SettingsDep, dispatcher: DispatcherDep,
) -> ExportsOut:
    """Genera una descarga: el MP3 al momento; otra calidad de vídeo, en segundo plano."""
    now = utcnow()
    clip, job = editing.get_owned_clip(session, user, clip_id)
    if body.format == "mp3":
        exports.make_mp3(storage, job, clip)
    else:
        task = exports.request_quality(session, user, job, clip, body.quality or exports.BASE_QUALITY, now)
        if task is not None:
            session.commit()
            if dispatch_job(dispatcher, task, now):
                session.commit()
    return _exports_out(session, storage, job, clip, settings.api.signed_url_ttl_seconds)
