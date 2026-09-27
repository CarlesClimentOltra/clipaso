"""Opciones que el usuario elige para sus clips: formato, duración y estilo de subtítulos.

Es la única fuente de verdad: la API las publica (`GET /options`) y la web las pinta tal cual.
Se traducen a los perfiles del motor (`configs/output_profiles`) con `build_profile`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from smartcuts.domain.models import OutputProfile

HexColor = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$")]

FORMATS: dict[str, dict] = {
    "vertical": {"label": "Vertical 9:16", "hint": "TikTok, Reels y Shorts", "profile": "vertical_9x16"},
    "square": {"label": "Cuadrado 1:1", "hint": "Feed de Instagram y LinkedIn", "profile": "square_1x1"},
    "horizontal": {"label": "Horizontal 16:9", "hint": "YouTube y web", "profile": "horizontal_16x9"},
}
FormatT = Literal["vertical", "square", "horizontal"]

DURATIONS: dict[str, dict] = {
    "auto": {"label": "Automática", "hint": "La que mejor encaje con cada momento", "range": None},
    "short": {"label": "Cortos", "hint": "15-30 s", "range": (15, 30, 22)},
    "medium": {"label": "Medios", "hint": "30-60 s", "range": (30, 60, 42)},
    "long": {"label": "Largos", "hint": "60-90 s", "range": (60, 90, 75)},
}
DurationT = Literal["auto", "short", "medium", "long"]

# Familia de cada fuente incluida en assets/fonts (la que va en el ASS).
FONTS: dict[str, str] = {
    "Archivo Black": "Archivo Black",
    "Anton": "Anton",
    "Bebas Neue": "Bebas Neue",
    "Poppins": "Poppins ExtraBold",
    "Luckiest Guy": "Luckiest Guy",
}
FontT = Literal["Archivo Black", "Anton", "Bebas Neue", "Poppins", "Luckiest Guy"]
SIZE_FACTOR = {"s": 0.8, "m": 1.0, "l": 1.25}


class CaptionStyle(BaseModel):
    """Estilo de subtítulos tal como lo elige el usuario."""

    enabled: bool = True
    font: FontT = "Archivo Black"
    text_color: HexColor = "FFFFFF"
    highlight_color: HexColor = "00E5FF"
    size: Literal["s", "m", "l"] = "m"
    position: Literal["bottom", "middle", "top"] = "bottom"
    uppercase: bool = True
    box: bool = False
    box_color: HexColor = "000000"


class CaptionPreset(BaseModel):
    id: str
    name: str
    style: CaptionStyle


PRESETS: list[CaptionPreset] = [
    CaptionPreset(id="clasico", name="Clásico", style=CaptionStyle(
        font="Archivo Black", text_color="FFFFFF", highlight_color="00E5FF")),
    CaptionPreset(id="amarillo", name="Amarillo", style=CaptionStyle(
        font="Anton", text_color="FFFFFF", highlight_color="FFE600", size="l")),
    CaptionPreset(id="caja", name="Caja", style=CaptionStyle(
        font="Poppins", text_color="FFFFFF", highlight_color="FFE600", uppercase=False, box=True)),
    CaptionPreset(id="titular", name="Titular", style=CaptionStyle(
        font="Bebas Neue", text_color="FFFFFF", highlight_color="FF3B30", size="l")),
    CaptionPreset(id="comic", name="Cómic", style=CaptionStyle(
        font="Luckiest Guy", text_color="FFFFFF", highlight_color="7CFC00", position="middle")),
    CaptionPreset(id="minimal", name="Minimal", style=CaptionStyle(
        font="Poppins", text_color="FFFFFF", highlight_color="FFFFFF", size="s", uppercase=False)),
]
DEFAULT_STYLE = PRESETS[0].style


class BrandingPrefs(BaseModel):
    """Marca personal del usuario (el logo se sube aparte; aquí solo si hay uno)."""

    enabled: bool = True
    handle: str = Field("", max_length=30)
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "top-right"
    has_logo: bool = False


def build_profile(base: OutputProfile, *, duration: str = "auto", style: CaptionStyle | None = None) -> OutputProfile:
    """Perfil del motor con la duración y el estilo elegidos."""
    update: dict = {}
    rng = DURATIONS.get(duration, DURATIONS["auto"])["range"]
    if rng:
        update |= {"min_duration": rng[0], "max_duration": rng[1], "target_duration": rng[2]}
    if style is not None and base.subtitles.enabled:
        base_size = base.subtitles.font_size_ratio
        subtitles = base.subtitles.model_copy(update={
            "enabled": style.enabled,
            "font": FONTS[style.font],
            "primary_color": style.text_color.upper(),
            "highlight_color": style.highlight_color.upper(),
            "font_size_ratio": round(base_size * SIZE_FACTOR[style.size], 4),
            "position": style.position,
            # En el centro no hay margen; arriba se deja sitio para la cabecera de la app.
            "margin_v_ratio": 0.12 if style.position == "top" else base.subtitles.margin_v_ratio,
            "uppercase": style.uppercase,
            "box": style.box,
            "box_color": style.box_color.upper(),
        })
        update["subtitles"] = subtitles
    return base.model_copy(update=update)
