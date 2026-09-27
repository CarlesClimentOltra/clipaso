"""Genera subtítulos ASS con la palabra que se está diciendo resaltada."""

from __future__ import annotations

from smartcuts.domain.models import SubtitleStyle, Word

_TRIM = ",.;:…\"'«»“”"


def ass_color(rrggbb: str) -> str:
    rr, gg, bb = rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]
    return f"&H00{bb}{gg}{rr}".upper()


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


def build_ass(words: list[Word], style: SubtitleStyle, width: int, height: int) -> str:
    """`words` con tiempos relativos al inicio del clip."""
    font_size = int(height * style.font_size_ratio)
    outline = max(1, round(height * style.outline_ratio))
    margin_v = int(height * style.margin_v_ratio)
    highlight = ass_color(style.highlight_color)
    primary = ass_color(style.primary_color)

    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style.font},{font_size},{primary},{primary},{ass_color(style.outline_color)},"
        f"&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 2)},2,"
        f"{int(width * 0.08)},{int(width * 0.08)},{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: list[str] = []
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
