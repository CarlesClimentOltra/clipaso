"""Traducción de subtítulos: frase a frase con un LLM, conservando los tiempos.

El reconocimiento de voz da el tiempo de cada palabra original; al traducir, el orden y el número de
palabras cambian, así que cada frase traducida se reparte sobre el tramo que ocupaba la original
(según dónde caían sus palabras). El resultado es un `Transcript` normal: el resto del motor
(subtítulos incrustados, SRT, editor) no distingue si está traducido.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from smartcuts.application.cost import CostTracker
from smartcuts.domain.errors import LLMError
from smartcuts.domain.models import Sentence, Transcript, Word
from smartcuts.domain.ports import LLMClient
from smartcuts.infra.logging import get_logger

log = get_logger(__name__)

LANGUAGE_NAMES = {
    "es": "Spanish (Spain)", "en": "English", "pt": "Portuguese", "fr": "French", "it": "Italian",
    "de": "German", "ca": "Catalan",
}
BATCH_CHARS = 6000  # texto original por petición (varias peticiones en vídeos largos)

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"i": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["i", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _system(target: str) -> str:
    return (
        f"You translate video subtitles into {LANGUAGE_NAMES.get(target, target)}. "
        "Each item is one spoken sentence. Translate every item faithfully and naturally, as a native "
        "subtitler would: keep the meaning and tone, keep names, and keep it about as short as the original "
        "so it fits on screen at the same pace. Return exactly one item per input item with the same `i`; "
        "never merge, split, skip or add items. If an item is already in the target language, return it as is."
    )


def _spread(sentence: Sentence, text: str) -> list[Word]:
    """Palabras de `text` repartidas sobre el tiempo de la frase original, siguiendo su ritmo."""
    tokens = text.split()
    source = sentence.words or [Word(text=sentence.text, start=sentence.start, end=sentence.end)]
    if not tokens:
        return []
    weights = [len(t) + 1 for t in tokens]
    total = sum(weights)

    def at(fraction: float) -> float:
        # Punto del tiempo original: se recorre palabra a palabra (las pausas de la frase se respetan).
        pos = min(fraction, 0.9999) * len(source)
        w = source[int(pos)]
        return w.start + (w.end - w.start) * (pos - int(pos))

    out, acc = [], 0
    for token, weight in zip(tokens, weights, strict=True):
        start, acc = at(acc / total), acc + weight
        end = at(acc / total) if acc < total else source[-1].end
        out.append(Word(text=f" {token}", start=round(start, 3), end=round(max(end, start + 0.05), 3)))
    return out


class Translator:
    def __init__(self, llm: LLMClient, cost: CostTracker) -> None:
        self.llm = llm
        self.cost = cost

    def translate(
        self, transcript: Transcript, target: str, on_progress: Callable[[float], None] | None = None,
    ) -> Transcript:
        sentences = transcript.sentences
        batches: list[list[Sentence]] = [[]]
        size = 0
        for s in sentences:
            if batches[-1] and size + len(s.text) > BATCH_CHARS:
                batches.append([])
                size = 0
            batches[-1].append(s)
            size += len(s.text)

        translated: dict[int, str] = {}
        for bi, batch in enumerate(batches):
            if not batch:
                continue
            user = "\n".join(json.dumps({"i": s.index, "text": s.text.strip()}, ensure_ascii=False) for s in batch)
            self.cost.check("translation", self.cost.llm_cost(self.llm.model, self.llm.estimate_input_tokens(user),
                                                              len(user) // 2))
            response = self.llm.complete_json(system=_system(target), user=user, schema=SCHEMA,
                                              max_tokens=min(32000, 1000 + len(user)))
            self.cost.record_llm(response.usage)
            for item in response.data.get("items", []):
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    translated[int(item.get("i", -1))] = item["text"].strip()
            if on_progress:
                on_progress((bi + 1) / len(batches))

        missing = [s.index for s in sentences if s.index not in translated]
        if len(missing) > len(sentences) * 0.2:
            raise LLMError("La traducción vino incompleta", detail=f"faltan {len(missing)} de {len(sentences)} frases")
        out = []
        for s in sentences:
            text = translated.get(s.index, s.text.strip())
            out.append(s.model_copy(update={"text": text, "words": _spread(s, text)}))
        log.info("translation.done", target=target, sentences=len(sentences), missing=len(missing))
        return transcript.model_copy(update={"language": target, "sentences": out})
