"""Worker: ejecuta el pipeline del core para los jobs encolados.

La tabla `jobs` hace de cola: el worker reclama un job con un UPDATE atómico
(`status queued → running`), por lo que pueden correr varios workers a la vez
sin procesar dos veces el mismo job. En producción (Modal) cada envío ejecuta
`JobRunner.process(job_id)`; en local, `run_forever()` sondea la tabla.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path, PurePath

import sentry_sdk
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from smartcuts.application.pipeline import PipelineOptions
from smartcuts.bootstrap import build_pipeline
from smartcuts.domain.errors import ConfigurationError, SelectionError, SmartCutsError, SourceUnavailableError
from smartcuts.domain.ports import Storage, Transcriber
from smartcuts.infra import ffmpeg, registry
from smartcuts.infra.config import Settings
from smartcuts.infra.logging import bind_job, clear_job, get_logger
from smartcuts.saas.artifacts import make_preview, preview_key, save_analysis
from smartcuts.saas.db import session_scope, utcnow
from smartcuts.saas.maintenance import run_cleanup
from smartcuts.saas.models import Clip, Job, JobStatus, Upload, User
from smartcuts.saas.notifications import Notifier, build_notifier, clips_ready, deliver, processing_failed
from smartcuts.saas.rendering import project_branding, project_profile
from smartcuts.saas.services import clips_prefix, purge_upload, refund_job
from smartcuts.saas.tasks import TaskRunner

log = get_logger(__name__)

PROGRESS_MIN_INTERVAL = 1.5  # s entre escrituras de progreso en la BD


def classify_error(exc: BaseException, stage: str | None) -> str:
    if isinstance(exc, SelectionError) and "vacía" in str(exc):
        return "no_speech"
    if isinstance(exc, SourceUnavailableError) or (isinstance(exc, SmartCutsError) and stage in ("ingest", "audio")):
        return "invalid_video"
    if isinstance(exc, ConfigurationError):
        return "internal_error"  # fallo nuestro (credenciales, config), no del usuario
    return "processing_failed"


class JobRunner:
    def __init__(
        self, settings: Settings, sessions: sessionmaker[Session], storage: Storage, notifier: Notifier | None = None
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.storage = storage
        self.notifier = notifier or build_notifier(settings.notifications)
        self._transcriber: Transcriber | None = None
        self._tasks: TaskRunner | None = None

    @property
    def tasks(self) -> TaskRunner:
        """Re-renders y «más clips» (comparten conexión, almacenamiento y modelo de Whisper)."""
        if self._tasks is None:
            self._tasks = TaskRunner(self.settings, self.sessions, self.storage, transcriber=self.transcriber)
        return self._tasks

    @property
    def transcriber(self) -> Transcriber:
        if self._transcriber is None:
            t = self.settings.transcription
            self._transcriber = registry.create("transcribers", t.provider, **t.model_dump(exclude={"provider"}))
        return self._transcriber

    # ------------------------------------------------------------------ cola

    def claim(self, job_id: str) -> bool:
        now = utcnow()
        with session_scope(self.sessions) as s:
            result = s.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
                .values(status=JobStatus.RUNNING, stage="starting", started_at=now, heartbeat_at=now,
                        attempts=Job.attempts + 1)
            )
            return result.rowcount == 1

    def claim_next(self) -> str | None:
        with session_scope(self.sessions) as s:
            candidates = s.scalars(
                select(Job.id).where(Job.status == JobStatus.QUEUED).order_by(Job.created_at).limit(5)
            ).all()
        for job_id in candidates:
            if self.claim(job_id):
                return job_id
        return None

    def recover_stale(self) -> None:
        """Jobs 'running' sin latido: se reencolan o, agotados los intentos, fallan con reembolso."""
        now = utcnow()
        limit = now - timedelta(seconds=self.settings.worker.stale_after_seconds)
        with session_scope(self.sessions) as s:
            stale = s.scalars(
                select(Job).where(Job.status == JobStatus.RUNNING, Job.heartbeat_at < limit)
            ).all()
            for job in stale:
                if job.attempts < self.settings.worker.max_attempts:
                    job.status, job.stage, job.progress = JobStatus.QUEUED, "queued", 0.0
                    job.dispatched_at = None  # con worker remoto, el barrido lo reenvía enseguida
                    log.warning("job.requeued", job_id=job.id, attempts=job.attempts)
                else:
                    self._mark_failed(s, job, "worker_lost", "sin latido del worker")

    # ------------------------------------------------------------------ ejecución

    def process(self, job_id: str) -> bool:
        """Reclama y ejecuta un job concreto (worker remoto). False si otro worker ya lo tenía."""
        if not self.claim(job_id):
            log.info("job.not_claimed", job_id=job_id)
            return False
        self.run(job_id)
        return True

    def run(self, job_id: str) -> None:
        bind_job(job_id=job_id)
        tmp = Path(tempfile.mkdtemp(prefix=f"smartcuts-{job_id[:8]}-"))
        state = {"stage": "starting", "last_write": 0.0}
        try:
            with session_scope(self.sessions) as s:
                job = s.get(Job, job_id)
                if job is None or job.status != JobStatus.RUNNING:
                    return
                upload = s.get(Upload, job.upload_id) if job.upload_id else None
                if upload is None:
                    raise SourceUnavailableError("La subida asociada al job ya no existe")
                user_id, max_clips, title = job.user_id, job.max_clips, job.title
                options = dict(job.options or {})
                language = options.get("language", self.settings.language)
                upload_key, upload_ext = upload.storage_key, PurePath(upload.filename).suffix.lower() or ".mp4"
                upload_type = upload.content_type
                branding = project_branding(self.storage, s.get(User, user_id), options, tmp / "brand")

            self._write_progress(job_id, "ingest", 0.0, state, force=True)
            source = self.storage.local_path(upload_key)
            if source is None:
                source = self.storage.download_to(upload_key, tmp / f"source{upload_ext}")
            if options.get("trim") and not options.get("trim_applied"):
                source = self._apply_trim(job_id, Path(source), options, upload_key, upload_type, tmp)

            pipeline = build_pipeline(self.settings, transcriber=self.transcriber)
            opts = PipelineOptions(
                profile=project_profile(self.settings, options),
                max_clips=max_clips,
                language=None if language == "auto" else language,
                title=title,
                topic=options.get("topic") or "",
                branding=branding,
            )
            result = pipeline.run(
                str(source), opts, out_dir=tmp / "out",
                on_progress=lambda stage, overall: self._write_progress(job_id, stage, overall, state),
            )
            if not result.exports:
                raise SelectionError("La transcripción está vacía o no hay fragmentos válidos")

            clips: list[Clip] = []
            prefix = clips_prefix(user_id, job_id).rstrip("/")
            for exp in result.exports:
                video_key = f"{prefix}/{exp.rank:02d}.mp4"
                self.storage.put_file(video_key, exp.path, "video/mp4")
                thumb_key = None
                if exp.thumbnail and exp.thumbnail.exists():
                    thumb_key = f"{prefix}/{exp.rank:02d}.jpg"
                    self.storage.put_file(thumb_key, exp.thumbnail, "image/jpeg")
                clips.append(Clip(
                    job_id=job_id, rank=exp.rank, title=exp.title or f"Clip {exp.rank}", reason=exp.reason,
                    start=exp.start, end=exp.end, score=exp.score, video_key=video_key, thumb_key=thumb_key,
                    size_bytes=exp.path.stat().st_size, description=exp.description, hashtags=exp.hashtags,
                ))

            # Análisis del vídeo: editor, subtítulos descargables y «más clips» sin volver a transcribir.
            if result.transcript is not None and result.signals is not None:
                save_analysis(self.storage, user_id, job_id, result.transcript, result.signals)
            keep_source = bool(options.get("keep_source"))
            if keep_source:
                self._write_progress(job_id, "preview", 0.99, state, force=True)
                if preview := make_preview(Path(source), tmp / "preview.mp4"):
                    self.storage.put_file(preview_key(user_id, job_id), preview, "video/mp4")

            with session_scope(self.sessions) as s:
                job = s.get(Job, job_id)
                job.clips = clips
                job.status, job.stage, job.progress = JobStatus.DONE, "done", 1.0
                job.finished_at = utcnow()
                job.llm_cost_usd = round(result.cost_usd, 5)
                # Si el usuario no quiere editar ni pedir más clips, el original se borra ya (almacenamiento
                # y RGPD); si no, se conserva hasta que caduque el proyecto.
                if not keep_source and job.upload_id and (upload := s.get(Upload, job.upload_id)):
                    purge_upload(self.storage, upload)
                user = s.get(User, user_id)
                email = clips_ready(user.email, title, len(clips), user.plan.retention_days,
                                    f"{self.settings.notifications.web_url}/projects/{job_id}",
                                    lang=(user.preferences or {}).get("locale", "es"))
            log.info("job.done", clips=len(clips), cost_usd=round(result.cost_usd, 4))
            deliver(self.notifier, email)

        except Exception as exc:
            code = classify_error(exc, state["stage"])
            detail = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, SmartCutsError) and exc.detail:
                detail += f"\n{exc.detail}"
            log.error("job.failed", code=code, stage=state["stage"], error=detail[:2000],
                      exc_info=not isinstance(exc, SmartCutsError))
            if code in ("processing_failed", "internal_error"):  # fallos nuestros, no del vídeo del usuario
                with sentry_sdk.new_scope() as scope:
                    scope.set_tag("job_stage", state["stage"])
                    scope.set_tag("error_code", code)
                    scope.set_context("job", {"job_id": job_id})
                    sentry_sdk.capture_exception(exc)
            with session_scope(self.sessions) as s:
                job = s.get(Job, job_id)
                if job is not None:
                    self._mark_failed(s, job, code, detail)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            clear_job()

    def _apply_trim(
        self, job_id: str, source: Path, options: dict, upload_key: str, content_type: str, tmp: Path,
    ) -> Path:
        """Recorta el tramo elegido (si no se hizo ya en el navegador) y sustituye con él el original
        guardado: así el editor, los re-renders y «más clips» trabajan sobre lo mismo que se procesó."""
        start, end = options["trim"]
        cut = tmp / f"tramo{source.suffix or '.mp4'}"
        faststart = ["-movflags", "+faststart"] if cut.suffix in (".mp4", ".mov", ".m4v") else []
        ffmpeg.run([
            "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{end - start:.3f}",
            "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-avoid_negative_ts", "make_zero", *faststart,
            str(cut),
        ], what="recorte del tramo elegido")
        width, height, _, duration = ffmpeg.video_info(cut)
        self.storage.put_file(upload_key, cut, content_type)
        with session_scope(self.sessions) as s:
            job = s.get(Job, job_id)
            job.options = {**(job.options or {}), "trim_applied": True}
            if upload := s.get(Upload, job.upload_id):
                upload.size_bytes, upload.duration_seconds = cut.stat().st_size, duration
                upload.width, upload.height = width, height
        log.info("job.trimmed", start=start, end=end, duration=round(duration, 1))
        return cut

    def _mark_failed(self, s: Session, job: Job, code: str, detail: str) -> None:
        now = utcnow()
        job.status, job.error_code, job.error_detail = JobStatus.FAILED, code, detail[:8000]
        job.finished_at = now
        refund_job(s, job, now, note=f"fallo: {code}")
        self.storage.delete_prefix(clips_prefix(job.user_id, job.id))
        if user := s.get(User, job.user_id):
            deliver(self.notifier, processing_failed(user.email, job.title, code,
                                                     f"{self.settings.notifications.web_url}/new",
                                                     lang=(user.preferences or {}).get("locale", "es")))

    def _write_progress(self, job_id: str, stage: str, overall: float, state: dict, force: bool = False) -> None:
        now = time.monotonic()
        changed = stage != state["stage"]
        state["stage"] = stage
        if not (force or changed or now - state["last_write"] >= PROGRESS_MIN_INTERVAL):
            return
        state["last_write"] = now
        with session_scope(self.sessions) as s:
            s.execute(
                update(Job).where(Job.id == job_id)
                .values(stage=stage, progress=round(min(overall, 0.99), 4), heartbeat_at=utcnow())
            )

    # ------------------------------------------------------------------ bucle local

    def run_forever(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        log.info("worker.started", poll_seconds=self.settings.worker.poll_seconds)
        last_recovery = last_cleanup = 0.0
        while not stop.is_set():
            if time.monotonic() - last_recovery > 60:
                self.recover_stale()
                self.tasks.recover_stale()
                last_recovery = time.monotonic()
            if time.monotonic() - last_cleanup > self.settings.worker.cleanup_every_seconds:
                try:
                    run_cleanup(self.settings, self.sessions, self.storage)
                except Exception as exc:  # la limpieza nunca debe tumbar el worker
                    log.error("cleanup.failed", error=str(exc))
                last_cleanup = time.monotonic()
            if task_id := self.tasks.claim_next():  # las tareas son cortas y el usuario las espera
                self.tasks.run(task_id)
                continue
            job_id = self.claim_next()
            if job_id is None:
                stop.wait(self.settings.worker.poll_seconds)
                continue
            self.run(job_id)
