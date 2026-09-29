"""Cliente LLM sobre la API de Anthropic (Claude).

Credenciales: `ANTHROPIC_API_KEY` en el entorno o en `.env` (o un perfil de
`ant auth login`). Ojo: la suscripción Claude Pro/Max NO incluye acceso a la
API; la API se factura aparte desde https://platform.claude.com.
"""

from __future__ import annotations

import json
from typing import Any

from clipaso.domain.errors import ConfigurationError, LLMError
from clipaso.domain.ports import LLMResponse, LLMUsage
from clipaso.infra.logging import get_logger
from clipaso.infra.registry import register

log = get_logger(__name__)

# Modelos con adaptive thinking + effort. Haiku 4.5 no admite ninguno de los dos.
_ADAPTIVE_PREFIXES = ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-opus-4-8", "claude-opus-4-7")
# Modelos donde activamos el reenvío automático si los clasificadores rechazan la petición.
_FALLBACK_MODELS = ("claude-opus-5", "claude-opus-5-5", "claude-fable-5-1")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@register("llm", "anthropic")
class AnthropicLLM:
    name = "anthropic"
    billable = True

    def __init__(
        self,
        model: str = "claude-opus-5",
        effort: str = "high",
        max_output_tokens: int = 16000,
        server_side_fallback: bool = True,
        timeout_seconds: float = 600.0,
        **_: Any,
    ) -> None:
        self.model = model
        self.effort = effort
        self.max_output_tokens = max_output_tokens
        self.server_side_fallback = server_side_fallback and model in _FALLBACK_MODELS
        self.timeout_seconds = timeout_seconds
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(timeout=self.timeout_seconds, max_retries=3)
        return self._client

    def estimate_input_tokens(self, text: str) -> int:
        # Aproximación para español; suficiente para el control de presupuesto previo.
        return int(len(text) / 3.2) + 50

    def complete_json(
        self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int | None = None
    ) -> LLMResponse:
        import anthropic

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        if self.model.startswith(_ADAPTIVE_PREFIXES):
            params["thinking"] = {"type": "adaptive"}
            params["output_config"]["effort"] = self.effort

        try:
            if self.server_side_fallback:
                stream_ctx = self.client.beta.messages.stream(
                    **params, betas=[_FALLBACK_BETA], extra_body={"fallbacks": "default"}
                )
            else:
                stream_ctx = self.client.messages.stream(**params)
            with stream_ctx as stream:
                message = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise ConfigurationError(
                "Credenciales de Anthropic inválidas o ausentes. Define ANTHROPIC_API_KEY en .env "
                "(se obtiene en platform.claude.com; la suscripción de claude.ai no la incluye)."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise ConfigurationError("La API key no tiene permiso para este modelo", detail=str(exc)) from exc
        except anthropic.BadRequestError as exc:
            err = LLMError("Petición rechazada por la API de Anthropic", detail=str(exc))
            err.retryable = False
            raise err from exc
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            raise LLMError("Error temporal de la API de Anthropic", detail=str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Error de la API de Anthropic ({exc.status_code})", detail=str(exc)) from exc

        request_id = getattr(message, "_request_id", None)
        if message.stop_reason == "refusal":
            err = LLMError("El modelo rechazó la petición", detail=str(getattr(message, "stop_details", "")))
            err.retryable = False
            raise err
        if message.stop_reason == "max_tokens":
            raise LLMError("La respuesta se cortó por max_tokens; sube llm.max_output_tokens")

        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise LLMError("Respuesta sin bloque de texto", detail=f"request_id={request_id}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("La respuesta no es JSON válido", detail=text[:500]) from exc

        u = message.usage
        usage = LLMUsage(
            model=getattr(message, "model", self.model) or self.model,
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
        log.info("llm.done", model=usage.model, request_id=request_id,
                 input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        return LLMResponse(data=data, usage=usage, request_id=request_id)
