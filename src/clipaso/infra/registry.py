"""Registro de plugins por categoría y nombre.

Cada adaptador se declara con `@register("sources", "local")` y se crea por
configuración con `create("sources", "local", **deps)`. Añadir una fuente o
estrategia nueva = un módulo nuevo + importarlo en `clipaso.adapters`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from clipaso.domain.errors import ConfigurationError

T = TypeVar("T")

CATEGORIES = ("sources", "transcribers", "signals", "selectors", "llm", "reframers", "exporters", "storage")

_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {c: {} for c in CATEGORIES}


def register(category: str, name: str) -> Callable[[T], T]:
    if category not in _REGISTRY:
        raise ValueError(f"Categoría desconocida: {category}")

    def decorator(factory: T) -> T:
        if name in _REGISTRY[category]:
            raise ValueError(f"'{name}' ya está registrado en '{category}'")
        _REGISTRY[category][name] = factory  # type: ignore[assignment]
        return factory

    return decorator


def create(category: str, name: str, /, **kwargs: Any) -> Any:
    try:
        factory = _REGISTRY[category][name]
    except KeyError:
        options = ", ".join(sorted(_REGISTRY.get(category, {}))) or "(ninguno)"
        raise ConfigurationError(
            f"No hay ningún '{category}' llamado '{name}'. Disponibles: {options}"
        ) from None
    return factory(**kwargs)


def available(category: str) -> list[str]:
    return sorted(_REGISTRY[category])
