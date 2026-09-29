"""Cliente LLM a través de Claude Code en modo no interactivo (`claude -p`).

Usa la sesión con la que hayas hecho login en Claude Code, es decir, tu
suscripción de claude.ai (Pro/Max): no necesita API key ni se factura aparte;
consume de los límites de uso de tu plan. Pensado para uso personal; para un
producto con usuarios externos, usa el proveedor `anthropic` (API).

Requisitos: Claude Code instalado y con sesión iniciada (`claude` → /login).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from clipaso.domain.errors import ConfigurationError, LLMError
from clipaso.domain.ports import LLMResponse, LLMUsage
from clipaso.infra.logging import get_logger
from clipaso.infra.registry import register

log = get_logger(__name__)

_AUTH_HINTS = ("please run /login", "invalid api key", "not logged in", "authentication", "oauth")
_LIMIT_HINTS = ("usage limit", "rate limit", "limit reached", "overloaded")


def find_claude_executable(explicit: str | None = None) -> str:
    """Localiza el binario de Claude Code evitando el lanzador .cmd de npm en Windows
    (pasar un JSON Schema por cmd.exe rompe las comillas)."""
    path = explicit or shutil.which("claude")
    if not path:
        raise ConfigurationError(
            "No se encuentra Claude Code ('claude'). Instálalo y haz login, o usa --strategy heuristic."
        )
    if sys.platform == "win32" and path.lower().endswith((".cmd", ".bat")):
        native = Path(path).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if native.exists():
            return str(native)
    return path


@register("llm", "claude_cli")
class ClaudeCodeCLI:
    name = "claude_cli"
    billable = False  # va contra la suscripción, no contra el presupuesto en USD

    def __init__(
        self,
        cli_model: str = "sonnet",
        effort: str = "high",
        timeout_seconds: float = 600.0,
        cli_path: str | None = None,
        **_: Any,
    ) -> None:
        self.model = cli_model
        self.effort = effort
        self.timeout_seconds = timeout_seconds
        self.cli_path = cli_path

    def estimate_input_tokens(self, text: str) -> int:
        return int(len(text) / 3.2) + 50

    def complete_json(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int | None = None
    ) -> LLMResponse:
        exe = find_claude_executable(self.cli_path)
        # Sin ANTHROPIC_API_KEY en el entorno: si estuviera, Claude Code la usaría y facturaría por API.
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}

        with tempfile.TemporaryDirectory(prefix="clipaso-claude-") as tmp:
            system_file = Path(tmp) / "system.txt"
            system_file.write_text(system, encoding="utf-8")
            cmd = [
                exe, "-p",
                "--output-format", "json",
                "--json-schema", json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
                "--system-prompt-file", str(system_file),
                "--model", self.model,
                "--effort", self.effort,
                "--tools", "",                 # solo texto: sin herramientas ni acceso a ficheros
                "--no-session-persistence",
                "--strict-mcp-config",         # sin servidores MCP
                "--setting-sources", "",       # ignora hooks/ajustes de proyectos
            ]
            log.info("llm.claude_cli.request", model=self.model, prompt_chars=len(user))
            try:
                proc = subprocess.run(
                    cmd, input=user, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=env, cwd=tmp, timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise LLMError(f"Claude Code no respondió en {self.timeout_seconds:.0f} s") from exc

        payload = self._parse(proc)
        data = payload.get("structured_output")
        if data is None:
            try:
                data = json.loads(payload.get("result") or "")
            except json.JSONDecodeError as exc:
                raise LLMError("Claude Code no devolvió JSON estructurado",
                               detail=str(payload.get("result"))[:500]) from exc

        usage = self._usage(payload)
        log.info("llm.done", provider=self.name, model=usage.model, input_tokens=usage.input_tokens,
                 output_tokens=usage.output_tokens, seconds=round(payload.get("duration_ms", 0) / 1000, 1))
        return LLMResponse(data=data, usage=usage, request_id=payload.get("session_id"))

    @staticmethod
    def _parse(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        text = (proc.stdout or "").strip()
        payload: dict[str, Any] | None = None
        try:
            payload = json.loads(text) if text else None
        except json.JSONDecodeError:
            payload = None

        if payload is not None and not payload.get("is_error") and payload.get("subtype") == "success":
            return payload

        message = str((payload or {}).get("result") or proc.stderr or text or f"código {proc.returncode}")
        low = message.lower()
        if any(h in low for h in _AUTH_HINTS):
            raise ConfigurationError(
                "Claude Code no tiene sesión iniciada. Ejecuta `claude`, usa /login con tu cuenta y reintenta.",
                detail=message[:500],
            )
        if any(h in low for h in _LIMIT_HINTS):
            raise LLMError("Se alcanzó el límite de uso de tu plan de Claude; reintenta más tarde",
                           detail=message[:500])
        raise LLMError("Claude Code devolvió un error", detail=message[:1000])

    def _usage(self, payload: dict[str, Any]) -> LLMUsage:
        u = payload.get("usage") or {}
        models = payload.get("modelUsage") or {}
        # Claude Code usa además un modelo pequeño interno; nos quedamos con el que generó la respuesta.
        main = max(models.items(), key=lambda kv: kv[1].get("outputTokens", 0), default=(self.model, {}))[0]
        return LLMUsage(
            model=main,
            input_tokens=int(u.get("input_tokens") or 0),
            output_tokens=int(u.get("output_tokens") or 0),
            cache_read_tokens=int(u.get("cache_read_input_tokens") or 0),
            cache_write_tokens=int(u.get("cache_creation_input_tokens") or 0),
            billable=False,
        )
