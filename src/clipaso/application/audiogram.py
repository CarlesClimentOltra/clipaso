"""Audiograma: un audio (podcast, nota de voz) convertido en vídeo con onda animada.

El fondo es estático y se compone una sola vez con Pillow: la imagen del usuario (portada del podcast o su
logo) nítida en el centro sobre la misma imagen desenfocada, o un degradado de color si no hay imagen, y un
título opcional arriba. ffmpeg solo tiene que repetir ese fondo y dibujar encima la onda del audio, así que
el render es barato. Después el vídeo pasa por el flujo normal (subtítulos, marca, portada).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from clipaso.infra import ffmpeg
from clipaso.infra.logging import get_logger

log = get_logger(__name__)

FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
TITLE_FONT = "Poppins-ExtraBold.ttf"
FPS = 25


@dataclass
class AudiogramStyle:
    width: int
    height: int
    color: str = "0F172A"  # fondo sin imagen (hex sin #)
    accent: str = "B6E34A"  # color de la onda
    title: str = ""
    image: Path | None = None


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _gradient(size: tuple[int, int], color: str) -> Image.Image:
    """Degradado vertical del color elegido a una versión más oscura."""
    w, h = size
    top = _rgb(color)
    bottom = tuple(int(c * 0.35) for c in top)
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        column.putpixel((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    return column.resize((w, h))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines[:3]


def layout(style: AudiogramStyle) -> dict[str, int]:
    """Dónde va cada cosa (la onda y la imagen dependen del formato)."""
    w, h = style.width, style.height
    portrait = h > w * 1.2
    # En vertical los subtítulos van hacia el 70 % de la altura: la onda termina antes (~62 %).
    art = int(min(w * (0.56 if portrait else 0.42), h * (0.36 if portrait else 0.5)))
    art_y = int(h * (0.17 if portrait else 0.12))
    wave_h = int(h * (0.1 if portrait else 0.14))
    wave_y = art_y + art + int(h * 0.03)
    return {"art": art, "art_y": art_y, "wave_h": wave_h, "wave_y": wave_y, "title_y": int(h * 0.06)}


def background(style: AudiogramStyle) -> Image.Image:
    w, h = style.width, style.height
    pos = layout(style)
    art_img = None
    if style.image and style.image.is_file():
        try:
            art_img = ImageOps.exif_transpose(Image.open(style.image)).convert("RGB")
        except OSError as exc:  # imagen dañada: se usa el degradado
            log.warning("audiogram.bad_image", error=str(exc))
    if art_img is not None:
        bg = ImageOps.fit(art_img, (w, h)).filter(ImageFilter.GaussianBlur(radius=max(w, h) / 40))
        bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.45)
        art = ImageOps.fit(art_img, (pos["art"], pos["art"]))
        mask = Image.new("L", art.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *art.size), radius=int(pos["art"] * 0.06), fill=255)
        bg.paste(art, ((w - pos["art"]) // 2, pos["art_y"]), mask)
    else:
        bg = _gradient((w, h), style.color)
    if style.title.strip():
        draw = ImageDraw.Draw(bg)
        size = int(min(w, h) * 0.058)
        try:
            font = ImageFont.truetype(str(FONTS_DIR / TITLE_FONT), size)
        except OSError:
            font = ImageFont.load_default()
        y = pos["title_y"]
        for line in _wrap(draw, style.title.strip(), font, int(w * 0.86)):
            lw = draw.textlength(line, font=font)
            draw.text(((w - lw) / 2, y), line, font=font, fill=(255, 255, 255),
                      stroke_width=max(2, size // 14), stroke_fill=(0, 0, 0))
            y += int(size * 1.2)
    return bg


def render(audio: Path, dest: Path, work: Path, style: AudiogramStyle) -> Path:
    """Vídeo del audiograma: fondo fijo + onda animada + el audio original."""
    work.mkdir(parents=True, exist_ok=True)
    bg_path = work / "fondo.png"
    background(style).save(bg_path)
    pos = layout(style)
    w, h = style.width, style.height
    wave_w = int(w * 0.84) // 2 * 2
    graph = (
        f"[1:a]aformat=channel_layouts=mono,showwaves=s={wave_w}x{pos['wave_h']}:mode=cline:rate={FPS}:"
        f"scale=sqrt:draw=full:colors=0x{style.accent.strip('#')}[wave];"
        f"[0:v]scale={w}:{h},setsar=1,format=yuv420p[bg];"
        f"[bg][wave]overlay=(W-w)/2:{pos['wave_y']}:shortest=1,format=yuv420p[v]"
    )
    codec = (["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
             if ffmpeg.nvenc_available() else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                                                "-tune", "stillimage"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([
        "-loop", "1", "-framerate", str(FPS), "-i", str(bg_path.resolve()), "-i", str(audio.resolve()),
        "-filter_complex", graph, "-map", "[v]", "-map", "1:a:0", *codec, "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(dest.resolve()),
    ], what="render del audiograma")
    log.info("audiogram.rendered", size=f"{w}x{h}", image=bool(style.image), title=bool(style.title))
    return dest
