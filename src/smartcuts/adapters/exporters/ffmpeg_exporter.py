"""Exporta un clip con ffmpeg: recorte temporal + reencuadre + subtítulos + marca + audio normalizado."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from smartcuts.adapters.exporters.subtitles import FONTS_DIR, build_ass
from smartcuts.domain.models import Branding, OutputProfile, Word
from smartcuts.domain.ports import ExportRequest
from smartcuts.infra import ffmpeg
from smartcuts.infra.logging import get_logger
from smartcuts.infra.registry import register

log = get_logger(__name__)

LOGO_WIDTH_RATIO = 0.16  # ancho del logo respecto al ancho del vídeo
LOGO_MARGIN_RATIO = 0.035


def video_codec_args(profile: OutputProfile) -> list[str]:
    enc = profile.encoding
    codec = enc.codec
    if codec == "auto":
        codec = "h264_nvenc" if ffmpeg.nvenc_available() else "libx264"
    if codec == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(enc.crf + 1), "-b:v", "0",
                "-profile:v", "high"]
    return ["-c:v", codec, "-preset", enc.preset, "-crf", str(enc.crf), "-profile:v", "high"]


def _fonts_dir_for(work: Path) -> str:
    """Ruta a las fuentes relativa a `work` (evita escapar letras de unidad en el filtergraph)."""
    try:
        return Path(os.path.relpath(FONTS_DIR, work)).as_posix()
    except ValueError:  # otra unidad en Windows: se copian junto al trabajo
        local = work / "fonts"
        if not local.exists():
            shutil.copytree(FONTS_DIR, local)
        return "fonts"


def _logo_size(path: Path, width: int) -> tuple[int, int]:
    import cv2

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    w = int(width * LOGO_WIDTH_RATIO) // 2 * 2
    if img is None or img.shape[1] == 0:
        return w, w
    return w, int(w * img.shape[0] / img.shape[1]) // 2 * 2


def _logo_xy(position: str, logo_w: int, logo_h: int, margin: int) -> tuple[str, str]:
    x = f"{margin}" if position.endswith("left") else f"W-{logo_w}-{margin}"
    y = f"{margin}" if position.startswith("top") else f"H-{logo_h}-{margin}"
    return x, y


@register("exporters", "ffmpeg")
class FFmpegExporter:
    name = "ffmpeg"

    def __init__(self, **_: Any) -> None:
        pass

    def export(self, request: ExportRequest) -> Path:
        clip, profile, plan = request.clip, request.profile, request.reframe
        branding = request.branding or Branding()
        work = request.work_dir
        work.mkdir(parents=True, exist_ok=True)

        if plan.sendcmd:
            (work / "reframe.cmd").write_text(plan.sendcmd, encoding="utf-8")

        filter_complex = plan.filter_complex
        margin = int(min(profile.width, profile.height) * LOGO_MARGIN_RATIO)
        logo = branding.logo_path if branding.logo_path and Path(branding.logo_path).is_file() else None
        logo_w, logo_h = _logo_size(Path(logo), profile.width) if logo else (0, 0)

        if profile.subtitles.enabled or branding.handle.strip():
            words = [
                Word(text=w.text, start=w.start - clip.start, end=w.end - clip.start, probability=w.probability)
                for w in request.transcript.words_between(clip.start, clip.end)
            ]
            ass = build_ass(
                words, profile.subtitles, profile.width, profile.height,
                handle=branding.handle, handle_position=branding.position,
                handle_offset=(logo_h + margin // 2) if logo else 0, duration=clip.duration,
            )
            (work / "subs.ass").write_text(ass, encoding="utf-8")
            fonts = _fonts_dir_for(work)
            filter_complex = (
                filter_complex.replace("[vout]", "[vpre]") + f";[vpre]subtitles=subs.ass:fontsdir='{fonts}'[vout]"
            )

        if logo:
            shutil.copyfile(logo, work / "logo.png")
            x, y = _logo_xy(branding.position, logo_w, logo_h, margin)
            filter_complex = (
                filter_complex.replace("[vout]", "[vsub]")
                + f";[1:v]scale={logo_w}:{logo_h},format=rgba,colorchannelmixer=aa=0.92[logo]"
                + f";[vsub][logo]overlay={x}:{y}[vout]"
            )

        (work / "filter.txt").write_text(filter_complex, encoding="utf-8")  # para depurar
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_filters = ["loudnorm=I=-14:TP=-1.5:LRA=11"] if profile.encoding.loudnorm else []
        args = [
            "-ss", f"{clip.start:.3f}", "-t", f"{clip.duration:.3f}",
            "-i", str(request.source.path),
            *(["-i", "logo.png"] if logo else []),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "0:a:0?",
            *video_codec_args(profile),
            "-pix_fmt", "yuv420p",
            *(["-af", ",".join(audio_filters)] if audio_filters else []),
            "-c:a", "aac", "-b:a", profile.encoding.audio_bitrate, "-ar", "48000",
            "-movflags", "+faststart",
            str(request.output_path.resolve()),
        ]
        log.info("export.start", rank=request.rank, start=round(clip.start, 2),
                 duration=round(clip.duration, 1), reframe=plan.mode, logo=bool(logo), handle=bool(branding.handle))
        # cwd=work: los filtros referencian reframe.cmd, subs.ass y logo.png por nombre relativo,
        # lo que evita el infierno de escapar rutas de Windows dentro de filtergraphs.
        ffmpeg.run(args, cwd=work, what=f"exportación del clip {request.rank}")
        return request.output_path
