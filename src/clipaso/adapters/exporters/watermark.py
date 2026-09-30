"""Marca de agua de Clipaso: el icono de la marca y el nombre, semitransparentes, en una esquina del vídeo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from clipaso.adapters.exporters.subtitles import FONTS_DIR

WIDTH_RATIO = 0.24  # ancho de la marca respecto al lado corto del vídeo
FONT_FILE = "Poppins-ExtraBold.ttf"
LIME = (182, 227, 74, 255)
INK = (20, 32, 8, 255)


def corner(user_position: str) -> str:
    """Esquina de la marca de agua: abajo, en el lado contrario a la marca del usuario (si está abajo)."""
    if user_position == "bottom-right":
        return "bottom-left"
    return "bottom-right"


def render(dest: Path, width: int) -> tuple[int, int]:
    """PNG con fondo transparente de `width` px de ancho (aprox.). Devuelve (ancho, alto) pares."""
    scale = 4  # se dibuja grande y se reduce: bordes suaves
    h = int(width * 0.22) * scale
    icon = h
    try:
        font = ImageFont.truetype(str(FONTS_DIR / FONT_FILE), int(h * 0.72))
    except OSError:
        font = ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    text_w = int(probe.textlength("Clipaso", font=font))
    gap = int(h * 0.28)
    pad = int(h * 0.25)
    img = Image.new("RGBA", (pad * 2 + icon + gap + text_w, h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Icono: cuadrado lima redondeado con un «play».
    x0, y0 = pad, pad
    draw.rounded_rectangle((x0, y0, x0 + icon, y0 + icon), radius=int(icon * 0.26), fill=LIME)
    draw.polygon([(x0 + icon * 0.38, y0 + icon * 0.28), (x0 + icon * 0.38, y0 + icon * 0.72),
                  (x0 + icon * 0.74, y0 + icon * 0.5)], fill=INK)
    # Nombre con una sombra suave para que se lea sobre cualquier fondo.
    tx, ty = x0 + icon + gap, y0 + (icon - font.size) // 2 - int(h * 0.08)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx, ty + scale * 2), "Clipaso", font=font, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(scale * 2)), img)
    ImageDraw.Draw(img).text((tx, ty), "Clipaso", font=font, fill=(255, 255, 255, 255))
    out_w = max(2, int(img.width / scale) // 2 * 2)
    out_h = max(2, int(img.height / scale) // 2 * 2)
    img = img.resize((out_w, out_h), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return out_w, out_h
