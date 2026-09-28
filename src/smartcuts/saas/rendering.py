"""Traduce las opciones de un proyecto (y las preferencias del usuario) a lo que necesita el motor."""

from __future__ import annotations

from pathlib import Path

from smartcuts.domain.models import Branding, OutputProfile, ReframeMode
from smartcuts.domain.ports import Storage
from smartcuts.infra.config import Settings
from smartcuts.saas.artifacts import logo_key
from smartcuts.saas.models import User
from smartcuts.saas.presets import (
    DEFAULT_STYLE,
    FORMATS,
    MAX_ORIGINAL_SHORT_SIDE,
    BrandingPrefs,
    CaptionStyle,
    build_profile,
)


def caption_style(options: dict, override: dict | None = None) -> CaptionStyle:
    raw = override or options.get("caption_style")
    return CaptionStyle.model_validate(raw) if raw else DEFAULT_STYLE


def result_frame(options: dict) -> str:
    """Encuadre del resultado (vertical, square o horizontal), también para el formato «original»."""
    fmt = options.get("format", "vertical")
    if fmt != "original":
        return fmt
    width, height = options.get("source_size") or (16, 9)
    aspect = width / max(1, height)
    return "vertical" if aspect < 0.8 else "square" if aspect < 1.25 else "horizontal"


def original_profile(settings: Settings, size: list[int] | tuple[int, int]) -> OutputProfile:
    """Perfil con el encuadre del propio vídeo (sin recortar), como mucho en 1080p."""
    width, height = int(size[0]), int(size[1])
    aspect = width / max(1, height)
    base_name = "vertical_9x16" if aspect < 0.8 else "square_1x1" if aspect < 1.25 else "horizontal_16x9"
    base = settings.load_profile(base_name)
    factor = min(1.0, MAX_ORIGINAL_SHORT_SIDE / max(1, min(width, height)))
    even = lambda v: max(2, round(v * factor / 2) * 2)  # noqa: E731
    return base.model_copy(update={"name": "original", "width": even(width), "height": even(height),
                                   "reframe": ReframeMode.CENTER})


def project_profile(settings: Settings, options: dict, style_override: dict | None = None) -> OutputProfile:
    fmt = options.get("format", "vertical")
    if fmt == "original" and options.get("source_size"):
        base = original_profile(settings, options["source_size"])
    else:
        base = settings.load_profile(FORMATS.get(fmt, FORMATS["vertical"])["profile"] or "horizontal_16x9")
    return build_profile(base, duration=options.get("duration", "auto"), style=caption_style(options, style_override))


def project_branding(storage: Storage, user: User, options: dict, work_dir: Path) -> Branding | None:
    """Marca actual del usuario si el proyecto la lleva activada (el logo se descarga a `work_dir`)."""
    if not options.get("branding"):
        return None
    prefs = BrandingPrefs.model_validate((user.preferences or {}).get("branding", {}))
    if not prefs.enabled:
        return None
    logo: Path | None = None
    if prefs.has_logo and (data := storage.read_bytes(logo_key(user.id))):
        work_dir.mkdir(parents=True, exist_ok=True)
        logo = work_dir / "logo.png"
        logo.write_bytes(data)
    branding = Branding(handle=prefs.handle, logo_path=logo, position=prefs.position)
    return branding if branding.active else None
