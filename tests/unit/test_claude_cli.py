from __future__ import annotations

import json
import subprocess

import pytest

from smartcuts.adapters.llm.claude_cli import ClaudeCodeCLI
from smartcuts.application.cost import CostTracker
from smartcuts.domain.errors import ConfigurationError, LLMError


def completed(payload: dict | None, stderr: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, json.dumps(payload) if payload is not None else "", stderr)


SUCCESS = {
    "type": "result", "subtype": "success", "is_error": False, "session_id": "abc", "duration_ms": 1200,
    "result": '{"clips": []}', "structured_output": {"clips": [{"first_sentence": 1}]},
    "usage": {"input_tokens": 10, "output_tokens": 50, "cache_creation_input_tokens": 1400},
    "modelUsage": {"claude-haiku-4-5": {"outputTokens": 3}, "claude-sonnet-5": {"outputTokens": 50}},
}


def test_parses_structured_output_and_usage(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["env"], seen["input"] = cmd, kwargs["env"], kwargs["input"]
        return completed(SUCCESS)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("smartcuts.adapters.llm.claude_cli.find_claude_executable", lambda _=None: "claude")

    resp = ClaudeCodeCLI().complete_json(system="sys", user="transcripción larga", schema={"type": "object"})

    assert resp.data == {"clips": [{"first_sentence": 1}]}
    assert resp.usage.model == "claude-sonnet-5" and resp.usage.billable is False
    assert "ANTHROPIC_API_KEY" not in seen["env"]  # si no, facturaría por API
    assert seen["input"] == "transcripción larga"  # por stdin, no por argumento
    assert "--json-schema" in seen["cmd"] and "--tools" in seen["cmd"]


@pytest.mark.parametrize(
    ("result", "error"),
    [
        ("Invalid API key · Please run /login", ConfigurationError),
        ("Claude AI usage limit reached|1759000000", LLMError),
        ("algo raro", LLMError),
    ],
)
def test_maps_errors(result, error):
    payload = {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": result}
    with pytest.raises(error):
        ClaudeCodeCLI._parse(completed(payload, code=1))


def test_subscription_usage_costs_nothing():
    cost = CostTracker(budget_usd=0.0, pricing={"claude-sonnet-5": (2.0, 10.0)})
    resp_usage = ClaudeCodeCLI()._usage(SUCCESS)
    assert cost.record_llm(resp_usage) == 0.0 and cost.spent == 0.0
