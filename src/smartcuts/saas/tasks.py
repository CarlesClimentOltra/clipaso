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
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from smartcuts.application.pipeline import PipelineOptions
from smartcuts.bootstrap import build_pipeline
from smartcuts.domain.errors import SmartCutsError
from smartcuts.domain.models import ClipCandidate
from smartcuts.domain.ports import Storage
from smartcuts.infra.config import Settings
from smartcuts.infra.logging import bind_job, clear_job, get_logger
from smartcuts.saas.artifacts import SourceCache, apply_edits, load_signals, load_transcript
from smartcuts.saas.db import session_scope, utcnow
from smartcuts.saas.models import Clip, ClipStatus, Job, Task, TaskKind, TaskStatus, Upload, UploadStatus, User
from smartcuts.saas.rendering import project_branding, project_profile
from smartcuts.saas.services import clips_prefix

log = get_logger(__name__)


class TaskError(Exception):
    """Fallo esperable de una tarea, con un mensaje apto para el usuario."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskRunner:
    def __init__(
        self, settings: Settings, sessions: sessionmaker[Session], storage: Storage,
        sources: SourceCache | None = None, transcriber=None,
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.storage = storage
        self.sources = sources or SourceCache(Path(tempfile.gettempdir()) / "smartcuts-sources")
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
                    self._finish_failed(s, task, "worker_lost", "El proceso se interrumpió. Inténtalo de nuevo.")

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
        tmp = Path(tempfile.mkdtemp(prefix=f"smartcuts-task-{task_id[:8]}-"))
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
            else:
                raise TaskError("internal_error", f"Tarea desconocida: {kind}")
            with session_scope(self.sessions) as s:
                task = s.get(Task, task_id)
                task.status, task.finished_at = TaskStatus.DONE, utcnow()
            log.info("task.done", kind=kind)
        except Exception as exc:
            if isinstance(exc, TaskError):
                code, message = exc.code, exc.message
            else:
                code, message = "processing_failed", "Algo falló al generar el clip. Inténtalo de nuevo."
                log.error("task.failed", error=str(exc), exc_info=not isinstance(exc, SmartCutsError))
                sentry_sdk.capture_exception(exc)
            with session_scope(self.sessions) as s:
                if task := s.get(Task, task_id):
                    self._finish_failed(s, task, code, message, detail=f"{type(exc).__name__}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            clear_job()

    def _finish_failed(self, s: Session, task: Task, code: str, message: str, detail: str = "") -> None:
        task.status, task.finished_at = TaskStatus.FAILED, utcnow()
        task.error_code, task.error_detail = code, (detail or message)[:8000]
        if task.clip_id and (clip := s.get(Clip, task.clip_id)):
            clip.status, clip.render_error = ClipStatus.FAILED, message[:255]

    # ------------------------------------------------------------------ piezas comunes

    def _load(self, s: Session, task_id: str) -> tuple[Task, Job, Upload, User]:
        task = s.get(Task, task_id)
        job = s.get(Job, task.job_id)
        upload = s.get(Upload, job.upload_id) if job and job.upload_id else None
        if job is None or upload is None or upload.status == UploadStatus.PURGED:
            raise TaskError("source_unavailable", "El vídeo original ya no está disponible para este proyecto.")
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
                raise TaskError("not_found", "El clip ya no existe.")
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
            raise TaskError("source_unavailable", "No se encuentra la transcripción de este proyecto.")
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
        for key in old_keys:
            if key and key not in (video_key, thumb_key):
                self.storage.delete_prefix(key)

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
            raise TaskError("source_unavailable", "No se encuentra el análisis de este proyecto.")
        source = self._source(upload_key, filename)
        self._beat(task_id)
        opts = PipelineOptions(profile=project_profile(self.settings, options), max_clips=count,
                               language=None if language == "auto" else language, title=title, topic=topic,
                               exclude=existing, branding=branding, first_rank=next_rank)
        pipeline = build_pipeline(self.settings, transcriber=self.transcriber)
        try:
            result = pipeline.run(str(source), opts, out_dir=tmp / "out", transcript=transcript, signals=signals)
        except SmartCutsError as exc:
            if "ningún clip" in str(exc) or "vacía" in str(exc):
                raise TaskError("no_more_clips", "No hemos encontrado más momentos que merezcan un clip.") from exc
            raise
        if not result.exports:
            raise TaskError("no_more_clips", "No hemos encontrado más momentos que merezcan un clip.")

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
            job.llm_cost_usd = round((job.llm_cost_usd or 0) + result.cost_usd, 5)
        log.info("task.more_clips", added=len(new_clips))
