"""CLI de Clipaso.

    clipaso process <url|ruta> [--clips 5] [--profile vertical_9x16] [--strategy hybrid]
    clipaso doctor
    clipaso profiles
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from clipaso.domain.errors import ClipasoError
from clipaso.domain.models import ReframeMode
from clipaso.infra.config import get_settings
from clipaso.infra.logging import configure_logging
from clipaso.infra.tls import use_system_trust_store

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Genera clips cortos a partir de vídeos largos.")

STAGES = {"transcript", "signals", "selection"}


def _setup() -> None:
    # La consola de Windows no siempre usa UTF-8; evita errores con tildes y emojis.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    use_system_trust_store()
    s = get_settings()
    configure_logging(s.log_level, s.log_json)


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


@app.command()
def process(
    uri: Annotated[str, typer.Argument(help="Ruta a un vídeo local.")],
    clips: Annotated[int | None, typer.Option("--clips", "-n", help="Número de clips a generar.")] = None,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Perfil de salida (ver `profiles`).")] = None,
    strategy: Annotated[str | None, typer.Option(help="hybrid (Claude + señales) o heuristic (sin coste).")] = None,
    model: Annotated[str | None, typer.Option(help="Modelo: sonnet/opus (claude_cli) o id completo (API).")] = None,
    provider: Annotated[str | None, typer.Option(help="claude_cli (suscripción) o anthropic (API).")] = None,
    min_duration: Annotated[float | None, typer.Option("--min", help="Duración mínima (s).")] = None,
    max_duration: Annotated[float | None, typer.Option("--max", help="Duración máxima (s).")] = None,
    reframe: Annotated[ReframeMode | None, typer.Option(help="auto | face | blur_pad | center")] = None,
    subtitles: Annotated[bool | None, typer.Option("--subs/--no-subs", help="Subtítulos incrustados.")] = None,
    language: Annotated[str | None, typer.Option(help="Idioma del audio (es, en…). 'auto' para detectar.")] = None,
    force: Annotated[list[str] | None, typer.Option(help=f"Recalcular etapa ignorando caché: {sorted(STAGES)}")] = None,
) -> None:
    """Procesa un vídeo y exporta los mejores clips."""
    _setup()
    from clipaso.application.pipeline import PipelineOptions
    from clipaso.bootstrap import build_pipeline

    settings = get_settings()
    if provider:
        settings.llm.provider = provider  # type: ignore[assignment]
    if model:
        if settings.llm.provider == "claude_cli":
            settings.llm.cli_model = model
        else:
            settings.llm.model = model
    out_profile = settings.load_profile(profile or settings.default_profile)
    updates: dict = {}
    if min_duration is not None:
        updates["min_duration"] = min_duration
    if max_duration is not None:
        updates["max_duration"] = max_duration
    if min_duration is not None or max_duration is not None:
        lo = updates.get("min_duration", out_profile.min_duration)
        hi = updates.get("max_duration", out_profile.max_duration)
        if lo >= hi:
            raise typer.BadParameter("--min debe ser menor que --max")
        updates["target_duration"] = min(max(out_profile.target_duration, lo), hi)
    if reframe is not None:
        updates["reframe"] = reframe
    if subtitles is not None:
        updates["subtitles"] = out_profile.subtitles.model_copy(update={"enabled": subtitles})
    out_profile = out_profile.model_copy(update=updates)

    unknown = set(force or []) - STAGES
    if unknown:
        raise typer.BadParameter(f"Etapas desconocidas en --force: {', '.join(unknown)}")

    lang = language or settings.language
    try:
        pipeline = build_pipeline(settings, strategy)
        result = pipeline.run(
            uri,
            PipelineOptions(
                profile=out_profile,
                max_clips=clips or settings.default_clips,
                language=None if lang == "auto" else lang,
                force=set(force or []),
            ),
        )
    except ClipasoError as exc:
        typer.secho(f"\n✗ {exc}", fg=typer.colors.RED, err=True)
        if exc.detail:
            typer.secho(exc.detail, fg=typer.colors.BRIGHT_BLACK, err=True)
        raise typer.Exit(1) from exc

    typer.echo("")
    typer.secho(f"✓ {len(result.exports)} clips · estrategia: {result.selection.strategy} · "
                f"coste LLM: ${result.cost_usd:.3f}", fg=typer.colors.GREEN, bold=True)
    for note in result.selection.notes:
        typer.secho(f"  {note}", fg=typer.colors.BRIGHT_BLACK)
    clips_by_rank = sorted(result.selection.clips, key=lambda c: c.score, reverse=True)
    for exp, clip in zip(result.exports, clips_by_rank, strict=False):
        typer.echo(
            f"\n  #{exp.rank}  [{_fmt(exp.start)}–{_fmt(exp.end)}] {exp.end - exp.start:4.0f}s  "
            f"score {exp.score:.2f}  ({exp.reframe_mode})\n"
            f"      {exp.title}\n"
            f"      {clip.reason}\n"
            f"      → {exp.path}"
        )
    if result.exports:
        typer.echo(f"\nCarpeta: {Path(result.exports[0].path).parent}")


@app.command()
def profiles() -> None:
    """Lista los perfiles de salida disponibles."""
    _setup()
    s = get_settings()
    for name in s.list_profiles():
        p = s.load_profile(name)
        typer.echo(f"{name:18} {p.width}x{p.height}  {p.min_duration:.0f}-{p.max_duration:.0f}s  "
                   f"reframe={p.reframe.value}  subs={'sí' if p.subtitles.enabled else 'no'}")


@app.command()
def doctor() -> None:
    """Comprueba que el entorno está listo (ffmpeg, GPU, API key…)."""
    _setup()
    from clipaso.infra import ffmpeg
    from clipaso.infra.cuda import cuda_device_count

    s = get_settings()

    def check(label: str, ok: bool, detail: str = "") -> None:
        mark = typer.style("✓" if ok else "✗", fg=typer.colors.GREEN if ok else typer.colors.RED)
        typer.echo(f"  {mark} {label}{f'  ({detail})' if detail else ''}")

    typer.echo("Clipaso doctor\n")
    ff = shutil.which("ffmpeg")
    check("ffmpeg", bool(ff), ff or "instálalo y añádelo al PATH")
    check("ffprobe", bool(shutil.which("ffprobe")))
    if ff:
        check("NVENC (codificación por GPU)", ffmpeg.nvenc_available(), "si no, se usa libx264 (CPU)")
    n = cuda_device_count()
    check("CUDA para Whisper", n > 0, f"{n} GPU" if n else "se usará CPU (más lento)")
    typer.echo(f"  · proveedor LLM: {s.llm.provider}")
    if s.llm.provider == "claude_cli":
        from clipaso.adapters.llm.claude_cli import find_claude_executable

        try:
            exe = find_claude_executable()
            check("Claude Code", True, f"{exe} · modelo {s.llm.cli_model} · sesión: se verifica al usarlo")
        except ClipasoError as exc:
            check("Claude Code", False, str(exc))
    else:
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        check("ANTHROPIC_API_KEY", has_key, s.llm.model if has_key else "necesaria para el proveedor 'anthropic'")
        if has_key:
            try:
                import anthropic

                anthropic.Anthropic(max_retries=0, timeout=20).models.retrieve(s.llm.model)
                check("API de Anthropic", True, f"clave válida · {s.llm.model} disponible")
            except Exception as exc:
                check("API de Anthropic", False, _short(exc))
    check("Perfiles de salida", bool(s.list_profiles()), ", ".join(s.list_profiles()))

    typer.echo("\nServicios")
    _check_database(s, check)
    _check_storage(s, check)
    _check_auth(s, check)
    sentry_detail = "región UE" if ".de.sentry.io" in s.sentry_dsn else "sin DSN: errores solo en logs"
    check("Sentry", bool(s.sentry_dsn), sentry_detail)
    typer.echo(f"\n  datos: {s.data_dir}\n  salida: {s.output_dir}")


def _short(exc: Exception, limit: int = 160) -> str:
    text = " ".join(str(exc).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _check_database(s, check) -> None:
    from sqlalchemy import text

    from clipaso.saas.db import make_engine

    url = s.database_url()
    where = url.split("@")[-1] if "@" in url else url
    if "PEGA_AQUI" in url:
        check("Base de datos", False, "falta la cadena de conexión en .env (CLIPASO_DATABASE__URL)")
        return
    try:
        with make_engine(url).connect() as conn:
            conn.execute(text("select 1"))
        check("Base de datos", True, where)
    except Exception as exc:
        check("Base de datos", False, f"{where}: {_short(exc)}")


def _check_storage(s, check) -> None:
    import tempfile
    import uuid

    from clipaso.bootstrap import build_storage

    label = f"Almacenamiento ({s.storage.backend})"
    if s.storage.backend == "r2" and "PEGA_AQUI" in s.storage.r2_access_key_id + s.storage.r2_secret_access_key:
        check(label, False, "faltan las claves de R2 en .env")
        return
    try:
        storage = build_storage(s)
        key = f"healthcheck/{uuid.uuid4().hex}.txt"
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.txt"
            probe.write_text("ok", encoding="utf-8")
            storage.put_file(key, probe, "text/plain")
        ok = storage.size(key) == 2
        storage.delete_prefix(key)
        where = f"bucket {s.storage.r2_bucket} ({s.storage.r2_jurisdiction}) · " if s.storage.backend == "r2" else ""
        check(label, ok, f"{where}subir/leer/borrar OK" if ok else "no se pudo leer lo subido")
    except Exception as exc:
        check(label, False, _short(exc))


def _check_auth(s, check) -> None:
    if s.auth.mode == "dev":
        check("Login", True, "modo dev (email sin contraseña, solo local)")
        return
    import httpx

    url = f"{s.auth.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        keys = httpx.get(url, timeout=15).raise_for_status().json().get("keys", [])
        ok = bool(keys) or bool(s.auth.supabase_jwt_secret)
        check("Login (Supabase Auth)", ok, f"{len(keys)} clave(s) de firma públicas" if ok else "sin claves JWKS")
    except Exception as exc:
        check("Login (Supabase Auth)", False, _short(exc))


# --------------------------------------------------------------------------- SaaS


@app.command()
def api(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option(help="Recarga al cambiar el código (desarrollo).")] = False,
) -> None:
    """Arranca la API web (FastAPI)."""
    _setup()
    import uvicorn

    uvicorn.run("clipaso.interfaces.api.app:app", host=host, port=port, reload=reload, log_config=None)


@app.command()
def worker() -> None:
    """Procesa los vídeos encolados por la web (bucle; Ctrl+C para parar)."""
    _setup()
    import signal
    import threading

    from clipaso.bootstrap import build_storage
    from clipaso.saas.db import session_factory
    from clipaso.saas.migrations import upgrade_database
    from clipaso.saas.worker import JobRunner

    s = get_settings()
    if s.env == "dev":
        upgrade_database(s)
    from clipaso.infra.observability import init_sentry

    init_sentry(s, "worker")
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    JobRunner(s, session_factory(s), build_storage(s)).run_forever(stop)


@app.command()
def openapi(out: Annotated[Path, typer.Option(help="Fichero de salida.")] = Path("web/openapi.json")) -> None:
    """Exporta el esquema OpenAPI (el frontend genera sus tipos a partir de él)."""
    _setup()
    import json

    from clipaso.interfaces.api.app import create_app

    schema = create_app(get_settings(), migrate=False).openapi()
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.secho(f"✓ {out}", fg=typer.colors.GREEN)


@app.command()
def cleanup() -> None:
    """Borra clips caducados, subidas abandonadas y carpetas temporales (el worker lo hace cada hora)."""
    _setup()
    from clipaso.bootstrap import build_storage
    from clipaso.saas.db import session_factory
    from clipaso.saas.maintenance import run_cleanup

    s = get_settings()
    report = run_cleanup(s, session_factory(s), build_storage(s))
    typer.secho(
        f"✓ proyectos caducados: {report.expired_jobs} · subidas borradas: {report.purged_uploads} · "
        f"carpetas temporales: {report.workspaces}",
        fg=typer.colors.GREEN,
    )


@app.command("db-upgrade")
def db_upgrade() -> None:
    """Aplica las migraciones pendientes de la base de datos."""
    _setup()
    from clipaso.saas.migrations import upgrade_database

    upgrade_database(get_settings())
    typer.secho("✓ Base de datos al día", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
