"""Tareas sobre proyectos ya procesados: volver a exportar un clip editado y buscar más clips.

Igual que los jobs, la tabla `tasks` hace de cola: se reclaman con un UPDATE atómico, llevan latido
y, si el worker muere, el barrido las reencola. No consumen minutos del plan: el vídeo ya se pagó.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path, PurePath

import sentry_sdk
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from clipaso.application.pipeline import PipelineOptions
from clipaso.bootstrap import build_pipeline
from clipaso.domain.errors import ClipasoError
from clipaso.domain.models import ClipCandidate
from clipaso.domain.ports import Storage
from clipaso.infra import ffmpeg
from clipaso.infra.config import Settings
from clipaso.infra.logging import bind_job, clear_job, get_logger
from clipaso.saas import cover_service, exports
from clipaso.saas.artifacts import SourceCache, apply_edits, load_signals, load_transcript
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.metering import Meter
from clipaso.saas.models import (
    Clip,
    ClipStatus,
    DailyAction,
    Job,
    Task,
    TaskKind,
    TaskStatus,
    Upload,
    UploadStatus,
    User,
)
from clipaso.saas.rendering import project_branding, project_profile
from clipaso.saas.services import clips_prefix

log = get_logger(__name__)


class TaskError(Exception):
    """Fallo esperable de una tarea; `code` es una clave del catálogo de mensajes (saas/errors.py)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class TaskRunner:
    def __init__(
        self, settings: Settings, sessions: sessionmaker[Session], storage: Storage,
        sources: SourceCache | None = None, transcriber=None,
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.storage = storage
        self.sources = sources or SourceCache(Path(tempfile.gettempdir()) / "clipaso-sources")
        self.transcriber = transcriber

    # ------------------------------------------------------------------ cola

    def claim(self, task_id: str) -> bool:
        now = utcnow()
        with session_scope(self.sessions) as s:
            result = s.execute(
                update(Task)
                .where(Task.id == task_id, Task.status == TaskStatus.QUEUED)
                .values(status=TaskStatus.RUNNING, started_at=now, heartbeat_at=now, attempts=Task.attempts + 1)
            )
            return result.rowcount == 1

    def claim_next(self) -> str | None:
        with session_scope(self.sessions) as s:
            candidates = s.scalars(
                select(Task.id).where(Task.status == TaskStatus.QUEUED).order_by(Task.created_at).limit(5)
            ).all()
        return next((task_id for task_id in candidates if self.claim(task_id)), None)

    def recover_stale(self) -> None:
        limit = utcnow() - timedelta(seconds=self.settings.worker.stale_after_seconds)
        with session_scope(self.sessions) as s:
            for task in s.scalars(select(Task).where(Task.status == TaskStatus.RUNNING, Task.heartbeat_at < limit)):
                if task.attempts < self.settings.worker.max_attempts:
                    task.status, task.dispatched_at = TaskStatus.QUEUED, None
                    log.warning("task.requeued", task_id=task.id)
                else:
                    self._finish_failed(s, task, "worker_lost")

    def _beat(self, task_id: str) -> None:
        with session_scope(self.sessions) as s:
            s.execute(update(Task).where(Task.id == task_id).values(heartbeat_at=utcnow()))

    # ------------------------------------------------------------------ ejecución

    def process(self, task_id: str) -> bool:
        if not self.claim(task_id):
            log.info("task.not_claimed", task_id=task_id)
            return False
        self.run(task_id)
        return True

    def run(self, task_id: str) -> None:
        bind_job(task_id=task_id)
        tmp = Path(tempfile.mkdtemp(prefix=f"clipaso-task-{task_id[:8]}-"))
        meter = Meter(self.settings.costs)
        try:
            with session_scope(self.sessions) as s:
                task = s.get(Task, task_id)
                if task is None or task.status != TaskStatus.RUNNING:
                    return
                kind = task.kind
            if kind == TaskKind.RENDER_CLIP:
                self._render_clip(task_id, tmp)
            elif kind == TaskKind.MORE_CLIPS:
                self._more_clips(task_id, tmp)
            elif kind == TaskKind.EXPORT_CLIP:
                self._export_clip(task_id, tmp)
            elif kind == TaskKind.COVER_CLIP:
                self._cover_clip(task_id, tmp)
            else:
                raise TaskError("internal_error", f"tarea desconocida: {kind}")
            with session_scope(self.sessions) as s:
                task = s.get(Task, task_id)
                task.status, task.finished_at = TaskStatus.DONE, utcnow()
                task.metrics = meter.finish()
            log.info("task.done", kind=kind)
        except Exception as exc:
            if isinstance(exc, TaskError):
                code = exc.code
            else:
                code = "render_failed"
                log.error("task.failed", error=str(exc), exc_info=not isinstance(exc, ClipasoError))
                sentry_sdk.capture_exception(exc)
            with session_scope(self.sessions) as s:
                if task := s.get(Task, task_id):
                    task.metrics = meter.finish(failed=True)
                    self._finish_failed(s, task, code, detail=f"{type(exc).__name__}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            clear_job()

    def _finish_failed(self, s: Session, task: Task, code: str, detail: str = "") -> None:
        task.status, task.finished_at = TaskStatus.FAILED, utcnow()
        task.error_code, task.error_detail = code, (detail or code)[:8000]
        s.execute(delete(DailyAction).where(DailyAction.task_id == task.id))  # lo que falla no gasta cupo
        # Solo un re-render fallido deja el clip en error; una exportación fallida no toca el clip.
        if task.kind == TaskKind.COVER_CLIP and task.clip_id and (clip := s.get(Clip, task.clip_id)) and clip.cover:
            clip.cover = {**clip.cover, "pending": False}
        if task.kind == TaskKind.RENDER_CLIP and task.clip_id and (clip := s.get(Clip, task.clip_id)):
            clip.status, clip.render_error = ClipStatus.FAILED, code  # se traduce al mostrarlo

    # ------------------------------------------------------------------ piezas comunes

    def _load(self, s: Session, task_id: str) -> tuple[Task, Job, Upload, User]:
        task = s.get(Task, task_id)
        job = s.get(Job, task.job_id)
        upload = s.get(Upload, job.upload_id) if job and job.upload_id else None
        if job is None or upload is None or upload.status == UploadStatus.PURGED:
            raise TaskError("source_unavailable")
        return task, job, upload, s.get(User, job.user_id)

    def _source(self, upload_key: str, filename: str) -> Path:
        return self.sources.get(self.storage, upload_key, PurePath(filename).suffix.lower() or ".mp4")

    def _upload_clip(self, user_id: str, job_id: str, rank: int, version: int, video: Path, thumb: Path | None):
        prefix = clips_prefix(user_id, job_id).rstrip("/")
        stem = f"{rank:02d}" if version == 1 else f"{rank:02d}-v{version}"
        video_key = f"{prefix}/{stem}.mp4"
        self.storage.put_file(video_key, video, "video/mp4")
        thumb_key = None
        if thumb and thumb.exists():
            thumb_key = f"{prefix}/{stem}.jpg"
            self.storage.put_file(thumb_key, thumb, "image/jpeg")
        return video_key, thumb_key, video.stat().st_size

    # ------------------------------------------------------------------ re-render

    def _render_clip(self, task_id: str, tmp: Path) -> None:
        with session_scope(self.sessions) as s:
            task, job, upload, user = self._load(s, task_id)
            clip = s.get(Clip, task.clip_id)
            if clip is None:
                raise TaskError("not_found")
            start, end = float(task.payload["start"]), float(task.payload["end"])
            options, user_id, job_id, title = dict(job.options or {}), job.user_id, job.id, job.title
            rank, version, edits, style = clip.rank, clip.version, dict(clip.word_edits or {}), clip.caption_style
            candidate = ClipCandidate(start=start, end=end, first_sentence=0, last_sentence=0, score=clip.score,
                                      title=clip.title, reason=clip.reason, description=clip.description,
                                      hashtags=list(clip.hashtags or []))
            branding = project_branding(self.storage, user, options, tmp / "brand")
            upload_key, filename = upload.storage_key, upload.filename
            old_keys = [clip.video_key, clip.thumb_key]

        transcript = load_transcript(self.storage, user_id, job_id)
        if transcript is None:
            raise TaskError("no_transcript")
        source = self._source(upload_key, filename)
        self._beat(task_id)
        opts = PipelineOptions(profile=project_profile(self.settings, options, style), max_clips=1, language=None,
                               title=title, branding=branding)
        pipeline = build_pipeline(self.settings, transcriber=self.transcriber)
        exported = pipeline.render(str(source), opts, candidate, rank, apply_edits(transcript, edits), tmp / "out")
        new_version = version + 1
        video_key, thumb_key, size = self._upload_clip(user_id, job_id, rank, new_version, exported.path,
                                                       exported.thumbnail)
        with session_scope(self.sessions) as s:
            clip = s.get(Clip, task.clip_id)
            clip.start, clip.end = start, end
            clip.video_key, clip.thumb_key, clip.size_bytes = video_key, thumb_key, size
            clip.version, clip.status, clip.render_error = new_version, ClipStatus.READY, None
            exports.drop_exports(self.storage, clip)  # las otras calidades eran de la versión anterior
            cover_time = (clip.cover or {}).get("time")
            needs_cover = cover_time is None or not start <= cover_time <= end
        if needs_cover:  # el fotograma de la portada quedó fuera del nuevo recorte
            self._covers(task_id, [task.clip_id], transcript, source, tmp)
        for key in old_keys:
            if key and key not in (video_key, thumb_key):
                self.storage.delete_prefix(key)

    # ------------------------------------------------------------------ otras calidades

    def _export_clip(self, task_id: str, tmp: Path) -> None:
        with session_scope(self.sessions) as s:
            task = s.get(Task, task_id)
            clip = s.get(Clip, task.clip_id) if task.clip_id else None
            job = s.get(Job, task.job_id)
            if clip is None or job is None:
                raise TaskError("not_found")
            quality, version = str(task.payload["quality"]), int(task.payload["version"])
            if clip.version != version:
                return  # el clip cambió mientras esperaba: esta exportación ya no sirve
            upload = s.get(Upload, job.upload_id) if job.upload_id else None
            has_source = upload is not None and upload.status == UploadStatus.READY
            options, user_id, job_id, title = dict(job.options or {}), job.user_id, job.id, job.title
            rank, edits, style = clip.rank, dict(clip.word_edits or {}), clip.caption_style
            candidate = ClipCandidate(start=clip.start, end=clip.end, first_sentence=0, last_sentence=0,
                                      score=clip.score, title=clip.title)
            branding = None
            if has_source:
                branding = project_branding(self.storage, s.get(User, user_id), options, tmp / "brand")
            upload_key, filename = (upload.storage_key, upload.filename) if upload else (None, None)
            video_key = clip.video_key
            key = exports.export_key(job, clip, quality, "mp4")

        if has_source:
            # Render nuevo desde el original a la resolución pedida: subtítulos y marca nítidos.
            transcript = load_transcript(self.storage, user_id, job_id)
            if transcript is None:
                raise TaskError("no_transcript")
            source = self._source(upload_key, filename)
            self._beat(task_id)
            profile = exports.scaled_profile(project_profile(self.settings, options, style), quality)
            opts = PipelineOptions(profile=profile, max_clips=1, language=None, title=title, branding=branding)
            pipeline = build_pipeline(self.settings, transcriber=self.transcriber)
            video = pipeline.render(str(source), opts, candidate, rank, apply_edits(transcript, edits),
                                    tmp / "out").path
        else:
            # Sin original: solo se puede reducir el clip ya renderizado.
            if exports.QUALITIES[quality] >= exports.QUALITIES[exports.BASE_QUALITY]:
                raise TaskError("source_unavailable")
            clip_file = self.storage.local_path(video_key) or self.storage.download_to(video_key, tmp / "clip.mp4")
            short = exports.QUALITIES[quality]
            video = tmp / f"{quality}.mp4"
            ffmpeg.run(["-i", str(clip_file), "-vf", f"scale='if(lt(iw,ih),{short},-2)':'if(lt(iw,ih),-2,{short})'",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-movflags", "+faststart", str(video)], what=f"clip en {quality}")

        self.storage.put_file(key, video, "video/mp4")
        with session_scope(self.sessions) as s:
            clip = s.get(Clip, task.clip_id)
            if clip is None or clip.version != version:
                self.storage.delete_prefix(key)
                return
            clip.exports = {**(clip.exports or {}),
                            quality: {"version": version, "key": key, "size": video.stat().st_size}}
        log.info("task.exported", quality=quality)

    # ------------------------------------------------------------------ portadas

    def _covers(self, task_id: str, clip_ids: list[str], transcript, source: Path, tmp: Path,
                again: bool = False) -> None:
        with session_scope(self.sessions) as s:
            task = s.get(Task, task_id)
            job = s.get(Job, task.job_id)
            user = s.get(User, job.user_id)
            options = dict(job.options or {})
            branding = project_branding(self.storage, user, options, tmp / "brand-cover")
            logo = branding.logo_path.read_bytes() if branding and branding.logo_path else None
            clips = [c for c in (s.get(Clip, cid) for cid in clip_ids) if c is not None]
            cost = cover_service.generate_for_clips(
                self.storage, self.settings, job.user_id, job.id, clips, source=source, transcript=transcript,
                options=options, logo=logo, logo_position=branding.position if branding else "top-right",
                again=again,
            )
            job.llm_cost_usd = round((job.llm_cost_usd or 0) + cost, 5)

    def _cover_clip(self, task_id: str, tmp: Path) -> None:
        """«Regenerar con IA»: otra propuesta de portada distinta de la actual."""
        with session_scope(self.sessions) as s:
            task, job, upload, _user = self._load(s, task_id)
            upload_key, filename, user_id, job_id = upload.storage_key, upload.filename, job.user_id, job.id
        transcript = load_transcript(self.storage, user_id, job_id)
        source = self._source(upload_key, filename)
        self._beat(task_id)
        self._covers(task_id, [task.clip_id], transcript, source, tmp, again=True)

    # ------------------------------------------------------------------ más clips

    def _more_clips(self, task_id: str, tmp: Path) -> None:
        with session_scope(self.sessions) as s:
            task, job, upload, user = self._load(s, task_id)
            options, user_id, job_id, title = dict(job.options or {}), job.user_id, job.id, job.title
            count = int(task.payload.get("count", 3))
            topic = str(task.payload.get("topic") or options.get("topic") or "")
            existing = [(c.start, c.end) for c in job.clips]
            next_rank = max((c.rank for c in job.clips), default=0) + 1
            branding = project_branding(self.storage, user, options, tmp / "brand")
            upload_key, filename = upload.storage_key, upload.filename
            language = options.get("language", self.settings.language)

        transcript = load_transcript(self.storage, user_id, job_id)
        signals = load_signals(self.storage, user_id, job_id)
        if transcript is None or signals is None:
            raise TaskError("no_transcript")
        source = self._source(upload_key, filename)
        self._beat(task_id)
        opts = PipelineOptions(profile=project_profile(self.settings, options), max_clips=count,
                               language=None if language == "auto" else language, title=title, topic=topic,
                               exclude=existing, branding=branding, first_rank=next_rank)
        pipeline = build_pipeline(self.settings, transcriber=self.transcriber)
        try:
            result = pipeline.run(str(source), opts, out_dir=tmp / "out", transcript=transcript, signals=signals)
        except ClipasoError as exc:
            if "ningún clip" in str(exc) or "vacía" in str(exc):
                raise TaskError("no_more_clips") from exc
            raise
        if not result.exports:
            raise TaskError("no_more_clips")

        new_clips: list[Clip] = []
        for exp in result.exports:
            video_key, thumb_key, size = self._upload_clip(user_id, job_id, exp.rank, 1, exp.path, exp.thumbnail)
            new_clips.append(Clip(
                job_id=job_id, rank=exp.rank, title=exp.title or f"Clip {exp.rank}", reason=exp.reason,
                start=exp.start, end=exp.end, score=exp.score, video_key=video_key, thumb_key=thumb_key,
                size_bytes=size, description=exp.description, hashtags=exp.hashtags,
            ))
            self._beat(task_id)
        with session_scope(self.sessions) as s:
            job = s.get(Job, job_id)
            job.clips.extend(new_clips)
            s.flush()
            new_ids = [c.id for c in new_clips]
        self._covers(task_id, new_ids, transcript, source, tmp)
        with session_scope(self.sessions) as s:
            job = s.get(Job, job_id)
            job.llm_cost_usd = round((job.llm_cost_usd or 0) + result.cost_usd, 5)
        log.info("task.more_clips", added=len(new_clips))
