"""Audiograma (fondo y render) y «del vídeo al texto» (textos de la IA y capítulos de YouTube)."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from PIL import Image

from clipaso.application import audiogram
from clipaso.application.audiogram import AudiogramStyle
from clipaso.application.cost import CostTracker
from clipaso.application.writer import TextWriter, _valid_chapters, chapters_text
from clipaso.domain.models import Sentence, Transcript, Word
from clipaso.domain.ports import LLMResponse, LLMUsage


def test_background_with_image_and_title(tmp_path):
    art = tmp_path / "art.png"
    Image.new("RGB", (800, 800), (200, 30, 30)).save(art)
    bg = audiogram.background(AudiogramStyle(width=540, height=960, title="Episodio 12: el miedo", image=art))
    assert bg.size == (540, 960)
    pos = audiogram.layout(AudiogramStyle(width=540, height=960))
    centre = bg.getpixel((270, pos["art_y"] + pos["art"] // 2))
    assert centre[0] > 150 and centre[1] < 80  # la portada, nítida en el centro
    plain = audiogram.background(AudiogramStyle(width=540, height=960, color="7C3AED"))
    assert plain.getpixel((5, 5)) != plain.getpixel((5, 950))  # degradado


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")
def test_render_audiogram_from_mp3(tmp_path):
    from clipaso.infra import ffmpeg

    mp3 = tmp_path / "voz.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
                    str(mp3)], check=True)
    out = audiogram.render(mp3, tmp_path / "a.mp4", tmp_path / "w", AudiogramStyle(width=360, height=640))
    w, h, _, d = ffmpeg.video_info(out)
    assert (w, h) == (360, 640) and d == pytest.approx(3.0, abs=0.2)
    assert {s["codec_type"] for s in ffmpeg.probe(out)["streams"]} == {"video", "audio"}


def test_chapters_follow_youtube_rules():
    raw = [{"start_seconds": 5, "title": "Intro"}, {"start_seconds": 8, "title": "Demasiado cerca"},
           {"start_seconds": 60, "title": "El experimento"}, {"start_seconds": 200, "title": "Conclusión"}]
    chapters = _valid_chapters(raw, duration=300)
    assert [c["start"] for c in chapters] == [0.0, 60.0, 200.0]  # el primero en 0 y separados ≥ 10 s
    assert chapters_text(chapters) == "00:00 Intro\n01:00 El experimento\n03:20 Conclusión"
    assert _valid_chapters(raw[:2], duration=300) == []  # menos de 3: no hay capítulos
    assert _valid_chapters(raw, duration=40) == []  # vídeo muy corto


class FakeLLM:
    model = "claude-haiku-test"
    billable = False

    def __init__(self):
        self.calls = []

    def estimate_input_tokens(self, text):
        return len(text) // 4

    def complete_json(self, *, system, user, schema, max_tokens=None, images=None):
        self.calls.append({"system": system, "user": user})
        return LLMResponse(data={
            "summary": "Resumen.", "key_points": ["Uno", " "], "chapters": [
                {"start_seconds": 0, "title": "Inicio"}, {"start_seconds": 30, "title": "Medio"},
                {"start_seconds": 70, "title": "Final"}],
            "blog_title": "Título", "blog_markdown": "## Hola\nTexto.", "linkedin": "Post", "thread": ["1/", "2/"],
            "seo_title": "SEO", "seo_description": "Desc", "seo_tags": ["#ia", "videos"],
        }, usage=LLMUsage(model=self.model, input_tokens=10, output_tokens=10, billable=False))


def test_writer_builds_all_texts():
    words = [Word(text=" Hola", start=0.0, end=0.5), Word(text=" mundo.", start=0.5, end=1.0)]
    t = Transcript(language="es", duration=100, sentences=[
        Sentence(index=0, start=0.0, end=1.0, text="Hola mundo.", words=words)])
    llm = FakeLLM()
    out = TextWriter(llm, CostTracker(budget_usd=1.0, pricing={})).write(t, duration=100, language="en", title="Charla")
    assert out["summary"] == "Resumen." and out["key_points"] == ["Uno"] and out["seo_tags"] == ["ia", "videos"]
    assert out["chapters_text"].startswith("00:00 Inicio") and out["language"] == "en"
    assert "in English" in llm.calls[0]["system"] and "[00:00] Hola mundo." in llm.calls[0]["user"]
