from __future__ import annotations

import shutil

import numpy as np
import pytest

from clipaso.adapters.exporters.subtitles import ass_color, ass_time, build_ass
from clipaso.adapters.reframing.face_track import camera_path, sendcmd_script
from clipaso.application.workspace import Workspace
from clipaso.domain.errors import ConfigurationError
from clipaso.domain.models import SubtitleStyle, Transcript
from clipaso.infra import registry
from tests.conftest import make_words


def test_registry_unknown_name():
    import clipaso.adapters  # noqa: F401

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
    from clipaso.adapters.exporters.subtitles import build_ass
    from clipaso.domain.models import SubtitleStyle, Word

    style = SubtitleStyle(font="Arial Black", position="top", box=True, box_color="112233")
    ass = build_ass([Word(text=" hola", start=0, end=0.5)], style, 1080, 1920, handle="@ana",
                    handle_position="bottom-left", duration=5)
    default = next(line for line in ass.splitlines() if line.startswith("Style: Default"))
    fields = default.split(",")
    assert fields[1] == "Archivo Black"  # alias a la fuente incluida
    assert fields[15] == "3" and fields[18] == "8"  # caja opaca, alineada arriba
    assert "Dialogue: 1,0:00:00.00,0:00:05.00,Handle,,0,0,0,,@ana" in ass


def test_build_ass_animations_and_exact_position():
    words = make_words("uno dos tres")

    def lines(**kw):
        ass = build_ass(words, SubtitleStyle(max_words=3, **kw), 1080, 1920)
        return [line.split(",,0,0,0,,", 1)[1] for line in ass.splitlines() if line.startswith("Dialogue")]

    hl, pr = r"{\c&H00FFE500}", r"{\c&H00FFFFFF}"
    hidden = r"{\alpha&HFF&}"
    assert lines(animation="karaoke")[1] == f"{hl}UNO{pr} {hl}DOS{pr} TRES"
    assert lines(animation="appear")[0] == f"{hl}UNO{pr} {hidden}DOS {hidden}TRES"
    assert r"\t(0,90,\fscx122\fscy122)" in lines(animation="pop")[2]
    assert lines(animation="none") == ["UNO DOS TRES"]
    assert lines(pos_y=0.4, animation="none")[0].startswith(r"{\an5\pos(540,768)}")


def test_build_ass_box_opacity_and_no_outline():
    ass = build_ass(make_words("hola"), SubtitleStyle(box=True, box_color="112233", box_opacity=60), 1080, 1920)
    default = next(line for line in ass.splitlines() if line.startswith("Style: Default")).split(",")
    assert default[5] == "&H66332211"  # 40 % transparente
    ass = build_ass(make_words("hola"), SubtitleStyle(outline_ratio=0, shadow_ratio=0), 1080, 1920)
    default = next(line for line in ass.splitlines() if line.startswith("Style: Default")).split(",")
    assert default[7] == "0" and (default[16], default[17]) == ("0", "0")  # sin negrita falsa, sin contorno


def test_build_captions_srt_and_vtt():
    from clipaso.adapters.exporters.subtitles import build_captions
    from clipaso.domain.models import Word

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

    from clipaso.adapters.exporters.ffmpeg_exporter import FFmpegExporter
    from clipaso.domain.models import (
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
    from clipaso.domain.ports import ExportRequest, ReframePlan

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


def test_chunk_words_respects_user_breaks():
    from clipaso.adapters.exporters.subtitles import chunk_words

    words = make_words("uno dos tres cuatro")
    words[0] = words[0].model_copy(update={"brk": "split"})
    words[2] = words[2].model_copy(update={"brk": "join"})
    chunks = chunk_words(words, max_words=3, max_seconds=10)
    assert [[w.text.strip() for w in c] for c in chunks] == [["uno"], ["dos", "tres", "cuatro"]]


def test_translator_keeps_sentence_timing():
    from clipaso.application.cost import CostTracker
    from clipaso.application.translation import Translator
    from clipaso.domain.models import Sentence, Word
    from clipaso.domain.ports import LLMResponse, LLMUsage

    class FakeLLM:
        name, model, billable = "fake", "claude-haiku-4-5", True

        def __init__(self):
            self.users = []

        def estimate_input_tokens(self, text):
            return len(text) // 3

        def complete_json(self, *, system, user, schema, max_tokens=None):
            import json

            self.users.append(user)
            items = [json.loads(line) for line in user.splitlines()]
            texts = {0: "Hello everyone, this is Clipaso.", 1: "See you later."}
            return LLMResponse(data={"items": [{"i": it["i"], "text": texts[it["i"]]} for it in items]},
                               usage=LLMUsage(model=self.model, input_tokens=100, output_tokens=20))

    names = ["Hola", "a", "todos", "esto", "es"]
    words = [Word(text=f" {w}", start=i * 0.5, end=i * 0.5 + 0.4) for i, w in enumerate(names)]
    transcript = Transcript(language="es", duration=10, sentences=[
        Sentence(index=0, start=0, end=2.4, text="Hola a todos, esto es Clipaso.", words=words),
        Sentence(index=1, start=5, end=6, text="Hasta luego.",
                 words=[Word(text=" Hasta", start=5, end=5.4), Word(text=" luego.", start=5.5, end=6)]),
    ])
    llm = FakeLLM()
    cost = CostTracker(budget_usd=1, pricing={"claude-haiku-4-5": (1.0, 5.0)})
    out = Translator(llm, cost).translate(transcript, "en")
    assert out.language == "en" and out.sentences[0].text == "Hello everyone, this is Clipaso."
    first = out.sentences[0].words
    assert [w.text.strip() for w in first] == ["Hello", "everyone,", "this", "is", "Clipaso."]
    assert first[0].start == 0 and first[-1].end <= 2.4 + 1e-6
    assert all(a.start <= b.start for a, b in zip(first, first[1:], strict=False))
    second = out.sentences[1].words
    assert second[0].start >= 5 and second[-1].end == 6  # cada frase se queda en su tramo
    assert '"text": "Hola a todos, esto es Clipaso."' in llm.users[0] and cost.spent > 0


def test_cover_compose_and_fit():
    from clipaso.saas import covers
    from clipaso.saas.presets import PRESETS_BY_ID

    frame = np.full((720, 1280, 3), 120, np.uint8)
    vertical = covers.fit(frame, covers.SIZES["vertical"], face_x=0.8)
    assert vertical.shape[:2] == (1920, 1080)
    tall = np.full((1920, 1080, 3), 90, np.uint8)
    assert covers.fit(tall, covers.SIZES["horizontal"]).shape[:2] == (720, 1280)  # fondo difuminado
    base = covers.to_jpeg(vertical)
    for template in covers.TEMPLATES:
        for preset in ("clasico", "caja"):
            out = covers.compose(base, covers.SIZES["vertical"], text="Un texto bastante largo para portada",
                                 highlight=2, template=template, style=PRESETS_BY_ID[preset].style)
            assert covers.from_jpeg(out).shape[:2] == (1920, 1080)
