"""Quitar silencios y muletillas: detección, plan de cortes, nueva línea de tiempo y montaje."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from clipaso.application import cleanup
from clipaso.application.cleanup import CutPlan, is_filler, plan_cuts, remap_transcript, shift
from clipaso.domain.models import Sentence, Transcript, Word
from clipaso.infra import ffmpeg


def _transcript() -> Transcript:
    w = lambda t, a, b: Word(text=t, start=a, end=b)  # noqa: E731
    return Transcript(language="es", duration=4.0, sentences=[
        Sentence(index=0, start=0.1, end=1.0, text="Hola a todos.",
                 words=[w(" Hola", 0.1, 0.5), w(" a", 0.5, 0.6), w(" todos.", 0.6, 1.0)]),
        Sentence(index=1, start=2.6, end=3.4, text="Eh, vale.", words=[w(" Eh,", 2.6, 2.9), w(" vale.", 3.0, 3.4)]),
    ])


@pytest.mark.parametrize(("text", "language", "expected"), [
    (" Eh,", "es", True), ("Mmm...", "es", True), ("hmm", "en", True), (" Um.", "en", True), ("Ähm", "de", True),
    ("euh", "fr", True), ("em", "es", True), ("em", "ca", False), ("um", "pt", False), ("er", "de", False),
    ("am", "en", False), ("este", "es", False), ("e", "es", False), ("mesa", "es", False),
])
def test_fillers(text, language, expected):
    assert is_filler(text, language) is expected


def test_plan_shortens_pauses_and_removes_fillers():
    plan = plan_cuts(_transcript(), 4.0, [(1.0, 2.5), (3.5, 4.0)], "normal", remove_fillers=True)
    assert plan.cuts == [(1.15, 2.35), (2.6, 2.9), (3.6, 4.0)]
    assert (plan.pauses, plan.fillers) == (2, 1)
    assert plan.duration == pytest.approx(2.1)
    # Ritmo natural: la pausa de 1,5 s se acorta menos; sin muletillas, el «eh» se queda.
    natural = plan_cuts(_transcript(), 4.0, [(1.0, 2.5), (3.5, 4.0)], "natural", remove_fillers=False)
    assert natural.cuts[0] == (1.25, 2.25) and natural.fillers == 0


def test_filler_between_silences_becomes_one_short_pause():
    t = _transcript()
    plan = plan_cuts(t, 4.0, [(1.0, 2.6), (2.9, 3.0)], "normal")
    # silencio + «eh» + silencio = un bloque: queda una sola pausa corta (media en cada borde).
    assert plan.fillers == 1 and plan.pauses == 0 and plan.cuts == [(1.15, 2.9)]


def test_filler_is_widened_to_the_whole_sound():
    # Whisper marca «mmm» en 2,0-2,2 s, pero suena de 1,9 a 2,6 s (entre dos silencios): se quita entero.
    t = _transcript()
    t.sentences[1].words = [Word(text=" mmm,", start=2.0, end=2.2), Word(text=" vale.", start=3.5, end=3.9)]
    plan = plan_cuts(t, 4.0, [(1.0, 1.9), (2.6, 3.45)], "normal")
    assert plan.fillers == 1 and plan.cuts == [(1.15, 3.3)]


def test_speech_inside_a_quiet_span_is_protected():
    # El umbral de energía se equivoca y marca como silencio una palabra corta: no se corta.
    plan = plan_cuts(_transcript(), 4.0, [(0.3, 1.8)], "normal", remove_fillers=False)
    assert all(not (s < 0.8 < e) for s, e in plan.cuts)  # centro de «todos»


def test_without_energy_reference_uses_word_gaps_but_keeps_long_non_speech():
    plan = plan_cuts(_transcript(), 20.0, None, "normal", remove_fillers=False)
    assert (1.15, 2.45) in plan.cuts
    assert all(e <= 3.5 for _, e in plan.cuts)  # los 16 s finales sin voz (¿música?) se respetan


def test_remap_moves_words_and_drops_fillers():
    plan = CutPlan(cuts=[(1.15, 2.35), (2.6, 2.9), (3.6, 4.0)], original=4.0)
    assert shift(3.0, plan.cuts) == pytest.approx(1.5) and shift(2.7, plan.cuts) == pytest.approx(1.4)
    out = remap_transcript(_transcript(), plan)
    assert out.duration == pytest.approx(2.1)
    assert [w.text for s in out.sentences for w in s.words] == [" Hola", " a", " todos.", " Vale."]
    vale = out.sentences[1].words[0]
    assert (vale.start, vale.end) == (pytest.approx(1.5), pytest.approx(1.9))
    assert out.sentences[1].text == "Vale."


def test_never_leaves_an_empty_video():
    empty = Transcript(language="es", duration=10.0, sentences=[])
    assert plan_cuts(empty, 10.0, [(0.0, 10.0)], "fast").cuts == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")
def test_quiet_spans_and_render(tmp_path):
    video = tmp_path / "in.mp4"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-af", "volume='if(between(t,1,2.5)+gte(t,3.5),0,1)':eval=frame",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video),
    ], check=True)
    audio = ffmpeg.extract_audio(video, tmp_path / "a.wav")
    spans = cleanup.quiet_spans(audio, 0.1)
    assert spans and spans[0][0] == pytest.approx(1.0, abs=0.05) and spans[0][1] == pytest.approx(2.5, abs=0.05)

    plan = plan_cuts(_transcript(), 4.0, spans, "normal")
    out = cleanup.render(video, plan, tmp_path / "out.mp4", tmp_path / "work")
    _, _, _, duration = ffmpeg.video_info(out)
    assert duration == pytest.approx(plan.duration, abs=0.12)
    streams = {s["codec_type"] for s in ffmpeg.probe(out)["streams"]}
    assert streams == {"video", "audio"}
