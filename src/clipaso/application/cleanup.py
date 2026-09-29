"""Quitar silencios y muletillas: decide qué tramos sobran y monta el vídeo sin ellos.

Las pausas se detectan por la energía del audio (umbral adaptado al ruido de fondo de cada
vídeo), no solo por los huecos entre palabras de Whisper: así la música o los sonidos sin
voz no se cortan, y las palabras «estiradas» por Whisper sobre un silencio sí se recortan.
Las muletillas salen de la transcripción, hecha en modo literal para que Whisper las escriba.

El montaje es en dos partes: el vídeo con `select` de ffmpeg (preciso al fotograma, incluso
con fotogramas por segundo variables) y el audio con un fundido de pocos milisegundos en cada
corte, para que no se oigan chasquidos.
"""

from __future__ import annotations

import re
import unicodedata
import wave
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from clipaso.domain.models import Sentence, Transcript, Word
from clipaso.domain.segmentation import _join
from clipaso.infra import ffmpeg
from clipaso.infra.logging import get_logger

log = get_logger(__name__)

PaceT = Literal["natural", "normal", "fast"]


@dataclass(frozen=True)
class Pace:
    min_pause: float  # pausas más largas que esto se acortan…
    keep: float  # …hasta dejar esta pausa


PACES: dict[str, Pace] = {
    "natural": Pace(min_pause=0.9, keep=0.5),
    "normal": Pace(min_pause=0.6, keep=0.3),
    "fast": Pace(min_pause=0.4, keep=0.15),
}

# Muletillas que son solo sonido (no palabras con significado), escritas como las transcribe Whisper.
_FILLER = re.compile(r"^(e+h+m*|e+m+|e+r+m+|u+h+m*|u+m+|h+m+|m+h*m+|a+h+m+|ä+h*m*|ö+h+|e+u+h+|e+r+)$")
# Palabras reales en algunos idiomas que coinciden con el patrón.
_NOT_FILLER = {"pt": {"em", "um"}, "ca": {"em"}, "de": {"er"}, "fr": {"hum"}}
# Pista para que Whisper escriba las muletillas (por defecto las omite).
VERBATIM_PROMPTS = {
    "es": "Eh, bueno... em, a ver, mmm, pues eso. Ehh, o sea, vale.",
    "en": "Um, so... uh, I mean, hmm, like, you know. Uhm, okay.",
    "pt": "É, então... hã, tipo, hmm, né. Ehh, bom.",
    "fr": "Euh, bon... ben, hmm, voilà. Euh, alors.",
    "it": "Ehm, allora... cioè, mmm, niente. Eh, ecco.",
    "de": "Äh, also... ähm, hmm, genau. Äh, ja.",
    "ca": "Eh, bé... mmm, a veure, doncs això. Ehh, vale.",
}
DEFAULT_VERBATIM_PROMPT = "Um, eh... uh, hmm, mmm. Ehm, ah."

FRAME = 0.02  # s por ventana de energía
FADE = 0.006  # s de fundido de audio a cada lado de un corte
MIN_CUT = 0.06  # cortes más cortos no merecen la pena
MIN_PIECE = 0.12  # entre dos cortes no se deja un trozo más corto que esto (salvo que haya voz)
MAX_FILLER = 2.0  # s: un tramo con sonido más largo no puede ser solo una muletilla


def verbatim_prompt(language: str | None) -> str:
    return VERBATIM_PROMPTS.get(language or "", DEFAULT_VERBATIM_PROMPT)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text.strip().lower())
    return re.sub(r"[^\wäöü]", "", text)


def is_filler(text: str, language: str | None = None) -> bool:
    word = _norm(text)
    if not word or word in _NOT_FILLER.get(language or "", set()):
        return False
    return bool(_FILLER.match(word))


# --------------------------------------------------------------------------- detección


def quiet_spans(audio: Path, min_length: float) -> list[tuple[float, float]] | None:
    """Tramos en silencio de al menos `min_length` s. None si el audio no permite distinguir
    voz de fondo (música o ruido constantes): entonces solo se usan los huecos entre palabras."""
    with wave.open(str(audio), "rb") as wav:
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    window = int(rate * FRAME)
    n = samples.size // max(window, 1)
    if n < 10:
        return []
    frames = samples[: n * window].astype(np.float32).reshape(n, window) / 32768.0
    db = 20 * np.log10(np.maximum(np.sqrt(np.mean(frames**2, axis=1)), 1e-5))
    floor, speech = float(np.percentile(db, 10)), float(np.percentile(db, 90))
    if speech - floor < 12:
        return None
    threshold = floor + max(6.0, 0.3 * (speech - floor))
    quiet = db < threshold
    spans: list[tuple[float, float]] = []
    start = None
    for i, q in enumerate(np.append(quiet, False)):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * FRAME >= min_length:
                spans.append((start * FRAME, i * FRAME))
            start = None
    return spans


def _subtract(spans: list[tuple[float, float]], holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """`spans` menos `holes` (ambas listas ordenadas; barrido lineal, vale para vídeos de horas)."""
    holes = _merge(holes)
    out: list[tuple[float, float]] = []
    j = 0
    for s, e in sorted(spans):
        while j < len(holes) and holes[j][1] <= s:
            j += 1
        k, cur = j, s
        while k < len(holes) and holes[k][0] < e:
            if holes[k][0] > cur:
                out.append((cur, holes[k][0]))
            cur = max(cur, holes[k][1])
            k += 1
        if cur < e:
            out.append((cur, e))
    return out


def _merge(spans: list[tuple[float, float]], gap: float = 0.0) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1] + gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _core(w: Word) -> tuple[float, float] | None:
    """Parte de la palabra que seguro es voz. Las palabras muy largas suelen estar «estiradas»
    por Whisper sobre una pausa: de esas no se protege nada y manda la energía del audio."""
    d = w.end - w.start
    if d <= 0 or d > 1.2:
        return None
    return (w.start + 0.2 * d, w.end - 0.2 * d)


@dataclass
class CutPlan:
    cuts: list[tuple[float, float]] = field(default_factory=list)
    pauses: int = 0
    fillers: int = 0
    original: float = 0.0

    @property
    def removed(self) -> float:
        return sum(e - s for s, e in self.cuts)

    @property
    def duration(self) -> float:
        return self.original - self.removed

    def stats(self) -> dict:
        return {"original_seconds": round(self.original, 2), "removed_seconds": round(self.removed, 2),
                "pauses": self.pauses, "fillers": self.fillers}


def plan_cuts(
    transcript: Transcript,
    duration: float,
    quiet: list[tuple[float, float]] | None,
    pace: PaceT = "normal",
    remove_fillers: bool = True,
) -> CutPlan:
    p = PACES.get(pace, PACES["normal"])
    words = sorted((w for s in transcript.sentences for w in s.words), key=lambda w: w.start)
    fillers = [w for w in words if remove_fillers and is_filler(w.text, transcript.language)]
    filler_ids = {id(w) for w in fillers}
    cores = [c for w in words if id(w) not in filler_ids and (c := _core(w))]
    core_starts = [c[0] for c in cores]

    def speech_between(a: float, b: float) -> bool:
        i = bisect_left(core_starts, b)
        return any(cores[j][1] > a for j in range(max(0, i - 3), i))

    filler_spans = [(w.start, w.end) for w in fillers]
    if quiet:
        # Whisper marca las muletillas más cortas (y a veces algo adelantadas) de lo que suenan: cada una
        # se amplía al tramo con sonido que más la solapa, si en ese tramo no hay ninguna otra palabra.
        edges = [0.0, *[x for q in sorted(quiet) for x in q], duration]
        voiced = [(a, b) for a, b in zip(edges[::2], edges[1::2], strict=False) if b > a]
        voiced_ends = [b for _, b in voiced]
        widened = []
        for ws, we in filler_spans:
            k = bisect_right(voiced_ends, ws)
            best, overlap = None, 0.0
            for rs, re_ in voiced[k:k + 4]:
                if rs >= we:
                    break
                if (o := min(we, re_) - max(ws, rs)) > overlap:
                    best, overlap = (rs, re_), o
            if best and best[1] - best[0] <= MAX_FILLER and not speech_between(*best):
                ws, we = min(ws, best[0]), max(we, best[1])
            widened.append((ws, we))
        filler_spans = widened

    if quiet is None:
        # Sin referencia de energía: huecos entre palabras (los muy largos se respetan: suelen ser
        # contenido sin voz, no pausas).
        edges = [0.0, *[x for w in words for x in (w.start, w.end)], duration]
        silence = [(a, b) for a, b in zip(edges[::2], edges[1::2], strict=False) if 0 < b - a <= 8.0]
    else:
        silence = _subtract(quiet, cores)
    silence = [(s, e) for s, e in silence if e - s >= 0.1]

    # Bloques de silencio + muletillas contiguos: cada uno se convierte en una sola pausa.
    blocks: list[dict] = []
    items = sorted([(s, e, False) for s, e in silence] + [(s, e, True) for s, e in filler_spans])
    for s, e, is_f in items:
        # Nunca se une a través de una palabra.
        if blocks and s <= blocks[-1]["end"] + 0.08 and not speech_between(blocks[-1]["end"], s):
            b = blocks[-1]
            b["end"] = max(b["end"], e)
        else:
            b = {"start": s, "end": e, "fillers": 0, "silences": []}
            blocks.append(b)
        if is_f:
            b["fillers"] += 1
        else:
            b["silences"].append((s, e))

    plan = CutPlan(original=duration)
    cuts: list[tuple[float, float]] = []
    for b in blocks:
        s, e = b["start"], b["end"]
        at_start, at_end = s <= 0.05, e >= duration - 0.05
        if b["fillers"]:
            # Se quita todo el bloque salvo media pausa en cada borde que sea silencio (en un borde
            # que es la propia muletilla se corta a ras).
            sil = b["silences"]
            left = next((min(p.keep / 2, se - ss) for ss, se in sil if ss <= s + 0.01), 0.0)
            right = next((min(p.keep / 2, se - ss) for ss, se in sil if se >= e - 0.01), 0.0)
            cuts.append((s + (0.0 if at_start else left), e - (0.0 if at_end else right)))
            plan.fillers += b["fillers"]
        elif e - s >= p.min_pause or (at_start or at_end) and e - s >= 0.3:
            keep = min(p.keep, 0.2) / 2 if at_start or at_end else p.keep / 2
            cuts.append((0.0 if at_start else s + keep, duration if at_end else e - keep))
            plan.pauses += 1

    cuts = [(max(0.0, s), min(duration, e)) for s, e in cuts if e - s >= MIN_CUT]
    # Trozos minúsculos entre dos cortes, sin voz: fuera también.
    joined: list[tuple[float, float]] = []
    for s, e in _merge(cuts):
        if joined and s - joined[-1][1] < MIN_PIECE and not speech_between(joined[-1][1], s):
            joined[-1] = (joined[-1][0], e)
        else:
            joined.append((s, e))
    plan.cuts = [(round(s, 3), round(e, 3)) for s, e in joined]
    # Nunca dejar el vídeo vacío (vídeo sin voz o todo silencio).
    if plan.duration < min(1.0, duration * 0.5):
        return CutPlan(original=duration)
    return plan


# --------------------------------------------------------------------------- nueva línea de tiempo


class _Timeline:
    """Cortes ordenados y sin solapes, con búsquedas en O(log n)."""

    def __init__(self, cuts: list[tuple[float, float]]) -> None:
        self.cuts = cuts
        self.ends = [e for _, e in cuts]
        self.before = [0.0]
        for s, e in cuts:
            self.before.append(self.before[-1] + e - s)

    def shift(self, t: float) -> float:
        i = bisect_right(self.ends, t)
        if i < len(self.cuts) and self.cuts[i][0] < t:
            return self.cuts[i][0] - self.before[i]
        return t - self.before[i]

    def covered(self, a: float, b: float) -> float:
        total, k = 0.0, bisect_right(self.ends, a)
        while k < len(self.cuts) and self.cuts[k][0] < b:
            total += max(0.0, min(b, self.cuts[k][1]) - max(a, self.cuts[k][0]))
            k += 1
        return total


def shift(t: float, cuts: list[tuple[float, float]]) -> float:
    """Posición de `t` (vídeo original) en el vídeo ya sin cortes."""
    return _Timeline(cuts).shift(t)


def remap_transcript(transcript: Transcript, plan: CutPlan) -> Transcript:
    """La transcripción en la línea de tiempo del vídeo limpio, sin las palabras cortadas."""
    timeline = _Timeline(plan.cuts)
    sentences: list[Sentence] = []
    for sentence in transcript.sentences:
        words: list[Word] = []
        dropped_first = False
        for i, w in enumerate(sentence.words):
            if timeline.covered(w.start, w.end) >= 0.5 * max(w.end - w.start, 1e-3):
                dropped_first = dropped_first or i == 0 or not words
                continue
            start, end = timeline.shift(w.start), timeline.shift(w.end)
            words.append(w.model_copy(update={"start": round(start, 3), "end": round(max(end, start + 0.04), 3)}))
        if not words:
            continue
        if dropped_first:  # «Eh, bueno…» → «Bueno…»
            first = words[0]
            text = first.text.lstrip()
            words[0] = first.model_copy(update={"text": first.text[: len(first.text) - len(text)]
                                                 + text[:1].upper() + text[1:]})
        sentences.append(Sentence(index=len(sentences), start=words[0].start, end=words[-1].end,
                                  text=_join(words), words=words))
    return Transcript(language=transcript.language, duration=round(plan.duration, 3), sentences=sentences)


# --------------------------------------------------------------------------- montaje


def _sum(terms: list[str]) -> str:
    """Suma en árbol equilibrado: el parser de ffmpeg limita la profundidad y una suma lineal de
    más de ~100 términos falla; así, miles de cortes solo anidan una docena de niveles."""
    if len(terms) == 1:
        return terms[0]
    mid = len(terms) // 2
    return f"({_sum(terms[:mid])}+{_sum(terms[mid:])})"


def _select_expr(cuts: list[tuple[float, float]]) -> tuple[str, str]:
    drop = _sum([f"between(t,{s:.3f},{e:.3f})" for s, e in cuts])
    offset = _sum([f"gte(T,{e:.3f})*{e - s:.3f}" for s, e in cuts])
    return f"not({drop})", offset


def _cut_audio(src: Path, dest: Path, cuts: list[tuple[float, float]], duration: float) -> None:
    """Copia los tramos que se quedan, con un fundido corto en cada unión (sin chasquidos)."""
    with wave.open(str(src), "rb") as wi, wave.open(str(dest), "wb") as wo:
        rate, channels = wi.getframerate(), wi.getnchannels()
        wo.setnchannels(channels)
        wo.setsampwidth(wi.getsampwidth())
        wo.setframerate(rate)
        total = wi.getnframes()
        fade = max(1, int(rate * FADE))
        edges = [0.0, *[x for c in cuts for x in c], duration]
        for a, b in zip(edges[::2], edges[1::2], strict=False):
            first, last = int(round(a * rate)), min(total, int(round(b * rate)))
            if last <= first:
                continue
            wi.setpos(first)
            chunk = np.frombuffer(wi.readframes(last - first), dtype=np.int16).reshape(-1, channels)
            chunk = chunk.astype(np.float32)
            n = min(fade, len(chunk) // 2)
            if n:
                ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
                if a > 0:
                    chunk[:n] *= ramp
                if b < duration:
                    chunk[-n:] *= ramp[::-1]
            wo.writeframes(np.clip(chunk, -32768, 32767).astype(np.int16).tobytes())


def render(source: Path, plan: CutPlan, dest: Path, work: Path) -> Path:
    """Vídeo sin los tramos de `plan` (calidad alta: después se vuelve a codificar con subtítulos)."""
    work.mkdir(parents=True, exist_ok=True)
    full, cut = work / "audio_full.wav", work / "audio_cut.wav"
    ffmpeg.run(["-i", str(source), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(full)],
               what="extracción del audio original")
    _cut_audio(full, cut, plan.cuts, plan.original)
    keep, offset = _select_expr(plan.cuts)
    graph = f"[0:v]setpts=PTS-STARTPTS,select='{keep}',setpts='PTS-({offset})/TB'[v]" if plan.cuts else \
        "[0:v]setpts=PTS-STARTPTS[v]"
    (work / "clean_filter.txt").write_text(graph, encoding="utf-8")
    codec = (["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"]
             if ffmpeg.nvenc_available() else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([
        "-i", str(source.resolve()), "-i", cut.name, "-filter_complex_script", "clean_filter.txt",
        "-map", "[v]", "-map", "1:a:0", "-fps_mode", "vfr", *codec, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(dest.resolve()),
    ], cwd=work, what="montaje sin silencios")
    full.unlink(missing_ok=True)
    cut.unlink(missing_ok=True)
    log.info("clean.rendered", cuts=len(plan.cuts), removed=round(plan.removed, 1),
             duration=round(plan.duration, 1))
    return dest
