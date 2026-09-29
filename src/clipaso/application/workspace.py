"""Directorio de trabajo por vídeo, con caché de artefactos por etapa.

Cada etapa guarda su resultado junto a una huella (hash) de los parámetros que
lo produjeron. Si se relanza el pipeline con los mismos parámetros se reutiliza
el resultado: nunca se paga dos veces la misma transcripción o llamada al LLM.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def fingerprint(params: dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.root / name

    def subdir(self, name: str) -> Path:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load(self, stage: str, model: type[M], params: dict[str, Any]) -> M | None:
        file = self.path(f"{stage}.json")
        if not file.exists():
            return None
        try:
            envelope = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if envelope.get("fingerprint") != fingerprint(params):
            return None
        return model.model_validate(envelope["data"])

    def save(self, stage: str, value: BaseModel, params: dict[str, Any]) -> None:
        envelope = {"fingerprint": fingerprint(params), "params": params, "data": value.model_dump(mode="json")}
        tmp = self.path(f"{stage}.json.tmp")
        tmp.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path(f"{stage}.json"))

    def invalidate(self, *stages: str) -> None:
        for stage in stages:
            self.path(f"{stage}.json").unlink(missing_ok=True)
