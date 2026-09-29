"""Tráiler: momentos elegidos por la IA (o heurística), ajuste de duración, nueva línea de tiempo y montaje."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from clipaso.application import trailer
from clipaso.application.cost import CostTracker
from clipaso.application.trailer import TrailerPlan, TrailerPlanner, remap_transcript, target_seconds
from clipaso.domain.errors import LLMError
from clipaso.domain.models import Sentence, Transcript, Word
from clipaso.domain.ports import LLMResponse, LLMUsage


def _cost() -> CostTracker:
    return CostTracker(budget_usd=1.0, pricing={})


def _transcript(n: int = 20, length: float = 4.0, gap: float = 1.0) -> Transcript:
    sentences = []
    t = 0.5
    for i in range(n):
        words = [Word(text=f" frase{i}", start=t, end=t + length / 2),
                 Word(text=" ok.", start=t + length / 2, end=t + length)]
        sentences.append(Sentence(index=i, start=t, end=t + length, text=f"frase{i} ok.", words=words))
        t += length + gap
    return Transcript(language="es", duration=t, sentences=sentences)


class FakeLLM:
    model = "claude-test"
    billable = False

    def __init__(self, moments=None, fail=False):
        self.moments = moments or []
        self.fail = fail
        self.users: list[str] = []

    def estimate_input_tokens(self, text):
        return len(text) // 4

    def complete_json(self, *, system, user, schema, max_tokens=None, images=None):
        self.users.append(user)
        if self.fail:
            raise LLMError("sin servicio")
        return LLMResponse(data={"moments": self.moments, "title": "Lo que nadie cuenta",
                                 "description": "Míralo entero.", "hashtags": ["#ia", "videos"]},
                           usage=LLMUsage(model=self.model, input_tokens=100, output_tokens=50, billable=False))


def test_target_never_exceeds_half_the_video():
    assert target_seconds(60, 600) == 60 and target_seconds(60, 80) == 40 and target_seconds(90, 10) == 10


def test_llm_moments_in_trailer_order_with_padding():
    t = _transcript()
    llm = FakeLLM([{"first_sentence": 15, "last_sentence": 15, "role": "gancho"},
                   {"first_sentence": 2, "last_sentence": 3, "role": "clave"},
                   {"first_sentence": 3, "last_sentence": 4, "role": "clave"},  # se solapa: fuera
                   {"first_sentence": 99, "last_sentence": 99, "role": "clave"},  # no existe: fuera
                   {"first_sentence": 18, "last_sentence": 18, "role": "cierre"}])
    plan = TrailerPlanner(llm, _cost()).plan(t, None, duration=t.duration, target=30, topic="dinero")
    s = t.sentences
    assert plan.segments[0] == (round(s[15].start - 0.08, 3), round(s[15].end + 0.25, 3))  # el gancho primero
    assert len(plan.segments) == 3 and plan.segments[-1][0] == round(s[18].start - 0.08, 3)
    assert plan.title == "Lo que nadie cuenta" and plan.hashtags == ["ia", "videos"] and plan.strategy == "llm"
    assert "<tema>dinero</tema>" in llm.users[0]


def test_long_proposals_are_trimmed_keeping_hook_and_ending():
    t = _transcript()
    llm = FakeLLM([{"first_sentence": i, "last_sentence": i, "role": "clave"} for i in range(0, 20, 2)])
    plan = TrailerPlanner(llm, _cost()).plan(t, None, duration=t.duration, target=12)
    assert plan.duration <= 12 * 1.2 and plan.segments[0][0] < 1 and plan.segments[-1][0] > t.sentences[17].start


def test_falls_back_to_heuristic_when_the_llm_fails():
    t = _transcript()
    plan = TrailerPlanner(FakeLLM(fail=True), _cost()).plan(t, None, duration=t.duration, target=30,
                                                                   title="Charla")
    assert plan.strategy == "heuristic" and plan.segments and plan.title == "Charla"
    assert plan.segments == sorted(plan.segments)  # en orden cronológico


def test_remap_puts_moments_one_after_another():
    t = _transcript()
    s = t.sentences
    out = remap_transcript(t, [(s[10].start, s[10].end), (s[2].start, s[2].end)])
    assert out.duration == pytest.approx(8.0)
    assert [x.text for x in out.sentences] == ["Frase10 ok.", "Frase2 ok."]
    assert out.sentences[1].start == pytest.approx(4.0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")
def test_render_joins_moments_in_order(tmp_path):
    from clipaso.infra import ffmpeg

    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=size=320x180:rate=25:duration=12",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-shortest", "-c:v", "libx264",
                    "-c:a", "aac", str(video)], check=True)
    plan = TrailerPlan(segments=[(8.0, 10.0), (1.0, 3.5), (5.0, 6.0)])
    out = trailer.render(video, plan, tmp_path / "t.mp4", tmp_path / "w", width=320, height=180, fps=25)
    _, _, _, duration = ffmpeg.video_info(out)
    assert duration == pytest.approx(5.5, abs=0.15)
    assert {s["codec_type"] for s in ffmpeg.probe(out)["streams"]} == {"video", "audio"}
