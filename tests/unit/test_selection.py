from __future__ import annotations

from typing import Any

import pytest

from clipaso.adapters.selection.heuristic import HeuristicSelector
from clipaso.adapters.selection.hybrid import HybridSelector
from clipaso.application.cost import CostTracker
from clipaso.domain.errors import BudgetExceededError, SelectionError
from clipaso.domain.ports import LLMResponse, LLMUsage, SelectionRequest


class FakeLLM:
    name = "fake"
    model = "claude-opus-5"

    def __init__(self, clips: list[dict[str, Any]]) -> None:
        self.clips = clips
        self.calls: list[str] = []

    def estimate_input_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete_json(self, *, system, user, schema, max_tokens=16000) -> LLMResponse:
        self.calls.append(user)
        return LLMResponse(data={"clips": self.clips}, usage=LLMUsage(self.model, 5000, 800))


def request(source, transcript, signals, profile, n=3) -> SelectionRequest:
    return SelectionRequest(source=source, transcript=transcript, signals=signals, profile=profile, max_clips=n)


def test_heuristic_finds_energy_peak(source, transcript, signals, profile):
    sel = HeuristicSelector(weights={"audio_energy": 1.0}).select(request(source, transcript, signals, profile))
    assert sel.clips
    best = max(sel.clips, key=lambda c: c.score)
    assert best.start < 80 and best.end > 60
    for c in sel.clips:
        assert profile.min_duration <= c.duration <= profile.max_duration + 1


def test_hybrid_uses_llm_ranges_and_fixes_durations(source, transcript, signals, profile):
    s = transcript.sentences
    llm = FakeLLM([
        {"first_sentence": 0, "last_sentence": len(s) - 1, "score": 90, "title": "Demasiado largo",
         "hook": "", "reason": ""},
        {"first_sentence": 10, "last_sentence": 13, "score": 70, "title": "Bueno", "hook": "", "reason": "ok"},
        {"first_sentence": 999, "last_sentence": 1000, "score": 99, "title": "Inválido", "hook": "", "reason": ""},
    ])
    cost = CostTracker(budget_usd=1.0, pricing={"claude-opus-5": (5.0, 25.0)})
    sel = HybridSelector(llm=llm, cost=cost).select(request(source, transcript, signals, profile))

    assert len(sel.clips) == 2  # el inválido se descarta; el largo se recorta
    assert all(profile.min_duration * 0.85 <= c.duration <= profile.max_duration + 1 for c in sel.clips)
    assert "(señal" in llm.calls[0] and "[0]" in llm.calls[0]
    assert cost.spent == pytest.approx((5000 * 5 + 800 * 25) / 1e6)


def test_hybrid_respects_budget(source, transcript, signals, profile):
    cost = CostTracker(budget_usd=0.0001, pricing={"claude-opus-5": (5.0, 25.0)})
    llm = FakeLLM([])
    with pytest.raises(BudgetExceededError):
        HybridSelector(llm=llm, cost=cost).select(request(source, transcript, signals, profile))
    assert llm.calls == []  # no se llega a llamar a la API


def test_hybrid_raises_when_nothing_valid(source, transcript, signals, profile):
    cost = CostTracker(budget_usd=1.0, pricing={"claude-opus-5": (5.0, 25.0)})
    with pytest.raises(SelectionError):
        HybridSelector(llm=FakeLLM([]), cost=cost).select(request(source, transcript, signals, profile))
