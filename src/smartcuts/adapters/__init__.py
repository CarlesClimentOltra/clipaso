"""Implementaciones concretas de los puertos del dominio.

Importar este paquete registra todos los adaptadores en `smartcuts.infra.registry`.
Para añadir uno nuevo: crea el módulo, decóralo con `@register(...)` e impórtalo aquí.
"""

from smartcuts.adapters.exporters import ffmpeg_exporter  # noqa: F401
from smartcuts.adapters.llm import anthropic_client, claude_cli  # noqa: F401
from smartcuts.adapters.reframing import face_track, simple  # noqa: F401
from smartcuts.adapters.selection import heuristic, hybrid  # noqa: F401
from smartcuts.adapters.signals import audio_energy, speech_rate  # noqa: F401
from smartcuts.adapters.sources import local_file  # noqa: F401
from smartcuts.adapters.storage import local, r2  # noqa: F401
from smartcuts.adapters.transcription import faster_whisper  # noqa: F401
