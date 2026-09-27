"""Traduce las opciones de un proyecto (y las preferencias del usuario) a lo que necesita el motor."""

from __future__ import annotations

from pathlib import Path

from smartcuts.domain.models import Branding, OutputProfile
from smartcuts.domain.ports import Storage
from smartcuts.infra.config import Settings
from smartcuts.saas.artifacts import logo_key
from smartcuts.saas.models import User
from smartcuts.saas.presets import DEFAULT_STYLE, FORMATS, BrandingPrefs, CaptionStyle, build_profile


def caption_style(options: dict, override: dict | None = None) -> CaptionStyle:
    raw = override or options.get("caption_style")
    return CaptionStyle.model_validate(raw) if raw else DEFAULT_STYLE


def project_profile(settings: Settings, options: dict, style_override: dict | None = None) -> OutputProfile:
    fmt = options.get("format", "vertical")
    base = settings.load_profile(FORMATS.get(fmt, FORMATS["vertical"])["profile"])
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
