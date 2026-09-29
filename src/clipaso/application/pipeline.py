"""Orquestación del pipeline por etapas.

ingest → audio → transcribe → signals → select → export

Cada etapa persiste su resultado en el workspace del vídeo; relanzar el mismo
vídeo reutiliza todo lo que no haya cambiado. El pipeline no conoce ninguna
implementación concreta: recibe los componentes ya construidos (ver
`clipaso.bootstrap`).
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from clipaso.application import cleanup
from clipaso.application.cleanup import CutPlan, PaceT
from clipaso.application.cost import CostTracker
from clipaso.application.progress import CLEAN_WEIGHTS, SUBTITLE_WEIGHTS, ProgressCallback, ProgressReporter
from clipaso.application.translation import Translator
from clipaso.application.workspace import Workspace
from clipaso.domain.errors import ClipasoError, RenderError, UnsupportedSourceError
from clipaso.domain.models import (
    Branding,
    ClipCandidate,
    ExportedClip,
    JobResult,
    OutputProfile,
    Selection,
    SignalSet,
    SourceVideo,
    Transcript,
)
from clipaso.domain.ports import (
    AnalysisContext,
    ClipSelector,
    Exporter,
    ExportRequest,
    Reframer,
    SelectionRequest,
    SignalExtractor,
    Transcriber,
    VideoSource,
)
from clipaso.infra import ffmpeg
from clipaso.infra.logging import bind_job, clear_job, get_logger

log = get_logger(__name__)


@dataclass
class PipelineOptions:
    profile: OutputProfile
    max_clips: int
    language: str | None
    force: set[str] = field(default_factory=set)  # etapas a recalcular aunque haya caché
    title: str | None = None  # título legible (p. ej. nombre original del fichero subido)
    topic: str = ""  # tema que pide el usuario («momentos donde hablo de dinero»)
    exclude: list[tuple[float, float]] = field(default_factory=list)  # fragmentos que ya son clips
    branding: Branding | None = None
    first_rank: int = 1  # al añadir clips a un proyecto, numeración a continuación de los existentes
    transcribe_prompt: str | None = None  # p. ej. transcripción literal (con muletillas)


@dataclass
class Components:
    sources: list[VideoSource]
    transcriber: Transcriber
    transcriber_params: dict
    signals: list[SignalExtractor]
    selector: ClipSelector
    selector_params: dict
    fallback_selector: ClipSelector | None
    reframer_factory: Callable[[str], Reframer]
    exporter_factory: Callable[[str], Exporter]
    cost: CostTracker
    translator_factory: Callable[[], Translator] | None = None


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "clip"


@contextmanager
def stage(name: str) -> Iterator[None]:
    bind_job(stage=name)
    t0 = time.monotonic()
    log.info("stage.start")
    try:
        yield
    finally:
        log.info("stage.end", seconds=round(time.monotonic() - t0, 1))


class Pipeline:
    def __init__(self, components: Components, jobs_dir: Path, output_dir: Path) -> None:
        self.c = components
        self.jobs_dir = jobs_dir
        self.output_dir = output_dir

    def resolve_source(self, uri: str) -> VideoSource:
        for source in self.c.sources:
            if source.can_handle(uri):
                return source
        raise UnsupportedSourceError(
            f"Ninguna fuente sabe manejar '{uri}'. Fuentes activas: {', '.join(s.name for s in self.c.sources)}"
        )

    # ------------------------------------------------------------------ etapas

    def _ingest(self, uri: str, ws: Workspace, adapter: VideoSource) -> SourceVideo:
        with stage("ingest"):
            source = adapter.fetch(uri, ws.root)
            ws.save("source", source, {})
            log.info("source.ready", title=source.title, duration=round(source.duration),
                     resolution=f"{source.width}x{source.height}")
            return source

    def _audio(self, source: SourceVideo, ws: Workspace) -> Path:
        audio = ws.path("audio.wav")
        if not audio.exists():
            with stage("audio"):
                ffmpeg.extract_audio(source.path, audio.with_suffix(".tmp.wav"))
                audio.with_suffix(".tmp.wav").replace(audio)
        return audio

    def _transcribe(
        self, audio: Path, ws: Workspace, opts: PipelineOptions, progress: ProgressReporter
    ) -> Transcript:
        params = {"provider": self.c.transcriber.name, **self.c.transcriber_params, "language": opts.language}
        extra = {"prompt": opts.transcribe_prompt} if opts.transcribe_prompt else {}
        params |= extra
        if "transcript" not in opts.force and (cached := ws.load("transcript", Transcript, params)):
            log.info("transcript.cached", sentences=len(cached.sentences))
            return cached
        with stage("transcribe"):
            transcript = self.c.transcriber.transcribe(
                audio, opts.language, on_progress=progress.stage_callback("transcribe"), **extra
            )
            ws.save("transcript", transcript, params)
            (ws.path("transcript.txt")).write_text(
                "\n".join(f"[{s.start:7.1f}] {s.text}" for s in transcript.sentences), encoding="utf-8"
            )
            return transcript

    def _signals(self, ctx: AnalysisContext, ws: Workspace, opts: PipelineOptions) -> SignalSet:
        params = {"signals": [s.name for s in self.c.signals], "sentences": len(ctx.transcript.sentences)}
        if "signals" not in opts.force and (cached := ws.load("signals", SignalSet, params)):
            return cached
        with stage("signals"):
            result = SignalSet()
            for extractor in self.c.signals:
                try:
                    signal = extractor.extract(ctx)
                except Exception as exc:  # una señal rota no debe tumbar el job
                    log.warning("signal.failed", signal=extractor.name, error=str(exc))
                    continue
                if signal is None:
                    log.info("signal.unavailable", signal=extractor.name)
                    continue
                result.signals[signal.name] = signal
            ws.save("signals", result, params)
            return result

    def _select(self, request: SelectionRequest, ws: Workspace, opts: PipelineOptions) -> Selection:
        p = request.profile
        params = {
            "strategy": self.c.selector.name,
            **self.c.selector_params,
            "max_clips": request.max_clips,
            "durations": [p.min_duration, p.target_duration, p.max_duration],
            "transcript_sentences": len(request.transcript.sentences),
            "signals": sorted(request.signals.signals),
            "extra": request.extra,
        }
        if "selection" not in opts.force and (cached := ws.load("selection", Selection, params)):
            log.info("selection.cached", strategy=cached.strategy, clips=len(cached.clips))
            return cached
        with stage("select"):
            try:
                selection = self.c.selector.select(request)
            except ClipasoError as exc:
                if self.c.fallback_selector is None or self.c.fallback_selector.name == self.c.selector.name:
                    raise
                log.warning("selection.fallback", failed=self.c.selector.name,
                            fallback=self.c.fallback_selector.name, error=str(exc), detail=exc.detail)
                selection = self.c.fallback_selector.select(request)
                selection.notes.append(f"fallback tras error en '{self.c.selector.name}': {exc}")
                # No se cachea: la próxima ejecución volverá a intentar la estrategia principal.
                return selection
            ws.save("selection", selection, params)
            return selection

    @staticmethod
    def _remove_previous_exports(out_dir: Path) -> None:
        """Borra solo los clips que registró el manifest anterior (nunca otros ficheros)."""
        manifest = out_dir / "manifest.json"
        if not manifest.exists():
            return
        try:
            previous = JobResult.model_validate_json(manifest.read_text(encoding="utf-8"))
        except ValueError:
            return
        for exp in previous.exports:
            if Path(exp.path).parent.resolve() == out_dir.resolve():
                Path(exp.path).unlink(missing_ok=True)
        manifest.unlink()

    def _export(
        self,
        source: SourceVideo,
        transcript: Transcript,
        ranked: list[tuple[int, ClipCandidate]],
        ws: Workspace,
        opts: PipelineOptions,
        out_dir: Path,
        progress: ProgressReporter,
    ) -> list[ExportedClip]:
        profile = opts.profile
        reframer = self.c.reframer_factory(profile.reframe.value)
        exporter = self.c.exporter_factory(profile.exporter)
        exported: list[ExportedClip] = []
        failures: list[str] = []
        self._remove_previous_exports(out_dir)

        with stage("export"):
            for i, (rank, clip) in enumerate(ranked):
                bind_job(clip=rank)
                progress.report("export", i / max(len(ranked), 1))
                name = f"{rank:02d}_{slugify(clip.title)}"
                try:
                    plan = reframer.plan(source, clip, profile)
                    path = exporter.export(
                        ExportRequest(
                            source=source, clip=clip, rank=rank, profile=profile, reframe=plan,
                            transcript=transcript, output_path=out_dir / f"{name}.mp4",
                            work_dir=ws.subdir(f"render/{profile.name}/{rank:02d}"), branding=opts.branding,
                        )
                    )
                except ClipasoError as exc:
                    log.error("export.failed", error=str(exc), detail=exc.detail)
                    failures.append(f"{name}: {exc}")
                    continue
                thumbnail = self._thumbnail(path, clip.duration)
                exported.append(
                    ExportedClip(rank=rank, path=path, thumbnail=thumbnail, start=clip.start, end=clip.end,
                                 score=clip.score, title=clip.title, reason=clip.reason,
                                 description=clip.description, hashtags=clip.hashtags,
                                 reframe_mode=plan.mode, profile=profile.name)
                )
                log.info("export.done", file=path.name, reframe=plan.mode, notes=plan.notes)
            bind_job(clip=None)

        if ranked and not exported:
            raise RenderError("No se pudo exportar ningún clip", detail="\n".join(failures))
        return exported

    @staticmethod
    def _thumbnail(video: Path, duration: float) -> Path | None:
        thumb = video.with_suffix(".jpg")
        try:
            ffmpeg.thumbnail(video, thumb, at=min(1.5, duration / 2))
            return thumb
        except ClipasoError as exc:  # sin miniatura el clip sigue siendo válido
            log.warning("thumbnail.failed", error=str(exc))
            return None

    # ------------------------------------------------------------------ run

    def _open(self, uri: str, opts: PipelineOptions) -> tuple[SourceVideo, Workspace]:
        adapter = self.resolve_source(uri)
        source_id = adapter.source_id(uri)
        ws = Workspace(self.jobs_dir / source_id)
        bind_job(job=source_id)
        source = self._ingest(uri, ws, adapter)
        if opts.title:
            source = source.model_copy(update={"title": opts.title})
        return source, ws

    def run(
        self,
        uri: str,
        opts: PipelineOptions,
        *,
        out_dir: Path | None = None,
        on_progress: ProgressCallback | None = None,
        transcript: Transcript | None = None,
        signals: SignalSet | None = None,
    ) -> JobResult:
        """Procesa `uri`. `out_dir` fija dónde se escriben los clips (por defecto
        `output/<source_id>/<perfil>/`); `on_progress(stage, overall)` informa del avance.
        Con `transcript` y `signals` ya calculados (pedir más clips) se salta el análisis."""
        progress = ProgressReporter(on_progress)
        try:
            progress.report("ingest")
            source, ws = self._open(uri, opts)
            if transcript is None or signals is None:
                progress.report("audio")
                audio = self._audio(source, ws)
                progress.report("transcribe")
                transcript = self._transcribe(audio, ws, opts, progress)
                progress.report("signals")
                signals = self._signals(AnalysisContext(source, audio, transcript), ws, opts)
            progress.report("select")
            selection = self._select(
                SelectionRequest(
                    source=source, transcript=transcript, signals=signals, profile=opts.profile,
                    max_clips=opts.max_clips, language=opts.language or transcript.language,
                    extra={"topic": opts.topic, "exclude": [list(r) for r in opts.exclude]},
                ),
                ws,
                opts,
            )
            out_dir = out_dir or self.output_dir / source.source_id / opts.profile.name
            out_dir.mkdir(parents=True, exist_ok=True)
            progress.report("export")
            ranked = sorted(selection.clips, key=lambda c: c.score, reverse=True)
            exports = self._export(
                source, transcript, list(enumerate(ranked, start=opts.first_rank)), ws, opts, out_dir, progress
            )
            result = JobResult(source=source, selection=selection, exports=exports, cost_usd=self.c.cost.spent,
                               transcript=transcript, signals=signals)
            (out_dir / "manifest.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
            progress.report("export", 1.0)
            return result
        finally:
            clear_job()

    def subtitle(
        self,
        uri: str,
        opts: PipelineOptions,
        *,
        out_dir: Path,
        translate_to: str | None = None,
        on_progress: ProgressCallback | None = None,
        allow_silent: bool = False,
    ) -> JobResult:
        """Modo «solo subtitular»: el vídeo entero con subtítulos (traducidos si se pide), sin elegir momentos.
        También sirve para cambiar de formato; con `allow_silent`, un vídeo sin voz no es un error."""
        progress = ProgressReporter(on_progress, SUBTITLE_WEIGHTS)
        try:
            progress.report("ingest")
            source, ws = self._open(uri, opts)
            progress.report("audio")
            audio = self._audio(source, ws)
            progress.report("transcribe")
            transcript = self._transcribe(audio, ws, opts, progress)
            if not transcript.sentences and not allow_silent:
                raise ClipasoError("La transcripción está vacía")
            return self._whole_video(source, ws, audio, transcript, opts, out_dir, progress,
                                     translate_to if transcript.sentences else None, "subtitle")
        finally:
            clear_job()

    def clean(
        self,
        uri: str,
        opts: PipelineOptions,
        *,
        out_dir: Path,
        pace: PaceT = "normal",
        remove_fillers: bool = True,
        translate_to: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[JobResult, CutPlan]:
        """Quitar silencios y muletillas: el vídeo entero sin pausas largas ni «eh/em», con subtítulos.

        `result.source` es el vídeo ya limpio (sobre él trabajan después el editor y las portadas)."""
        progress = ProgressReporter(on_progress, CLEAN_WEIGHTS)
        try:
            progress.report("ingest")
            original, ws = self._open(uri, opts)
            progress.report("audio")
            audio = self._audio(original, ws)
            progress.report("transcribe")
            if remove_fillers:
                opts = replace(opts, transcribe_prompt=cleanup.verbatim_prompt(opts.language))
            transcript = self._transcribe(audio, ws, opts, progress)
            if not transcript.sentences:
                raise ClipasoError("La transcripción está vacía")
            progress.report("cut")
            with stage("cut"):
                plan = cleanup.plan_cuts(transcript, original.duration,
                                         cleanup.quiet_spans(audio, 0.1),
                                         pace, remove_fillers)
                log.info("clean.plan", **plan.stats(), cuts=len(plan.cuts))
                cleaned_path = cleanup.render(original.path, plan, out_dir / "limpio.mp4", ws.subdir("clean"))
            cleaned, cleaned_ws = self._open(str(cleaned_path), opts)
            cleaned_audio = self._audio(cleaned, cleaned_ws)
            result = self._whole_video(cleaned, cleaned_ws, cleaned_audio, cleanup.remap_transcript(transcript, plan),
                                       opts, out_dir, progress, translate_to, "clean")
            return result, plan
        finally:
            clear_job()

    def _whole_video(
        self,
        source: SourceVideo,
        ws: Workspace,
        audio: Path,
        transcript: Transcript,
        opts: PipelineOptions,
        out_dir: Path,
        progress: ProgressReporter,
        translate_to: str | None,
        strategy: str,
    ) -> JobResult:
        """El vídeo entero como un único «clip» con subtítulos (traducidos si se pide)."""
        progress.report("signals")
        signals = self._signals(AnalysisContext(source, audio, transcript), ws, opts)
        if translate_to and translate_to != transcript.language:
            if self.c.translator_factory is None:
                raise ClipasoError("Traducción no disponible")
            progress.report("translate")
            with stage("translate"):
                transcript = self.c.translator_factory().translate(
                    transcript, translate_to, on_progress=progress.stage_callback("translate"))
        whole = ClipCandidate(start=0.0, end=source.duration, first_sentence=0,
                              last_sentence=max(0, len(transcript.sentences) - 1), score=1.0,
                              title=opts.title or source.title or "Vídeo")
        out_dir.mkdir(parents=True, exist_ok=True)
        progress.report("export")
        exports = self._export(source, transcript, [(1, whole)], ws, opts, out_dir, progress)
        selection = Selection(strategy=strategy, clips=[whole])
        result = JobResult(source=source, selection=selection, exports=exports, cost_usd=self.c.cost.spent,
                           transcript=transcript, signals=signals)
        progress.report("export", 1.0)
        return result

    def render(
        self, uri: str, opts: PipelineOptions, clip: ClipCandidate, rank: int, transcript: Transcript, out_dir: Path
    ) -> ExportedClip:
        """Vuelve a exportar un clip concreto (editor: nuevo recorte, textos corregidos, otro estilo)."""
        try:
            source, ws = self._open(uri, opts)
            out_dir.mkdir(parents=True, exist_ok=True)
            exported = self._export(source, transcript, [(rank, clip)], ws, opts, out_dir, ProgressReporter(None))
            return exported[0]
        finally:
            clear_job()
