"""Guardar, recomponer y regenerar las portadas de los clips.

`clip.cover` guarda la decisión y dónde están las imágenes:
{"n": versión, "time", "face_x", "text", "highlight", "template", "candidates": [{"time", "face_x"}],
 "base_vertical", "base_horizontal", "vertical", "horizontal", "pending": bool}
Las «base» son el fotograma ya recortado sin texto; las otras dos, las portadas terminadas.
"""

from __future__ import annotations

from pathlib import Path

from clipaso.domain.ports import Storage
from clipaso.infra.logging import get_logger
from clipaso.saas import covers
from clipaso.saas.artifacts import logo_key
from clipaso.saas.errors import AppError
from clipaso.saas.models import Clip, Job, User
from clipaso.saas.presets import BrandingPrefs, CaptionStyle
from clipaso.saas.services import clips_prefix

log = get_logger(__name__)


def branding_logo(storage: Storage, user: User | None, options: dict) -> tuple[bytes | None, str]:
    """Logo de la marca (si el proyecto la lleva) y su esquina."""
    if user is None or not options.get("branding"):
        return None, "top-right"
    prefs = BrandingPrefs.model_validate((user.preferences or {}).get("branding", {}))
    if not prefs.enabled or not prefs.has_logo:
        return None, prefs.position
    return storage.read_bytes(logo_key(user.id)), prefs.position


def _keys(user_id: str, job_id: str, clip: Clip, n: int) -> dict[str, str]:
    prefix = clips_prefix(user_id, job_id).rstrip("/")
    stem = f"{prefix}/{clip.rank:02d}-portada-{n}"
    return {"base_vertical": f"{stem}-base-v.jpg", "base_horizontal": f"{stem}-base-h.jpg",
            "vertical": f"{stem}-9x16.jpg", "horizontal": f"{stem}-16x9.jpg"}


def _drop_images(storage: Storage, cover: dict | None) -> None:
    for name in ("base_vertical", "base_horizontal", "vertical", "horizontal"):
        if cover and (key := cover.get(name)):
            storage.delete_prefix(key)


def _store(
    storage: Storage, user_id: str, job_id: str, clip: Clip, *, base_v: bytes, base_h: bytes, info: dict,
    style: CaptionStyle, logo: bytes | None, logo_position: str,
) -> dict:
    """Compone las dos portadas, las sube y sustituye a las anteriores."""
    previous = clip.cover
    n = (previous or {}).get("n", 0) + 1
    keys = _keys(user_id, job_id, clip, n)
    template = info.get("template") or covers.DEFAULT_TEMPLATE
    finished = {
        size: covers.compose(base, covers.SIZES[size], text=info.get("text", ""), highlight=info.get("highlight"),
                             template=template, style=style, logo=logo, logo_position=logo_position)
        for size, base in (("vertical", base_v), ("horizontal", base_h))
    }
    storage.put_bytes(keys["base_vertical"], base_v, "image/jpeg")
    storage.put_bytes(keys["base_horizontal"], base_h, "image/jpeg")
    storage.put_bytes(keys["vertical"], finished["vertical"], "image/jpeg")
    storage.put_bytes(keys["horizontal"], finished["horizontal"], "image/jpeg")
    _drop_images(storage, previous)
    cover = {**info, "template": template, "n": n, **keys, "pending": False}
    clip.cover = cover
    return cover


def save_choice(
    storage: Storage, user_id: str, job_id: str, clip: Clip, choice: covers.CoverChoice, *, style: CaptionStyle,
    logo: bytes | None, logo_position: str,
) -> dict:
    """Guarda la propuesta de la IA (conserva la plantilla que eligiera el usuario)."""
    template = (clip.cover or {}).get("template", covers.DEFAULT_TEMPLATE)
    info = {"time": choice.time, "face_x": choice.face_x, "text": choice.text, "highlight": choice.highlight,
            "template": template, "candidates": choice.candidates}
    return _store(storage, user_id, job_id, clip, base_v=choice.base_vertical, base_h=choice.base_horizontal, info=info,
                  style=style, logo=logo, logo_position=logo_position)


def update(
    storage: Storage, job: Job, clip: Clip, *, style: CaptionStyle, logo: bytes | None, logo_position: str,
    text: str | None, highlight: int | None, template: str | None, time: float | None,
    source: str | Path | None, model_dir: Path,
) -> dict:
    """Cambios del usuario en el editor: texto, palabra resaltada, plantilla u otro fotograma."""
    current = clip.cover
    if current is None:
        raise AppError("not_found", 404)
    if template is not None and template not in covers.TEMPLATES:
        raise AppError("validation_error")
    info = {**current}
    if text is not None:
        info["text"] = " ".join(text.split())[: covers.MAX_TEXT_CHARS]
        words = len(info["text"].split())
        if info.get("highlight") is not None and info["highlight"] >= words:
            info["highlight"] = None
    if highlight is not None:
        info["highlight"] = highlight if 0 <= highlight < len(info.get("text", "").split()) else None
    if template is not None:
        info["template"] = template

    if time is not None and abs(time - float(current.get("time", -1))) > 0.05:
        # Fotogramas guardados (miniaturas sin vídeo): se usan tal cual.
        stored = next((c for c in current.get("candidates", [])
                       if c.get("key") and abs(c["time"] - time) < 0.05), None)
        if stored is not None:
            data = storage.read_bytes(stored["key"])
            frame = covers.from_jpeg(data) if data else None
            face_x = stored.get("face_x")
        else:
            if source is None:
                raise AppError("source_unavailable", 409)
            time = min(max(time, clip.start), clip.end)
            frame = covers.grab_frame(source, time, max_width=1920)
            # La cara de ese momento: la de un candidato cercano o, si no, se detecta ahora.
            near = next((c for c in current.get("candidates", []) if abs(c["time"] - time) < 0.3), None)
            if near is not None or frame is None:
                face_x = near.get("face_x") if near else None
            else:
                face_x = covers.score_frame(frame, covers.face_detector(model_dir))[1]
        if frame is None:
            raise AppError("validation_error", key="cover_frame")
        info["time"], info["face_x"] = round(time, 2), face_x
        base_v = covers.to_jpeg(covers.fit(frame, covers.SIZES["vertical"], face_x))
        base_h = covers.to_jpeg(covers.fit(frame, covers.SIZES["horizontal"], face_x))
    else:
        base_v = storage.read_bytes(current["base_vertical"])
        base_h = storage.read_bytes(current["base_horizontal"])
        if base_v is None or base_h is None:
            raise AppError("not_found", 404)
    return _store(storage, job.user_id, job.id, clip, base_v=base_v, base_h=base_h, info=info, style=style,
                  logo=logo, logo_position=logo_position)


def generate(
    storage: Storage, user_id: str, job_id: str, clip: Clip, *, source: str | Path, transcript, language: str,
    style: CaptionStyle, logo: bytes | None, logo_position: str, llm, detector, cost=None, again: bool = False,
    teaser: bool = False,
) -> dict | None:
    """Propuesta automática (IA) de portada para un clip. `again`: otra distinta de la actual."""
    current = clip.cover or {}
    choice = covers.auto_cover(
        source, clip.start, clip.end, detector=detector, llm=llm, cost=cost, title=clip.title, language=language,
        transcript=transcript_excerpt(transcript, clip.start, clip.end),
        avoid_time=current.get("time") if again else None, avoid_text=current.get("text") if again else None,
        teaser=teaser,
    )
    if choice is None:
        return None
    return save_choice(storage, user_id, job_id, clip, choice, style=style, logo=logo, logo_position=logo_position)


def generate_for_clips(
    storage: Storage, settings, user_id: str, job_id: str, clips: list[Clip], *, source: str | Path, transcript,
    options: dict, logo: bytes | None, logo_position: str, again: bool = False,
) -> float:
    """Portadas automáticas de varios clips (worker). Un fallo en una no afecta al resto. Devuelve el coste (USD)."""
    from clipaso.bootstrap import build_cost_tracker, build_fast_llm
    from clipaso.saas.rendering import caption_style

    cost = build_cost_tracker(settings)
    try:
        llm = build_fast_llm(settings)
    except Exception as exc:  # sin IA, las portadas se eligen por puntuación con el título del clip
        log.warning("cover.no_llm", error=str(exc)[:200])
        llm = None
    detector = covers.face_detector(settings.data_dir / "models")
    language = options.get("subtitle_language") or (transcript.language if transcript else "es")
    for clip in clips:
        style = caption_style(options, clip.caption_style)
        try:
            generate(storage, user_id, job_id, clip, source=source, transcript=transcript, language=language,
                     style=style, logo=logo, logo_position=logo_position, llm=llm, detector=detector, cost=cost,
                     again=again, teaser=options.get("mode") == "trailer")
        except Exception as exc:
            log.warning("cover.failed", rank=clip.rank, error=str(exc)[:300])
    return cost.spent


def transcript_excerpt(transcript, start: float, end: float) -> str:
    if transcript is None:
        return ""
    return " ".join(w.text.strip() for w in transcript.words_between(start, end))[:2500]
