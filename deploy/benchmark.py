"""Banco de medidas de coste en el hardware real (Modal, T4, región UE), fuera del flujo de producción.

    python deploy/modal_cli.py run deploy/benchmark.py            # todos los casos
    python deploy/modal_cli.py run deploy/benchmark.py --only clips  # solo los de un modo

Usa la misma imagen que el worker y los vídeos de prueba de `.bench/` (no se versionan). No toca la base de
datos ni R2: cada caso corre en una carpeta temporal y sin caché, como un proyecto nuevo. Mide por caso:
segundos de cada etapa, segundos de CPU (ffmpeg y Python), memoria máxima, coste de IA y peso de entrada y salida.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal
from modal_app import GPU, REGION, ROOT, image, secret

app = modal.App("clipaso-bench", image=image.add_local_dir(ROOT / ".bench", "/bench"))

SUBS = {"enabled": True, "font": "Montserrat", "animation": "highlight"}
# (vídeo, modo, opciones extra). Los tamaños y duraciones están en el README de .bench (ver deploy/benchmark.py).
CASES: list[tuple[str, str, dict]] = [
    ("c3_720.mp4", "clips", {"format": "vertical"}),
    ("c3_1080.mp4", "clips", {"format": "vertical"}),
    ("c1_4k.mp4", "clips", {"format": "vertical"}),
    ("c1_4k_hevc60.mp4", "clips", {"format": "vertical"}),
    ("c13_1080.mp4", "clips", {"format": "vertical"}),
    ("c3_720.mp4", "subtitle", {"format": "original"}),
    ("c3_1080.mp4", "subtitle", {"format": "original"}),
    ("c1_4k.mp4", "subtitle", {"format": "original"}),
    ("c13_1080.mp4", "subtitle", {"format": "original"}),
    ("c3_1080.mp4", "clean", {"format": "original"}),
    ("c1_4k.mp4", "clean", {"format": "original"}),
    ("c3_1080.mp4", "reframe", {"format": "vertical", "reframe_fit": "auto"}),
    ("c1_4k.mp4", "reframe", {"format": "vertical", "reframe_fit": "auto"}),
    ("c3_1080.mp4", "trailer", {"format": "vertical"}),
    ("c13_1080.mp4", "trailer", {"format": "vertical"}),
    ("a3.mp3", "audiogram", {"format": "vertical"}),
    ("c3_1080.mp4", "text", {}),
    ("c13_1080.mp4", "text", {}),
    ("a3.mp3", "text", {}),
]


def _run_case(name: str, mode: str, extra: dict, transcriber) -> dict:
    import resource
    import tempfile
    import time

    from clipaso.application.audiogram import AudiogramStyle
    from clipaso.application.pipeline import PipelineOptions
    from clipaso.application.writer import TextWriter
    from clipaso.bootstrap import build_cost_tracker, build_fast_llm, build_pipeline
    from clipaso.infra import ffmpeg
    from clipaso.infra.config import Settings
    from clipaso.saas import covers
    from clipaso.saas.artifacts import make_preview
    from clipaso.saas.rendering import project_profile

    src = Path("/bench") / name
    tmp = Path(tempfile.mkdtemp(prefix="bench-"))
    settings = Settings(data_dir=tmp / "data", output_dir=tmp / "out")  # sin caché de otros casos
    options = {"mode": mode, "caption_style": SUBS, **extra}
    if extra.get("format") == "original":
        w, h, _, _ = ffmpeg.video_info(src)
        options["source_size"] = [w, h]
    opts = PipelineOptions(profile=project_profile(settings, options), max_clips=3, language="es", title="Charla")
    pipeline = build_pipeline(settings, transcriber=transcriber)

    stages: dict[str, float] = {}
    state = {"stage": "start", "t": time.monotonic()}

    def on_progress(stage: str, _overall: float) -> None:
        now = time.monotonic()
        if stage != state["stage"]:
            stages[state["stage"]] = stages.get(state["stage"], 0.0) + now - state["t"]
            state["stage"], state["t"] = stage, now

    def rusage() -> float:
        me, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        return me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime

    cpu0, t0 = rusage(), time.monotonic()
    out = tmp / "result"
    result, source, llm_cost, extra_out = None, src, 0.0, {}
    if mode == "clips":
        result = pipeline.run(str(src), opts, out_dir=out, on_progress=on_progress)
    elif mode in ("subtitle", "reframe"):
        result = pipeline.subtitle(str(src), opts, out_dir=out, on_progress=on_progress, allow_silent=True)
    elif mode == "clean":
        result, plan = pipeline.clean(str(src), opts, out_dir=out, on_progress=on_progress)
        source, extra_out = result.source.path, plan.stats()
    elif mode == "trailer":
        result, plan = pipeline.trailer(str(src), opts, out_dir=out, seconds=60, on_progress=on_progress)
        source, extra_out = result.source.path, plan.stats()
    elif mode == "audiogram":
        style = AudiogramStyle(width=opts.profile.width, height=opts.profile.height, title="Episodio 1")
        result = pipeline.audiogram(str(src), opts, out_dir=out, style=style, on_progress=on_progress)
        source = result.source.path
    elif mode == "text":
        transcript, duration = pipeline.transcribe_only(str(src), opts, on_progress=on_progress)
        on_progress("write", 0.9)
        cost = build_cost_tracker(settings)
        texts = TextWriter(build_fast_llm(settings), cost).write(transcript, duration=duration, language="es")
        llm_cost += cost.spent
        extra_out = {"chapters": len(texts["chapters"]), "blog_words": len(texts["blog_markdown"].split())}
    on_progress("end", 1.0)
    pipeline_s = time.monotonic() - t0

    # Lo que hace el worker después del pipeline: portadas (IA con imágenes) y vista previa para el editor.
    cover_s = preview_s = 0.0
    output_bytes = 0
    if result is not None:
        llm_cost += result.cost_usd
        cost = build_cost_tracker(settings)
        llm = build_fast_llm(settings)
        detector = covers.face_detector(Path("/app/data/models"))
        t1 = time.monotonic()
        for exp in result.exports:
            covers.auto_cover(source if mode != "clips" else src, exp.start, exp.end, detector=detector, llm=llm,
                              transcript="", title=exp.title or "Clip", language="es", cost=cost)
            output_bytes += exp.path.stat().st_size
        cover_s = time.monotonic() - t1
        llm_cost += cost.spent
        if mode != "audiogram" and src.suffix != ".mp3":
            t2 = time.monotonic()
            preview = make_preview(Path(source), tmp / "preview.mp4")
            preview_s = time.monotonic() - t2
            output_bytes += preview.stat().st_size if preview else 0
    wall = time.monotonic() - t0
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    seconds = ffmpeg.audio_duration(src)
    row = {
        "file": name, "mode": mode, "minutes": round(seconds / 60, 2), "input_mb": round(src.stat().st_size / 1e6, 1),
        "wall_s": round(wall, 1), "pipeline_s": round(pipeline_s, 1), "cover_s": round(cover_s, 1),
        "preview_s": round(preview_s, 1), "cpu_s": round(rusage() - cpu0, 1),
        "peak_child_mb": round(kids.ru_maxrss / 1024), "llm_usd": round(llm_cost, 4),
        "output_mb": round(output_bytes / 1e6, 1), "clips": len(result.exports) if result else 0,
        "stages": {k: round(v, 1) for k, v in stages.items() if k != "start"}, **extra_out,
    }
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)
    return row


@app.function(gpu=GPU, region=REGION, secrets=[secret], timeout=3 * 60 * 60)
def run(only: str = "") -> list[dict]:
    import time

    import clipaso.bootstrap  # noqa: F401  registra los adaptadores (Whisper, LLM, exportador…)
    from clipaso.infra import registry
    from clipaso.infra.config import Settings

    t0 = time.monotonic()
    t = Settings().transcription
    transcriber = registry.create("transcribers", t.provider, **t.model_dump(exclude={"provider"}))
    transcriber._load()  # carga de Whisper: coste fijo de cada arranque en frío
    print(json.dumps({"whisper_load_s": round(time.monotonic() - t0, 1)}), flush=True)
    rows = []
    for name, mode, extra in CASES:
        if only and mode != only:
            continue
        try:
            row = _run_case(name, mode, extra, transcriber)
        except Exception as exc:  # un caso roto no para el banco
            row = {"file": name, "mode": mode, "error": f"{type(exc).__name__}: {exc}"[:300]}
        print(json.dumps(row, ensure_ascii=False), flush=True)
        rows.append(row)
    return rows


@app.local_entrypoint()
def main(only: str = "") -> None:
    rows = run.remote(only)
    out = ROOT / ".bench" / "results.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} casos → {out}")
