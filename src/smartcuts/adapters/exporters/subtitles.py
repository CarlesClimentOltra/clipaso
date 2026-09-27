"""Subtítulos: ASS incrustado (palabra activa resaltada) y SRT/VTT descargables."""

from __future__ import annotations

from pathlib import Path

from smartcuts.domain.models import SubtitleStyle, Word

# Fuentes libres incluidas en el repo (assets/fonts). ffmpeg las carga con `fontsdir`, así el
# resultado es idéntico en Windows, en Linux y en Modal sin instalar nada en el sistema.
FONTS_DIR = Path(__file__).resolve().parents[4] / "assets" / "fonts"
# Nombre en los estilos → familia real de la fuente incluida.
FONT_ALIASES = {"Arial Black": "Archivo Black"}

_TRIM = ",.;:…\"'«»“”"
_ALIGN = {"bottom": 2, "middle": 5, "top": 8}
_CORNER_ALIGN = {"top-left": 7, "top-right": 9, "bottom-left": 1, "bottom-right": 3}


def ass_color(rrggbb: str, alpha: int = 0) -> str:
    rr, gg, bb = rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]
    return f"&H{alpha:02X}{bb}{gg}{rr}".upper()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str, uppercase: bool) -> str:
    text = text.strip().strip(_TRIM).replace("\\", "").replace("{", "(").replace("}", ")")
    return text.upper() if uppercase else text


def _font(name: str) -> str:
    return FONT_ALIASES.get(name, name)


def chunk_words(words: list[Word], max_words: int, max_seconds: float) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    current: list[Word] = []
    for w in words:
        if current and (
            len(current) >= max_words
            or w.end - current[0].start > max_seconds
            or current[-1].text.strip().endswith((".", "?", "!", ","))
            or w.start - current[-1].end > 0.6
        ):
            chunks.append(current)
            current = []
        current.append(w)
    if current:
        chunks.append(current)
    return chunks


def build_ass(
    words: list[Word],
    style: SubtitleStyle,
    width: int,
    height: int,
    *,
    handle: str = "",
    handle_position: str = "top-right",
    handle_offset: int = 0,
    duration: float = 0.0,
) -> str:
    """`words` con tiempos relativos al inicio del clip. `handle` (p. ej. @usuario) se muestra fijo
    en una esquina durante `duration` segundos; `handle_offset` lo separa del logo si comparten esquina."""
    font_size = int(height * style.font_size_ratio)
    outline = max(1, round(height * style.outline_ratio))
    margin_v = int(height * style.margin_v_ratio) if style.position != "middle" else 0
    highlight = ass_color(style.highlight_color)
    primary = ass_color(style.primary_color)
    if style.box:
        border_style, edge, shadow = 3, max(2, font_size // 5), 0  # caja opaca: el "contorno" es el relleno
        outline_colour = ass_color(style.box_color)
    else:
        border_style, edge, shadow = 1, outline, max(1, outline // 2)
        outline_colour = ass_color(style.outline_color)
    side = int(width * 0.08)

    handle_size = max(12, int(height * 0.024))
    handle_margin = int(min(width, height) * 0.035)
    handle_margin_v = handle_margin + handle_offset

    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{_font(style.font)},{font_size},{primary},{primary},{outline_colour},"
        f"&H80000000,-1,0,0,0,100,100,0,0,{border_style},{edge},{shadow},{_ALIGN[style.position]},"
        f"{side},{side},{margin_v},1\n"
        f"Style: Handle,{_font(style.font)},{handle_size},{ass_color('FFFFFF', 0x30)},{ass_color('FFFFFF')},"
        f"{ass_color('000000', 0x40)},&H80000000,-1,0,0,0,100,100,0,0,1,{max(1, handle_size // 12)},0,"
        f"{_CORNER_ALIGN.get(handle_position, 9)},{handle_margin},{handle_margin},{handle_margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: list[str] = []
    if handle.strip() and duration > 0:
        events.append(f"Dialogue: 1,{ass_time(0)},{ass_time(duration)},Handle,,0,0,0,,{_clean(handle, False)}")
    if style.enabled:
        chunks = chunk_words([w for w in words if _clean(w.text, False)], style.max_words, style.max_chunk_seconds)
        for ci, chunk in enumerate(chunks):
            next_chunk_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else None
            tokens = [_clean(w.text, style.uppercase) for w in chunk]
            for wi, word in enumerate(chunk):
                start = word.start
                if wi + 1 < len(chunk):
                    end = chunk[wi + 1].start
                else:
                    end = word.end + 0.25
                    if next_chunk_start is not None:
                        end = min(end, next_chunk_start)
                if end - start < 0.05:
                    continue
                text = " ".join(
                    f"{{\\c{highlight}}}{tok}{{\\c{primary}}}" if i == wi else tok for i, tok in enumerate(tokens)
                )
                events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"


# --------------------------------------------------------------------------- SRT / VTT


def _caption_time(t: float, sep: str) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def build_captions(words: list[Word], fmt: str = "srt", *, max_words: int = 7, max_seconds: float = 3.5) -> str:
    """Subtítulos estándar para editores (CapCut, Premiere…). `words` relativos al inicio del clip."""
    lines = chunk_words([w for w in words if w.text.strip()], max_words, max_seconds)
    sep = "," if fmt == "srt" else "."
    cues = []
    for i, chunk in enumerate(lines, start=1):
        start, end = chunk[0].start, chunk[-1].end
        text = " ".join(w.text.strip() for w in chunk)
        timing = f"{_caption_time(start, sep)} --> {_caption_time(end, sep)}"
        cues.append(f"{i}\n{timing}\n{text}\n" if fmt == "srt" else f"{timing}\n{text}\n")
    body = "\n".join(cues)
    return body if fmt == "srt" else f"WEBVTT\n\n{body}"
