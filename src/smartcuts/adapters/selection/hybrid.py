"""Selección híbrida: señales baratas + criterio editorial de un LLM.

1. Cada frase de la transcripción se anota con una "señal" 0-9 que resume
   energía de audio y ritmo del habla.
2. El LLM lee la transcripción completa y propone clips como rangos de
   frases (así los cortes siempre caen en fronteras naturales).
3. Se validan duraciones, se combina la nota del LLM con las señales y se
   eligen los mejores sin solapamiento.
"""

from __future__ import annotations

from typing import Any

from smartcuts.application.cost import CostTracker
from smartcuts.domain.clips import clip_bounds, pick_non_overlapping, signal_score
from smartcuts.domain.errors import SelectionError
from smartcuts.domain.models import ClipCandidate, Selection, Sentence
from smartcuts.domain.ports import LLMClient, SelectionRequest
from smartcuts.infra.logging import get_logger
from smartcuts.infra.registry import register

log = get_logger(__name__)

SYSTEM_PROMPT = """\
Eres un editor de vídeo experto en contenido corto para TikTok, Instagram Reels y YouTube Shorts.
Tu trabajo es encontrar, dentro de la transcripción de un vídeo largo, los fragmentos que mejor \
funcionarían como clips independientes.

Un buen clip:
- Engancha en los primeros 3 segundos: arranca con una afirmación fuerte, una pregunta, un dato \
sorprendente o el inicio de una historia. Nunca empieza a mitad de idea ni depende de lo dicho antes.
- Se entiende solo, sin haber visto el resto del vídeo.
- Tiene un cierre: remate, conclusión, respuesta o punchline. No termina a media frase.
- Aporta valor claro: humor, emoción, polémica, un consejo concreto, una revelación o una opinión \
contundente.

Evita saludos, despedidas, patrocinios, autopromoción, relleno y tramos que solo tienen sentido \
con apoyo visual que el espectador no verá explicado.

Cada línea de la transcripción tiene el formato `[n] mm:ss-mm:ss (señal s) texto`, donde `n` es el \
índice de la frase y `s` (0-9) es un indicador automático de intensidad (volumen y ritmo del \
habla). Úsalo como pista, no como verdad: el contenido manda.

Los clips se definen con la primera y la última frase (índices inclusivos). Respeta la duración \
indicada y no hagas que dos clips se solapen. Escribe títulos y ganchos en el idioma del vídeo.\
"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "first_sentence": {"type": "integer"},
                    "last_sentence": {"type": "integer"},
                    "score": {"type": "integer", "description": "0-100: potencial viral del clip"},
                    "title": {"type": "string", "description": "Título corto y llamativo (máx. 60 caracteres)"},
                    "hook": {"type": "string", "description": "Qué engancha al espectador al principio"},
                    "reason": {"type": "string", "description": "Por qué funciona como clip, en una frase"},
                },
                "required": ["first_sentence", "last_sentence", "score", "title", "hook", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


@register("selectors", "hybrid")
class HybridSelector:
    name = "hybrid"

    def __init__(
        self,
        llm: LLMClient,
        cost: CostTracker,
        weights: dict[str, float] | None = None,
        llm_weight: float = 0.75,
        min_gap_seconds: float = 2.0,
        **_: Any,
    ) -> None:
        self.llm = llm
        self.cost = cost
        self.weights = weights or {"audio_energy": 0.6, "speech_rate": 0.4}
        self.llm_weight = llm_weight
        self.min_gap = min_gap_seconds

    # ------------------------------------------------------------------ prompt

    def _render_transcript(self, request: SelectionRequest) -> str:
        lines = []
        for s in request.transcript.sentences:
            sig, _ = signal_score(request.signals, self.weights, s.start, s.end)
            lines.append(f"[{s.index}] {_ts(s.start)}-{_ts(s.end)} (señal {min(9, int(sig * 10))}) {s.text}")
        return "\n".join(lines)

    def _user_prompt(self, request: SelectionRequest) -> str:
        p = request.profile
        chapters = "\n".join(f"- {_ts(c.start)} {c.title}" for c in request.source.chapters)
        want = max(request.max_clips * 2, request.max_clips + 3)
        return (
            f"Título del vídeo: {request.source.title or '(desconocido)'}\n"
            f"Duración total: {_ts(request.source.duration)}\n"
            + (f"Capítulos:\n{chapters}\n" if chapters else "")
            + f"\n<transcripcion>\n{self._render_transcript(request)}\n</transcripcion>\n\n"
            f"Propón hasta {want} clips ordenados de mejor a peor. Cada clip debe durar entre "
            f"{p.min_duration:.0f} y {p.max_duration:.0f} segundos (ideal: ~{p.target_duration:.0f} s), "
            "calculado con las marcas de tiempo de la primera y la última frase. "
            "Sé exigente con la puntuación: reserva 80+ para clips realmente excepcionales."
        )

    # ------------------------------------------------------------------ validación

    @staticmethod
    def _fit_duration(sentences: list[Sentence], first: int, last: int, lo: float, hi: float) -> tuple[int, int] | None:
        """Ajusta el rango para cumplir la duración: recorta por el final o extiende si se queda corto."""
        n = len(sentences)
        if not (0 <= first <= last < n):
            return None
        while last > first and sentences[last].end - sentences[first].start > hi:
            last -= 1
        while last + 1 < n and sentences[last].end - sentences[first].start < lo:
            if sentences[last + 1].end - sentences[first].start > hi:
                break
            last += 1
        span = sentences[last].end - sentences[first].start
        return (first, last) if lo * 0.85 <= span <= hi else None

    # ------------------------------------------------------------------ select

    def select(self, request: SelectionRequest) -> Selection:
        sentences = request.transcript.sentences
        if not sentences:
            raise SelectionError("La transcripción está vacía: no hay nada que seleccionar")

        user = self._user_prompt(request)
        est_in = self.llm.estimate_input_tokens(SYSTEM_PROMPT + user)
        estimate = self.cost.llm_cost(self.llm.model, est_in, 6000) if getattr(self.llm, "billable", True) else 0.0
        self.cost.check("selección LLM", estimate)
        log.info("selection.llm_request", model=self.llm.model, est_input_tokens=est_in,
                 est_usd=round(estimate, 4), sentences=len(sentences))

        response = self.llm.complete_json(system=SYSTEM_PROMPT, user=user, schema=SCHEMA)
        self.cost.record_llm(response.usage)

        p = request.profile
        candidates: list[ClipCandidate] = []
        rejected = 0
        for raw in response.data.get("clips", []):
            fitted = self._fit_duration(
                sentences, int(raw["first_sentence"]), int(raw["last_sentence"]), p.min_duration, p.max_duration
            )
            if fitted is None:
                rejected += 1
                continue
            first, last = fitted
            start, end = clip_bounds(sentences, first, last, request.source.duration)
            sig, parts = signal_score(request.signals, self.weights, start, end)
            llm_score = max(0, min(100, int(raw["score"]))) / 100
            has_signals = bool(parts)
            w = self.llm_weight if has_signals else 1.0
            score = w * llm_score + (1 - w) * sig
            candidates.append(
                ClipCandidate(
                    start=start,
                    end=end,
                    first_sentence=first,
                    last_sentence=last,
                    score=round(score, 4),
                    title=raw.get("title", "")[:80],
                    hook=raw.get("hook", ""),
                    reason=raw.get("reason", ""),
                    scores={"llm": llm_score, **parts},
                )
            )

        chosen = pick_non_overlapping(candidates, request.max_clips, min_gap=self.min_gap)
        notes = [
            f"modelo: {response.usage.model}",
            f"propuestos por el LLM: {len(response.data.get('clips', []))}, descartados por duración: {rejected}",
        ]
        if response.request_id:
            notes.append(f"request_id: {response.request_id}")
        if not chosen:
            raise SelectionError("El LLM no devolvió ningún clip válido", detail="; ".join(notes))
        return Selection(strategy=self.name, clips=sorted(chosen, key=lambda c: c.start), notes=notes)
