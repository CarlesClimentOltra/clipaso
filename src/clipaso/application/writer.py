"""Del vídeo al texto: a partir de la transcripción, la IA escribe los textos para publicar.

En una sola petición al modelo rápido: resumen, capítulos con marca de tiempo (formato de YouTube), artículo
de blog, post de LinkedIn, hilo de X y título, descripción y etiquetas SEO. Los capítulos se validan con las
reglas de YouTube (el primero en 00:00, al menos tres y separados por 10 s o más).
"""

from __future__ import annotations

from typing import Any

from clipaso.application.cost import CostTracker
from clipaso.application.translation import LANGUAGE_NAMES
from clipaso.domain.errors import ClipasoError
from clipaso.domain.models import Transcript
from clipaso.domain.ports import LLMClient
from clipaso.infra.logging import get_logger

log = get_logger(__name__)

MAX_TRANSCRIPT_CHARS = 180_000  # ~45k tokens: vídeos de varias horas
MIN_CHAPTER_GAP = 10.0
CHAPTERS_MIN_VIDEO = 60.0

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Resumen en 3-6 frases."},
        "key_points": {"type": "array", "items": {"type": "string"}, "description": "3-7 ideas clave."},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"start_seconds": {"type": "number"}, "title": {"type": "string"}},
                "required": ["start_seconds", "title"],
                "additionalProperties": False,
            },
        },
        "blog_title": {"type": "string"},
        "blog_markdown": {"type": "string", "description": "Artículo en Markdown, sin repetir el título."},
        "linkedin": {"type": "string"},
        "thread": {"type": "array", "items": {"type": "string"}},
        "seo_title": {"type": "string"},
        "seo_description": {"type": "string"},
        "seo_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "key_points", "chapters", "blog_title", "blog_markdown", "linkedin", "thread",
                 "seo_title", "seo_description", "seo_tags"],
    "additionalProperties": False,
}


def _ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def _system(language: str) -> str:
    lang = LANGUAGE_NAMES.get(language, language)
    return (
        "You are a content writer who turns video transcripts into ready-to-publish texts. "
        f"Write everything in {lang}, in a natural, clear style, faithful to what is said in the video: never "
        "invent facts, names or figures that are not in the transcript. Refer to the person speaking naturally "
        f"in {lang} (by name if it is said; never with the English word 'speaker' unless writing in English). "
        "Each transcript line starts with its timestamp [mm:ss].\n"
        "- summary: 3-6 sentences on what the video covers and its main takeaway.\n"
        "- key_points: 3-7 short key ideas.\n"
        "- chapters: YouTube chapters in order; the first one starts at 0, at least 3 chapters, each at least "
        "10 seconds long, with short descriptive titles (max 60 characters). Use the transcript timestamps.\n"
        "- blog_title and blog_markdown: a blog article (500-900 words) based on the video, with an intro, "
        "## subheadings and a conclusion. Do not repeat the title inside the body.\n"
        "- linkedin: a LinkedIn post (120-220 words) with a strong first line, short paragraphs and a closing "
        "question. At most 3 hashtags at the end.\n"
        "- thread: an X (Twitter) thread of 4-8 posts, each under 270 characters; the first one is a hook.\n"
        "- seo_title (max 70 characters), seo_description (max 160 characters) and seo_tags (8-15 tags, "
        "without #) to publish the video on YouTube."
    )


def chapters_text(chapters: list[dict]) -> str:
    """Los capítulos tal como se pegan en la descripción de YouTube."""
    return "\n".join(f"{_ts(c['start'])} {c['title']}" for c in chapters)


def _valid_chapters(raw: list[dict], duration: float) -> list[dict]:
    if duration < CHAPTERS_MIN_VIDEO:
        return []
    chapters: list[dict] = []
    for item in sorted(raw, key=lambda c: float(c.get("start_seconds", 0))):
        start = max(0.0, min(float(item.get("start_seconds", 0)), duration - MIN_CHAPTER_GAP))
        title = " ".join(str(item.get("title", "")).split())[:80]
        if not title:
            continue
        if not chapters:
            start = 0.0  # YouTube exige que el primero empiece en 00:00
        elif start - chapters[-1]["start"] < MIN_CHAPTER_GAP:
            continue
        chapters.append({"start": round(start, 1), "title": title})
    return chapters if len(chapters) >= 3 else []


class TextWriter:
    def __init__(self, llm: LLMClient, cost: CostTracker) -> None:
        self.llm = llm
        self.cost = cost

    def write(self, transcript: Transcript, *, duration: float, language: str, title: str = "") -> dict:
        lines = "\n".join(f"[{_ts(s.start)}] {s.text}" for s in transcript.sentences)
        if len(lines) > MAX_TRANSCRIPT_CHARS:
            lines = lines[:MAX_TRANSCRIPT_CHARS] + "\n[…]"
        user = (f"Video title: {title or '(unknown)'}\nDuration: {_ts(duration)}\n"
                f"\n<transcript>\n{lines}\n</transcript>")
        system = _system(language)
        if getattr(self.llm, "billable", True):
            est_in = self.llm.estimate_input_tokens(system + user)
            self.cost.check("textos del vídeo", self.cost.llm_cost(self.llm.model, est_in, 6000))
        response = self.llm.complete_json(system=system, user=user, schema=SCHEMA, max_tokens=8000)
        self.cost.record_llm(response.usage)
        d = response.data
        chapters = _valid_chapters(d.get("chapters", []), duration)
        result = {
            "language": language,
            "summary": str(d.get("summary", "")).strip(),
            "key_points": [str(p).strip() for p in d.get("key_points", []) if str(p).strip()][:10],
            "chapters": chapters,
            "chapters_text": chapters_text(chapters),
            "blog_title": str(d.get("blog_title", "")).strip(),
            "blog_markdown": str(d.get("blog_markdown", "")).strip(),
            "linkedin": str(d.get("linkedin", "")).strip(),
            "thread": [str(p).strip() for p in d.get("thread", []) if str(p).strip()][:12],
            "seo_title": str(d.get("seo_title", "")).strip()[:100],
            "seo_description": str(d.get("seo_description", "")).strip()[:300],
            "seo_tags": [str(t).strip().lstrip("#") for t in d.get("seo_tags", []) if str(t).strip()][:20],
        }
        if not result["summary"]:
            raise ClipasoError("La IA no devolvió textos")
        log.info("writer.done", chapters=len(chapters), blog_words=len(result["blog_markdown"].split()),
                 thread=len(result["thread"]))
        return result
