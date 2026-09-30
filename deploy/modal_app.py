"""Worker de Clipaso en Modal: una GPU por vídeo, que solo cuesta mientras procesa.

    modal run deploy/modal_app.py::smoke   # comprueba la imagen (GPU, Whisper, ffmpeg, fuentes)
    modal deploy deploy/modal_app.py       # publica el worker y las tareas periódicas

La API (dispatcher "modal") llama a `Worker.process(job_id)` por cada job nuevo.
Además corren dos tareas programadas:
- cada 5 min, `sweep`: reencola jobs de workers caídos y reenvía los que no llegaron a arrancar;
- cada hora, `cleanup`: caducidad de clips y borrado de subidas abandonadas.

La configuración (base de datos, R2, Anthropic, Sentry) llega del secreto
`clipaso-worker` de Modal; se crea con `deploy/modal_secret.py`.
"""

from __future__ import annotations

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "clipaso-worker"
GPU = "T4"  # 16 GB, la más barata; Whisper large-v3-turbo transcribe ~20x más rápido que tiempo real
REGION = "eu"  # los vídeos de los usuarios no salen de la UE
SITE = "/usr/local/lib/python3.12/site-packages"
WHISPER_MODEL = "large-v3-turbo"
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
# Los subtítulos usan "Arial Black", que no existe en Linux: Archivo Black (libre, OFL) es casi idéntica.
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf"
FONT_ALIAS = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias binding="same"><family>Arial Black</family><prefer><family>Archivo Black</family></prefer></alias>
</fontconfig>
"""


def _bake_assets() -> None:
    """Se ejecuta al construir la imagen: modelos y fuentes quedan dentro (arranques rápidos, sin descargas)."""
    import urllib.request

    from faster_whisper import download_model

    download_model(WHISPER_MODEL)
    models = Path("/app/data/models")
    models.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(YUNET_URL, models / "face_detection_yunet_2023mar.onnx")
    fonts = Path("/usr/local/share/fonts/clipaso")
    fonts.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(FONT_URL, fonts / "ArchivoBlack-Regular.ttf")
    Path("/etc/fonts/conf.d/99-clipaso-arial-black.conf").write_text(FONT_ALIAS)


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "fontconfig")
    .pip_install_from_pyproject(str(ROOT / "pyproject.toml"), optional_dependencies=["gpu"])
    .env({
        # cuBLAS y cuDNN vienen de los paquetes pip nvidia-* (extra "gpu"); CTranslate2 los busca aquí.
        "LD_LIBRARY_PATH": f"{SITE}/nvidia/cublas/lib:{SITE}/nvidia/cudnn/lib",
    })
    .run_function(_bake_assets)
    .run_commands("fc-cache -f")
    .env({
        "HF_HUB_OFFLINE": "1",  # el modelo ya está en la imagen
        "PYTHONPATH": "/app/src",
        "CLIPASO_LOG_JSON": "true",
        "CLIPASO_WORKER__DISPATCHER": "modal",
        "CLIPASO_WORKER__MODAL_APP": APP_NAME,
    })
    # El código va al final: cambiarlo no reconstruye las capas pesadas de arriba.
    .add_local_dir(ROOT / "src", "/app/src", ignore=["**/__pycache__"])
    .add_local_dir(ROOT / "configs", "/app/configs")
    .add_local_dir(ROOT / "assets", "/app/assets")
)

app = modal.App(APP_NAME, image=image)
secret = modal.Secret.from_name("clipaso-worker")


def _context(component: str):
    from clipaso.bootstrap import build_storage
    from clipaso.infra.config import get_settings
    from clipaso.infra.logging import configure_logging
    from clipaso.infra.observability import init_sentry
    from clipaso.saas.db import session_factory

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    init_sentry(settings, component)
    return settings, session_factory(settings), build_storage(settings)


@app.cls(
    gpu=GPU,
    region=REGION,
    secrets=[secret],
    timeout=2 * 60 * 60,  # vídeos de hasta 3 h en el plan Pro
    # Si llega otro vídeo en el minuto siguiente, reutiliza la GPU con Whisper cargado. Medido (banco de costes):
    # cada minuto encendida sin trabajo cuesta ~0,012 $ y un arranque en frío apenas unos segundos.
    scaledown_window=60,
    max_containers=5,  # techo de GPUs simultáneas (control de gasto)
)
class Worker:
    @modal.enter()
    def setup(self) -> None:
        from clipaso.saas.worker import JobRunner

        self.runner = JobRunner(*_context("worker"))

    @modal.method()
    def process(self, job_id: str) -> bool:
        return self.runner.process(job_id)

    @modal.method()
    def run_task(self, task_id: str) -> bool:
        """Re-render de un clip editado o más clips del mismo vídeo."""
        return self.runner.tasks.process(task_id)


@app.function(region=REGION, secrets=[secret], schedule=modal.Period(minutes=5), timeout=300)
def sweep() -> None:
    from clipaso.saas.dispatch import get_dispatcher, redispatch_queued
    from clipaso.saas.worker import JobRunner

    settings, sessions, storage = _context("sweep")
    runner = JobRunner(settings, sessions, storage)
    runner.recover_stale()
    runner.tasks.recover_stale()
    redispatch_queued(settings, sessions, get_dispatcher(settings))


@app.function(region=REGION, secrets=[secret], schedule=modal.Period(hours=1), timeout=900)
def cleanup() -> None:
    from clipaso.saas.maintenance import run_cleanup

    run_cleanup(*_context("cleanup"))


@app.function(region=REGION, secrets=[secret], schedule=modal.Cron("30 3 * * *"), timeout=900)
def backup() -> None:
    """Copia diaria de la base de datos en R2 (se guardan 30 días). Si falla, avisa en Sentry."""
    from clipaso.saas.backup import run_backup
    from clipaso.saas.db import utcnow

    _, sessions, storage = _context("backup")
    run_backup(sessions, storage, utcnow())


@app.function(gpu=GPU, region=REGION, timeout=600)
def smoke() -> dict:
    """Diagnóstico de la imagen, sin tocar base de datos ni almacenamiento."""
    import subprocess
    import tempfile

    from clipaso.infra import ffmpeg
    from clipaso.infra.cuda import cuda_device_count

    report: dict = {"cuda_devices": cuda_device_count(), "nvenc": ffmpeg.nvenc_available()}
    report["font"] = subprocess.run(["fc-match", "Arial Black"], capture_output=True, text=True).stdout.strip()
    report["yunet"] = Path("/app/data/models/face_detection_yunet_2023mar.onnx").exists()

    # Las fuentes de los subtítulos (assets/fonts) deben resolverse sin caer en otra por defecto.
    from clipaso.adapters.exporters.ffmpeg_exporter import _fonts_dir_for
    from clipaso.adapters.exporters.subtitles import build_ass
    from clipaso.domain.models import SubtitleStyle, Word

    fonts_ok = {}
    from clipaso.saas.presets import FONTS

    for font in FONTS.values():
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "subs.ass").write_text(build_ass([Word(text=" hola", start=0, end=1)], SubtitleStyle(font=font),
                                                     360, 640), encoding="utf-8")
            log = subprocess.run(
                ["ffmpeg", "-v", "verbose", "-f", "lavfi", "-i", "color=s=360x640:d=1",
                 "-vf", f"subtitles=subs.ass:fontsdir='{_fonts_dir_for(work)}'", "-frames:v", "1", "-f", "null", "-"],
                cwd=work, capture_output=True, text=True,
            ).stderr
            chosen = next((ln.split("->")[-1].strip() for ln in log.splitlines() if "fontselect" in ln), "?")
            fonts_ok[font] = chosen
    report["subtitle_fonts"] = fonts_ok

    from clipaso.adapters.transcription.faster_whisper import FasterWhisperTranscriber

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "tone.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(wav)],
                       check=True)
        t = FasterWhisperTranscriber(model=WHISPER_MODEL, device="cuda")
        t.transcribe(wav, "es")
        report["whisper"] = "ok"
    print(report)
    return report
