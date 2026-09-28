"""Opciones que el usuario elige para sus clips: formato, duración y estilo de subtítulos.

Es la única fuente de verdad: la API las publica (`GET /options`) y la web las pinta tal cual.
Se traducen a los perfiles del motor (`configs/output_profiles`) con `build_profile`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from smartcuts.domain.models import OutputProfile

HexColor = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$")]

FORMATS: dict[str, dict] = {
    "vertical": {"label": "Vertical 9:16", "hint": "TikTok, Reels y Shorts", "profile": "vertical_9x16"},
    "square": {"label": "Cuadrado 1:1", "hint": "Feed de Instagram y LinkedIn", "profile": "square_1x1"},
    "horizontal": {"label": "Horizontal 16:9", "hint": "YouTube y web", "profile": "horizontal_16x9"},
    # Solo subtitular: el vídeo tal cual (la base de tamaños de letra se elige según su proporción).
    "original": {"label": "Original", "hint": "El mismo formato que tu vídeo", "profile": None},
}
FormatT = Literal["vertical", "square", "horizontal", "original"]
ModeT = Literal["clips", "subtitle"]
MAX_ORIGINAL_SHORT_SIDE = 1080  # el vídeo subtitulado sale como mucho en 1080p (4K se pide aparte)

DURATIONS: dict[str, dict] = {
    "auto": {"label": "Automática", "hint": "La que mejor encaje con cada momento", "range": None},
    "short": {"label": "Cortos", "hint": "15-30 s", "range": (15, 30, 22)},
    "medium": {"label": "Medios", "hint": "30-60 s", "range": (30, 60, 42)},
    "long": {"label": "Largos", "hint": "60-90 s", "range": (60, 90, 75)},
}
DurationT = Literal["auto", "short", "medium", "long"]

# Nombre que ve el usuario → familia real de la fuente incluida en assets/fonts (la que va en el ASS).
FONTS: dict[str, str] = {
    "Archivo Black": "Archivo Black",
    "Anton": "Anton",
    "Bebas Neue": "Bebas Neue",
    "Poppins": "Poppins ExtraBold",
    "Luckiest Guy": "Luckiest Guy",
    "Montserrat": "Montserrat Black",
    "Oswald": "Oswald",
    "Bangers": "Bangers",
    "Rubik": "Rubik Black",
    "Permanent Marker": "Permanent Marker",
    "Inter": "Inter ExtraBold",
}
FontT = Literal["Archivo Black", "Anton", "Bebas Neue", "Poppins", "Luckiest Guy", "Montserrat", "Oswald",
                "Bangers", "Rubik", "Permanent Marker", "Inter"]
SIZE_SCALE = {"s": 80, "m": 100, "l": 125}  # los tres tamaños de la primera versión, en %
AnimationT = Literal["highlight", "pop", "karaoke", "appear", "none"]


class CaptionStyle(BaseModel):
    """Estilo de subtítulos tal como lo elige el usuario."""

    enabled: bool = True
    font: FontT = "Archivo Black"
    text_color: HexColor = "FFFFFF"
    highlight_color: HexColor = "00E5FF"
    scale: int = Field(100, ge=50, le=200, description="Tamaño del texto, en % del tamaño base del formato.")
    position: Literal["bottom", "middle", "top"] = "bottom"
    y: int | None = Field(None, ge=5, le=95, description="Altura exacta (% desde arriba); si falta, `position`.")
    uppercase: bool = True
    outline: int = Field(4, ge=0, le=12, description="Grosor del contorno (0 = sin contorno).")
    outline_color: HexColor = "000000"
    shadow: int = Field(2, ge=0, le=12, description="Distancia de la sombra (0 = sin sombra).")
    box: bool = False
    box_color: HexColor = "000000"
    box_opacity: int = Field(100, ge=0, le=100)
    animation: AnimationT = Field("highlight", description="Cómo se marca la palabra que se está diciendo.")
    max_words: int = Field(3, ge=1, le=8, description="Palabras como máximo en pantalla a la vez.")

    @model_validator(mode="before")
    @classmethod
    def _legacy_size(cls, data):
        # Los estilos guardados antes de los deslizadores tenían «size» (s/m/l) en vez de «scale».
        if isinstance(data, dict) and "scale" not in data and data.get("size") in SIZE_SCALE:
            data = {**data, "scale": SIZE_SCALE[data["size"]]}
        return data


class CaptionPreset(BaseModel):
    id: str
    name: str
    style: CaptionStyle


PRESETS: list[CaptionPreset] = [
    CaptionPreset(id="clasico", name="Clásico", style=CaptionStyle(
        font="Archivo Black", text_color="FFFFFF", highlight_color="00E5FF")),
    CaptionPreset(id="amarillo", name="Amarillo", style=CaptionStyle(
        font="Anton", text_color="FFFFFF", highlight_color="FFE600", scale=125, animation="pop")),
    CaptionPreset(id="caja", name="Caja", style=CaptionStyle(
        font="Poppins", text_color="FFFFFF", highlight_color="FFE600", uppercase=False, box=True,
        box_opacity=85, outline=0, shadow=0)),
    CaptionPreset(id="titular", name="Titular", style=CaptionStyle(
        font="Bebas Neue", text_color="FFFFFF", highlight_color="FF3B30", scale=125)),
    CaptionPreset(id="comic", name="Cómic", style=CaptionStyle(
        font="Luckiest Guy", text_color="FFFFFF", highlight_color="7CFC00", position="middle", outline=6,
        animation="pop")),
    CaptionPreset(id="minimal", name="Minimal", style=CaptionStyle(
        font="Inter", text_color="FFFFFF", highlight_color="FFFFFF", scale=80, uppercase=False, outline=0,
        shadow=3, animation="none", max_words=5)),
    CaptionPreset(id="karaoke", name="Karaoke", style=CaptionStyle(
        font="Montserrat", text_color="FFFFFF", highlight_color="FFD60A", animation="karaoke", max_words=4)),
    CaptionPreset(id="neon", name="Neón", style=CaptionStyle(
        font="Rubik", text_color="FFFFFF", highlight_color="FF2BD6", outline=5, outline_color="2B0A3D",
        animation="pop")),
    CaptionPreset(id="rotulador", name="Rotulador", style=CaptionStyle(
        font="Permanent Marker", text_color="FFFFFF", highlight_color="FFFFFF", uppercase=False, outline=5,
        animation="appear", max_words=4)),
]
PRESETS_BY_ID = {p.id: p for p in PRESETS}
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
    if style is not None:
        subs = base.subtitles
        update["subtitles"] = subs.model_copy(update={
            "enabled": style.enabled,
            "font": FONTS[style.font],
            "primary_color": style.text_color.upper(),
            "highlight_color": style.highlight_color.upper(),
            "font_size_ratio": round(subs.font_size_ratio * style.scale / 100, 4),
            "position": style.position,
            # En el centro no hay margen; arriba se deja sitio para la cabecera de la app.
            "margin_v_ratio": 0.12 if style.position == "top" else subs.margin_v_ratio,
            "pos_y": style.y / 100 if style.y is not None else None,
            "uppercase": style.uppercase,
            "outline_ratio": style.outline / 1000,
            "outline_color": style.outline_color.upper(),
            "shadow_ratio": style.shadow / 1000,
            "box": style.box,
            "box_color": style.box_color.upper(),
            "box_opacity": style.box_opacity,
            "animation": style.animation,
            "max_words": style.max_words,
            "max_chunk_seconds": max(1.6, 0.55 * style.max_words),
        })
    return base.model_copy(update=update)
