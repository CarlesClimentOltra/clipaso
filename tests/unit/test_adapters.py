from __future__ import annotations

import shutil

import numpy as np
import pytest

from smartcuts.adapters.exporters.subtitles import ass_color, ass_time, build_ass
from smartcuts.adapters.reframing.face_track import camera_path, sendcmd_script
from smartcuts.application.workspace import Workspace
from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.models import SubtitleStyle, Transcript
from smartcuts.infra import registry
from tests.conftest import make_words


def test_registry_unknown_name():
    import smartcuts.adapters  # noqa: F401

    with pytest.raises(ConfigurationError, match="Disponibles"):
        registry.create("selectors", "no-existe")


def test_workspace_cache_invalidates_on_param_change(tmp_path):
    ws = Workspace(tmp_path)
    t = Transcript(language="es", duration=1, sentences=[])
    ws.save("transcript", t, {"model": "a"})
    assert ws.load("transcript", Transcript, {"model": "a"}) == t
    assert ws.load("transcript", Transcript, {"model": "b"}) is None


def test_ass_helpers():
    assert ass_color("00E5FF") == "&H00FFE500"
    assert ass_time(3723.456) == "1:02:03.46"


def test_build_ass_highlights_each_word():
    words = make_words("hola qué tal. esto va bien")
    ass = build_ass(words, SubtitleStyle(max_words=3), 1080, 1920)
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue")]
    assert len(dialogues) == len(words)
    assert "{\\c&H00FFE500}HOLA{\\c&H00FFFFFF} QUÉ TAL" in dialogues[0]
    assert "PlayResY: 1920" in ass


def test_camera_holds_still_inside_dead_zone_and_jumps_on_cut():
    centers = np.array([0.50, 0.52, 0.49, 0.51, 0.50, 0.85, 0.86, 0.85, 0.84, 0.85])
    cam, cuts = camera_path(centers, dead_zone=0.05, cut_jump=0.18, follow=0.35, median_window=1)
    assert np.allclose(cam[:5], 0.50)
    assert cuts[5] and cam[5] == pytest.approx(0.85)


def test_camera_fills_missing_detections():
    centers = np.array([np.nan, np.nan, 0.3, np.nan, 0.3])
    cam, _ = camera_path(centers, dead_zone=0.05, cut_jump=0.5, follow=0.5, median_window=1)
    assert np.allclose(cam, 0.3)


def test_sendcmd_script_clamps_to_frame():
    times = np.array([0.0, 1.0])
    cam = np.array([0.0, 1.0])
    x0, script = sendcmd_script(times, cam, np.array([False, False]), src_w=1920, crop_w=606, duration=1.0)
    xs = [int(line.split()[-1].rstrip(";")) for line in script.strip().splitlines()]
    assert x0 == 0 and min(xs) >= 0 and max(xs) <= 1920 - 606
    assert all(x % 2 == 0 for x in xs)


def test_build_ass_styles_box_position_and_handle():
    from smartcuts.adapters.exporters.subtitles import build_ass
    from smartcuts.domain.models import SubtitleStyle, Word

    style = SubtitleStyle(font="Arial Black", position="top", box=True, box_color="112233")
    ass = build_ass([Word(text=" hola", start=0, end=0.5)], style, 1080, 1920, handle="@ana",
                    handle_position="bottom-left", duration=5)
    default = next(line for line in ass.splitlines() if line.startswith("Style: Default"))
    fields = default.split(",")
    assert fields[1] == "Archivo Black"  # alias a la fuente incluida
    assert fields[15] == "3" and fields[18] == "8"  # caja opaca, alineada arriba
    assert "Dialogue: 1,0:00:00.00,0:00:05.00,Handle,,0,0,0,,@ana" in ass


def test_build_captions_srt_and_vtt():
    from smartcuts.adapters.exporters.subtitles import build_captions
    from smartcuts.domain.models import Word

    words = [Word(text=" Hola,", start=0.0, end=0.4), Word(text=" mundo", start=0.5, end=1.25)]
    srt = build_captions(words, "srt")
    assert srt.startswith("1\n00:00:00,000 --> 00:00:00,400\nHola,\n")
    assert "2\n00:00:00,500 --> 00:00:01,250\nmundo" in srt
    assert build_captions(words, "vtt").startswith("WEBVTT\n\n00:00:00.000 --> 00:00:00.400")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")
def test_exporter_renders_logo_handle_and_styled_subtitles(tmp_path):
    import subprocess

    import cv2
    import numpy as np

    from smartcuts.adapters.exporters.ffmpeg_exporter import FFmpegExporter
    from smartcuts.domain.models import (
        Branding,
        ClipCandidate,
        OutputProfile,
        Sentence,
        SourceVideo,
        SubtitleStyle,
        Transcript,
        VideoEncoding,
        Word,
    )
    from smartcuts.domain.ports import ExportRequest, ReframePlan

    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=640x360:d=2:r=25",
                    "-f", "lavfi", "-i", "sine=d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)],
                   check=True)
    logo = tmp_path / "logo.png"
    img = np.zeros((100, 200, 4), np.uint8)
    img[:, :, 2], img[:, :, 3] = 255, 255  # rojo opaco
    cv2.imwrite(str(logo), img)
    words = [Word(text=" hola", start=0.2, end=0.6), Word(text=" mundo", start=0.7, end=1.2)]
    transcript = Transcript(language="es", duration=2, sentences=[
        Sentence(index=0, start=0.2, end=1.2, text="hola mundo", words=words)])
    profile = OutputProfile(name="t", width=360, height=640, subtitles=SubtitleStyle(font="Anton", box=True),
                            encoding=VideoEncoding(codec="libx264", loudnorm=False))
    out = tmp_path / "out.mp4"
    FFmpegExporter().export(ExportRequest(
        source=SourceVideo(source_id="s", provider="local", uri=str(src), path=src, duration=2, width=640,
                           height=360, fps=25),
        clip=ClipCandidate(start=0, end=1.5, first_sentence=0, last_sentence=0, score=1),
        rank=1, profile=profile,
        reframe=ReframePlan(mode="center", filter_complex="[0:v]scale=-2:640,crop=360:640[vout]"),
        transcript=transcript, output_path=out, work_dir=tmp_path / "work",
        branding=Branding(handle="@ana", logo_path=logo, position="top-left"),
    ))
    frame = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-i", str(out), "-frames:v", "1", str(frame)],
                   check=True)
    pixels = cv2.imread(str(frame))
    b, g, r = pixels[20:40, 20:40].mean(axis=(0, 1))  # esquina superior izquierda: el logo
    assert r > 200 and g < 60 and b < 60
