"""Portadas de los clips: un fotograma real del vídeo + un texto corto con gancho.

- El worker elige el fotograma (se descartan los borrosos, oscuros o sin cara y una IA con visión
  escoge el más atractivo de los mejores) y escribe el texto (`auto_cover`).
- La composición (`compose`) usa la fuente y los colores del estilo de subtítulos del clip y el logo
  de la marca, en dos tamaños: 9:16 (TikTok, Reels, Shorts) y 16:9 (miniatura de YouTube).
- Los fotogramas base se guardan ya recortados: cambiar el texto o la plantilla desde el editor solo
  recompone la imagen (no hace falta volver a leer el vídeo).
"""

from __future__ import annotations

import io
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from clipaso.adapters.exporters.subtitles import FONTS_DIR
from clipaso.domain.ports import LLMClient
from clipaso.infra import ffmpeg
from clipaso.infra.logging import get_logger
from clipaso.saas.presets import FONT_FILES, CaptionStyle

log = get_logger(__name__)

SIZES = {"vertical": (1080, 1920), "horizontal": (1280, 720)}
TEMPLATES = ("impacto", "caja", "titular", "limpia")
DEFAULT_TEMPLATE = "impacto"
CANDIDATES = 16  # fotogramas que se analizan por clip
SHORTLIST = 6  # los que se enseñan a la IA
MAX_TEXT_CHARS = 42
LANGUAGE_NAMES = {"es": "Spanish", "en": "English", "pt": "Portuguese", "fr": "French", "it": "Italian",
                  "de": "German", "ca": "Catalan"}


@dataclass
class Frame:
    time: float
    image: np.ndarray  # BGR
    face_x: float | None  # centro horizontal de la cara principal (0..1)
    score: float


@dataclass
class CoverChoice:
    time: float
    face_x: float | None
    text: str
    highlight: int | None
    candidates: list[dict] = field(default_factory=list)  # [{"time", "face_x"}] para el editor
    base_vertical: bytes = b""
    base_horizontal: bytes = b""


# --------------------------------------------------------------------------- fotogramas


def grab_frame(src: str | Path, t: float, max_width: int = 1920) -> np.ndarray | None:
    """Un fotograma (BGR) del vídeo en el segundo `t`. `src` puede ser una ruta o una URL firmada."""
    import cv2

    cmd = [ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(src),
           "-frames:v", "1", "-vf", f"scale='min(iw,{max_width})':-2", "-f", "image2pipe", "-vcodec", "png", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("cover.grab_failed", t=round(t, 2), error=str(exc)[:200])
        return None
    img = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR) if out else None
    return img


def face_detector(model_dir: Path):
    """Detector de caras (YuNet). Sin él las portadas se eligen solo por nitidez y luz."""
    try:
        from clipaso.adapters.reframing.face_track import YuNetFaceDetector

        return YuNetFaceDetector(model_dir, analysis_width=480, min_score=0.6)
    except Exception as exc:  # sin red para descargar el modelo, OpenCV sin DNN…
        log.warning("cover.no_face_detector", error=str(exc)[:200])
        return None


def score_frame(img: np.ndarray, detector) -> tuple[float, float | None]:
    """Puntuación 0..1 (cara grande y centrada, nítido y bien iluminado) y centro de la cara."""
    import cv2

    small = cv2.resize(img, (480, int(img.shape[0] * 480 / img.shape[1])))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharp = min(1.0, float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 250)
    light = 1 - min(1.0, abs(float(gray.mean()) / 255 - 0.5) * 2)
    face_x, face_score = None, 0.0
    if detector is not None:
        faces = detector.faces(small)
        if faces:
            cx, cy, fw, _fh, conf = faces[0]
            face_x = cx
            face_score = min(1.0, fw * 4) * conf * (1 - abs(cy - 0.42))  # caras grandes, arriba del centro
    return 0.55 * face_score + 0.3 * sharp + 0.15 * light, face_x


SINGLE_PASS_MAX_SECONDS = 240  # hasta aquí compensa decodificar el tramo una vez que buscar 16 veces


def _frames_single_pass(src: Path, start: float, end: float, count: int, width: int = 1280):
    """Los `count` fotogramas del tramo en una sola llamada a ffmpeg (clips cortos)."""
    src_w, src_h, _, _ = ffmpeg.video_info(src)
    width = min(width, src_w) // 2 * 2
    height = max(2, round(src_h * width / src_w / 2) * 2)
    duration = max(0.1, end - start)
    rate = count / duration
    cmd = [ffmpeg.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
           "-i", str(src), "-vf", f"fps={rate:.6f},scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=300, check=True).stdout
    size = width * height * 3
    for i in range(min(count, len(raw) // size)):
        img = np.frombuffer(raw, np.uint8, count=size, offset=i * size).reshape(height, width, 3).copy()
        yield round(start + (i + 0.5) / rate, 2), img


def sample_frames(src: str | Path, start: float, end: float, detector, count: int = CANDIDATES) -> list[Frame]:
    pairs: list[tuple[float, np.ndarray]] = []
    local = isinstance(src, Path) or not str(src).startswith("http")
    if local and end - start <= SINGLE_PASS_MAX_SECONDS:
        try:
            pairs = list(_frames_single_pass(Path(src), start, end, count))
        except Exception as exc:
            log.warning("cover.single_pass_failed", error=str(exc)[:200])
    if not pairs:  # vídeos largos (modo subtitular) o URL: saltos directos a cada momento
        margin = min(0.5, (end - start) / 10)
        for t in np.linspace(start + margin, max(start + margin, end - margin), num=max(1, count)):
            if (img := grab_frame(src, float(t), max_width=1280)) is not None:
                pairs.append((round(float(t), 2), img))
    frames = []
    for t, img in pairs:
        score, face_x = score_frame(img, detector)
        frames.append(Frame(time=t, image=img, face_x=face_x, score=round(score, 4)))
    return frames


def shortlist(frames: list[Frame], k: int = SHORTLIST) -> list[Frame]:
    """Los mejores, sin dos casi iguales seguidos (separados en el tiempo)."""
    if not frames:
        return []
    span = max(f.time for f in frames) - min(f.time for f in frames)
    gap = span / (k * 2.5) if span else 0
    chosen: list[Frame] = []
    for f in sorted(frames, key=lambda f: f.score, reverse=True):
        if all(abs(f.time - c.time) >= gap for c in chosen):
            chosen.append(f)
        if len(chosen) == k:
            break
    return chosen


# --------------------------------------------------------------------------- encuadre


def _crop(img: np.ndarray, size: tuple[int, int], face_x: float | None = None) -> np.ndarray:
    """Recorta a la proporción de `size` (alrededor de la cara si la hay) y escala."""
    import cv2

    width, height = size
    target = width / height
    h, w = img.shape[:2]
    if w / h > target:
        crop_w = int(h * target)
        center = (face_x if face_x is not None else 0.5) * w
        x0 = int(min(max(center - crop_w / 2, 0), w - crop_w))
        img = img[:, x0:x0 + crop_w]
    elif w / h < target:
        crop_h = int(w / target)
        y0 = int(min(max(h * 0.42 - crop_h / 2, 0), h - crop_h))  # un poco por encima del centro (caras)
        img = img[y0:y0 + crop_h, :]
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def fit(img: np.ndarray, size: tuple[int, int], face_x: float | None = None) -> np.ndarray:
    """Encaja el fotograma en `size` recortando alrededor de la cara (o con fondo difuminado si hace falta)."""
    import cv2

    width, height = size
    h, w = img.shape[:2]
    if w / h >= (width / height) / 1.35:
        return _crop(img, size, face_x)
    # Vídeo mucho más estrecho que la portada (vertical → 16:9): fondo difuminado y el fotograma entero.
    bg = cv2.GaussianBlur(_crop(img, size), (0, 0), sigmaX=width / 40)
    bg = (bg * 0.55).astype(np.uint8)
    fg_w = int(w * height / h)
    fg = cv2.resize(img, (fg_w, height), interpolation=cv2.INTER_AREA)
    x0 = (width - fg_w) // 2
    bg[:, x0:x0 + fg_w] = fg
    return bg


def to_jpeg(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def from_jpeg(data: bytes) -> np.ndarray:
    import cv2

    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


# --------------------------------------------------------------------------- composición


def _hex(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _contrast(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return (0, 0, 0) if luminance > 150 else (255, 255, 255)


def _wrap(draw, words: list[str], font, max_width: int) -> list[list[int]]:
    """Reparte las palabras (por índice) en líneas que caben en `max_width`."""
    lines: list[list[int]] = []
    current: list[int] = []
    for i in range(len(words)):
        test = " ".join(words[j] for j in [*current, i])
        if current and draw.textlength(test, font=font) > max_width:
            lines.append(current)
            current = []
        current.append(i)
    if current:
        lines.append(current)
    return lines


def compose(
    base: bytes,
    size: tuple[int, int],
    *,
    text: str,
    highlight: int | None,
    template: str,
    style: CaptionStyle,
    logo: bytes | None = None,
    logo_position: str = "top-right",
) -> bytes:
    """Portada terminada (JPEG) a partir del fotograma base ya recortado a `size`."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont

    width, height = size
    image = Image.open(io.BytesIO(base)).convert("RGB").resize((width, height))
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Color(image).enhance(1.12)
    vertical = height > width
    words = (text.upper() if style.uppercase else text).split() if template != "limpia" else []

    if template == "titular":  # degradado oscuro abajo para que el texto se lea sobre cualquier fondo
        shade = Image.new("L", (1, 256))
        for y in range(256):
            shade.putpixel((0, y), int(230 * (y / 255) ** 1.6))
        mask = shade.resize((width, int(height * 0.55)))
        overlay = Image.new("RGB", mask.size, (0, 0, 0))
        image.paste(overlay, (0, height - mask.size[1]), mask)

    if words:
        draw = ImageDraw.Draw(image)
        font_path = FONTS_DIR / FONT_FILES.get(style.font, "ArchivoBlack-Regular.ttf")
        max_width = int(width * (0.86 if vertical else 0.84))
        size_px = int(height * (0.085 if vertical else 0.15))
        max_lines = 4 if vertical else 3
        while True:
            font = ImageFont.truetype(str(font_path), size_px)
            lines = _wrap(draw, words, font, max_width)
            fits = all(draw.textlength(words[i], font=font) <= max_width for i in range(len(words)))
            if (len(lines) <= max_lines and fits) or size_px <= 24:
                break
            size_px = int(size_px * 0.92)

        line_h = int(size_px * 1.12)
        block_h = line_h * len(lines)
        if template == "caja":
            top = int(height * (0.1 if vertical else 0.08))
        elif template == "titular":
            top = int(height * (0.86 if vertical else 0.9)) - block_h
        else:  # impacto: en el tercio inferior, donde no tapa la cara
            top = int(height * (0.7 if vertical else 0.62)) - block_h // 2
        text_rgb, hl_rgb = _hex(style.text_color), _hex(style.highlight_color)
        stroke = max(3, int(size_px * 0.075))
        outline = _hex(style.outline_color)

        box_rgb = _hex(style.box_color) if style.box else hl_rgb
        if template == "caja":
            # Primero todas las cajas (ajustadas a la altura real de las letras) y luego el texto encima.
            pad_x, pad_y = int(size_px * 0.25), int(size_px * 0.12)
            for li, line in enumerate(lines):
                line_text = " ".join(words[i] for i in line)
                x = (width - draw.textlength(line_text, font=font)) / 2
                left, top_px, right, bottom = draw.textbbox((x, top + li * line_h), line_text, font=font)
                draw.rounded_rectangle((left - pad_x, top_px - pad_y, right + pad_x, bottom + pad_y),
                                       radius=int(size_px * 0.16), fill=box_rgb)

        for li, line in enumerate(lines):
            line_text = " ".join(words[i] for i in line)
            line_w = draw.textlength(line_text, font=font)
            x = (width - line_w) / 2
            y = top + li * line_h
            for i in line:
                word = words[i]
                if template == "caja":
                    base_rgb = _contrast(box_rgb)
                    # Sobre franjas del color de resalte, la palabra destacada va en blanco (o amarillo).
                    hl_on_box = hl_rgb if style.box else ((255, 255, 255) if base_rgb == (0, 0, 0) else (255, 230, 0))
                    color = hl_on_box if i == highlight else base_rgb
                    draw.text((x, y), word, font=font, fill=color)
                else:
                    color = hl_rgb if i == highlight else text_rgb
                    shadow = max(2, int(size_px * 0.05))
                    draw.text((x + shadow, y + shadow), word, font=font, fill=(0, 0, 0))
                    draw.text((x, y), word, font=font, fill=color, stroke_width=stroke, stroke_fill=outline)
                x += draw.textlength(word + " ", font=font)

    if logo:
        mark = Image.open(io.BytesIO(logo)).convert("RGBA")
        mark_w = int(min(width, height) * 0.16)
        mark = mark.resize((mark_w, max(1, int(mark.height * mark_w / mark.width))))
        margin = int(min(width, height) * 0.035)
        x = margin if logo_position.endswith("left") else width - mark.width - margin
        y = margin if logo_position.startswith("top") else height - mark.height - margin
        image.paste(mark, (x, y), mark)

    out = io.BytesIO()
    image.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue()


# --------------------------------------------------------------------------- IA

SCHEMA = {
    "type": "object",
    "properties": {
        "frame": {"type": "integer", "description": "Índice del fotograma elegido (0 = el primero)."},
        "text": {"type": "string"},
        "highlight": {"type": "integer", "description": "Palabra del texto a resaltar (0 = la primera), -1 ninguna."},
    },
    "required": ["frame", "text", "highlight"],
    "additionalProperties": False,
}


def _system(language: str, with_images: bool, avoid_text: str | None, teaser: bool = False) -> str:
    lang = LANGUAGE_NAMES.get(language, language)
    frames = (
        "You receive numbered candidate frames (in order: 0, 1, 2…). Pick the one that makes the most "
        "clickable thumbnail: a clear, well-lit face with an expressive look, eyes open, no awkward "
        "mid-word mouth, no motion blur. "
        if with_images else "Set frame to 0. "
    )
    avoid = f' Write something clearly different from the previous cover text: "{avoid_text}".' if avoid_text else ""
    if teaser:  # tráiler: la portada invita a ver el vídeo, no cuenta la conclusión
        avoid += (" This is a trailer: never reveal the conclusion, the answer or the punchline; raise the "
                  "question instead.")
    return (
        "You design thumbnails for short vertical videos (TikTok, Reels, Shorts) and YouTube. " + frames +
        f"Write the cover text in {lang}: 2 to 5 punchy words (never more than 5) that create curiosity about "
        "what is said in the clip (a hook, not a summary), no emojis, no hashtags, no quotes, no final period. "
        "Choose the "
        f"single most important word to highlight in color (its index in the text).{avoid}"
    )


def ask_ai(
    llm: LLMClient, frames: list[Frame], *, transcript: str, title: str, language: str,
    avoid_text: str | None = None, teaser: bool = False,
) -> tuple[int, str, int | None, object | None]:
    """Fotograma elegido, texto, palabra resaltada y consumo (para el coste)."""
    images = None
    if getattr(llm, "supports_images", False):
        images = [to_jpeg(fit(f.image, (360, 640), f.face_x), 80) for f in frames]
    user = json.dumps({"clip_title": title, "transcript": transcript[:2500]}, ensure_ascii=False)
    response = llm.complete_json(system=_system(language, images is not None, avoid_text, teaser), user=user,
                                 schema=SCHEMA, max_tokens=300, images=images)
    data = response.data
    index = int(data.get("frame", 0))
    index = index if 0 <= index < len(frames) else 0
    text = " ".join(str(data.get("text", "")).replace('"', "").split())[:MAX_TEXT_CHARS].strip(" .")
    highlight = int(data.get("highlight", -1))
    highlight = highlight if 0 <= highlight < len(text.split()) else None
    return index, text, highlight, response.usage


def fallback_text(title: str) -> str:
    words = title.replace('"', "").split()
    return " ".join(words[:5])[:MAX_TEXT_CHARS]


def auto_cover(
    src: str | Path, start: float, end: float, *, detector, llm: LLMClient | None, transcript: str, title: str,
    language: str, cost=None, avoid_time: float | None = None, avoid_text: str | None = None,
    teaser: bool = False,
) -> CoverChoice | None:
    """Elige fotograma y texto para la portada de un tramo del vídeo. None si no se pudo leer ningún fotograma."""
    frames = sample_frames(src, start, end, detector)
    if avoid_time is not None:  # «regenerar»: que no repita el mismo fotograma
        frames = [f for f in frames if abs(f.time - avoid_time) > max(0.5, (end - start) / 20)] or frames
    best = shortlist(frames)
    if not best:
        return None
    index, text, highlight = 0, fallback_text(title), None
    if llm is not None:
        try:
            index, ai_text, highlight, usage = ask_ai(llm, best, transcript=transcript, title=title,
                                                      language=language, avoid_text=avoid_text, teaser=teaser)
            text = ai_text or text
            if cost is not None and usage is not None:
                cost.record_llm(usage)
        except Exception as exc:  # la portada nunca debe tumbar el procesamiento
            log.warning("cover.ai_failed", error=str(exc)[:300])
    chosen = best[index]
    return CoverChoice(
        time=chosen.time, face_x=chosen.face_x, text=text, highlight=highlight,
        candidates=[{"time": f.time, "face_x": f.face_x} for f in best],
        base_vertical=to_jpeg(fit(chosen.image, SIZES["vertical"], chosen.face_x)),
        base_horizontal=to_jpeg(fit(chosen.image, SIZES["horizontal"], chosen.face_x)),
    )
