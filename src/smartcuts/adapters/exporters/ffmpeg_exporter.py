"""Exporta un clip con ffmpeg: recorte temporal + reencuadre + subtítulos + audio normalizado."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from smartcuts.adapters.exporters.subtitles import build_ass
from smartcuts.domain.models import OutputProfile, Word
from smartcuts.domain.ports import ExportRequest
from smartcuts.infra import ffmpeg
from smartcuts.infra.logging import get_logger
from smartcuts.infra.registry import register

log = get_logger(__name__)


def video_codec_args(profile: OutputProfile) -> list[str]:
    enc = profile.encoding
    codec = enc.codec
    if codec == "auto":
        codec = "h264_nvenc" if ffmpeg.nvenc_available() else "libx264"
    if codec == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(enc.crf + 1), "-b:v", "0",
                "-profile:v", "high"]
    return ["-c:v", codec, "-preset", enc.preset, "-crf", str(enc.crf), "-profile:v", "high"]


@register("exporters", "ffmpeg")
class FFmpegExporter:
    name = "ffmpeg"

    def __init__(self, **_: Any) -> None:
        pass

    def export(self, request: ExportRequest) -> Path:
        clip, profile, plan = request.clip, request.profile, request.reframe
        work = request.work_dir
        work.mkdir(parents=True, exist_ok=True)

        if plan.sendcmd:
            (work / "reframe.cmd").write_text(plan.sendcmd, encoding="utf-8")

        filter_complex = plan.filter_complex
        if profile.subtitles.enabled:
            words = [
                Word(text=w.text, start=w.start - clip.start, end=w.end - clip.start, probability=w.probability)
                for w in request.transcript.words_between(clip.start, clip.end)
            ]
            ass = build_ass(words, profile.subtitles, profile.width, profile.height)
            (work / "subs.ass").write_text(ass, encoding="utf-8")
            filter_complex = filter_complex.replace("[vout]", "[vpre]") + ";[vpre]subtitles=subs.ass[vout]"

        (work / "filter.txt").write_text(filter_complex, encoding="utf-8")  # para depurar
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_filters = ["loudnorm=I=-14:TP=-1.5:LRA=11"] if profile.encoding.loudnorm else []
        args = [
            "-ss", f"{clip.start:.3f}", "-t", f"{clip.duration:.3f}",
            "-i", str(request.source.path),
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
                 duration=round(clip.duration, 1), reframe=plan.mode)
        # cwd=work: los filtros referencian reframe.cmd y subs.ass por nombre relativo,
        # lo que evita el infierno de escapar rutas de Windows dentro de filtergraphs.
        ffmpeg.run(args, cwd=work, what=f"exportación del clip {request.rank}")
        return request.output_path
