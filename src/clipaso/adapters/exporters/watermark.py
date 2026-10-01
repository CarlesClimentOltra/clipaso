"""Marca de agua de Clipaso: el icono de la marca y el nombre, semitransparentes, en una esquina del vídeo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from clipaso.adapters.exporters.subtitles import FONTS_DIR

WIDTH_RATIO = 0.24  # ancho de la marca respecto al lado corto del vídeo
FONT_FILE = "Poppins-ExtraBold.ttf"
LIME = (182, 227, 74, 255)
DARK = (13, 22, 8, 255)  # fondo del logo (#0d1608)


def draw_mark(size: int) -> Image.Image:
    """El logo de Clipaso (igual que web/app/icon.svg): «play» lima cortado en diagonal sobre fondo oscuro.

    Se dibuja en la cuadrícula de 32×32 del SVG escalada a `size` px.
    """
    u = size / 32
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=round(9 * u), fill=DARK)
    tri = [(11.5 * u, 8.8 * u), (23.6 * u, 16 * u), (11.5 * u, 23.2 * u)]
    d.polygon(tri, fill=LIME)
    width = round(2.4 * u)  # trazo con esquinas redondeadas, como stroke-linejoin="round"
    d.line([*tri, tri[0]], fill=LIME, width=width, joint="curve")
    for x, y in tri:
        d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=LIME)
    cut = round(2.6 * u)  # corte diagonal con extremos redondeados
    a, b = (8.5 * u, 21.5 * u), (21.5 * u, 9.5 * u)
    d.line([a, b], fill=DARK, width=cut)
    for x, y in (a, b):
        d.ellipse((x - cut / 2, y - cut / 2, x + cut / 2, y + cut / 2), fill=DARK)
    r = 1.6 * u
    d.ellipse((24.5 * u - r, 8.5 * u - r, 24.5 * u + r, 8.5 * u + r), fill=LIME)
    return img


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
    x0, y0 = pad, pad
    img.alpha_composite(draw_mark(icon), (x0, y0))
    # Nombre con una sombra suave para que se lea sobre cualquier fondo.
    tx, ty = x0 + icon + gap, y0 + (icon - font.size) // 2 - int(h * 0.08)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx, ty + scale * 2), "Clipaso", font=font, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(scale * 2)), img)
    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), "Clip", font=font, fill=(255, 255, 255, 255))
    draw.text((tx + probe.textlength("Clip", font=font), ty), "aso", font=font, fill=LIME)
    out_w = max(2, int(img.width / scale) // 2 * 2)
    out_h = max(2, int(img.height / scale) // 2 * 2)
    img = img.resize((out_w, out_h), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return out_w, out_h
