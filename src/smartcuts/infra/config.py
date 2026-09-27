"""Configuración por entorno.

Prioridad (de mayor a menor): variables de entorno `SMARTCUTS_*` > fichero
`.env` > valores por defecto de este módulo. Los anidados usan `__`, p. ej.
`SMARTCUTS_TRANSCRIPTION__MODEL=medium`.

Los formatos de salida no viven aquí sino en `configs/output_profiles/*.yaml`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.models import OutputProfile

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TranscriptionSettings(BaseModel):
    provider: str = "faster_whisper"
    # large-v3-turbo en int8_float16 cabe holgadamente en los 4 GB de una GTX 1650.
    model: str = "large-v3-turbo"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    compute_type: str = "int8_float16"
    cpu_compute_type: str = "int8"
    beam_size: int = 5
    vad_filter: bool = True


class LLMSettings(BaseModel):
    # anthropic: API de pago por uso (necesita ANTHROPIC_API_KEY). Obligatorio en producción.
    # claude_cli: Claude Code con tu suscripción personal. SOLO para pruebas locales tuyas:
    #             no se puede usar para servir a otros usuarios.
    provider: Literal["anthropic", "claude_cli"] = "anthropic"
    # Sonnet 5 con esfuerzo medio: buena selección a un coste por vídeo razonable para un SaaS.
    model: str = "claude-sonnet-5"
    # Modelo para 'claude_cli': alias de Claude Code (sonnet, opus) o id completo.
    cli_model: str = "sonnet"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    max_output_tokens: int = 16000
    # Reenvía la petición a otro modelo si los clasificadores de seguridad la rechazan.
    server_side_fallback: bool = True
    timeout_seconds: float = 600.0


class SelectionSettings(BaseModel):
    strategy: str = "hybrid"
    # Si el LLM falla (sin API key, presupuesto, red…) se usa la heurística.
    fallback_strategy: str = "heuristic"
    signals: list[str] = Field(default_factory=lambda: ["audio_energy", "speech_rate"])
    weights: dict[str, float] = Field(
        default_factory=lambda: {"audio_energy": 0.6, "speech_rate": 0.4}
    )
    llm_weight: float = Field(0.75, description="Peso del LLM frente a las señales en 'hybrid'.")
    min_gap_seconds: float = 2.0


class BudgetSettings(BaseModel):
    max_usd_per_job: float = 1.50
    # USD por millón de tokens (entrada, salida). Mantener al día con la web de precios.
    pricing: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {
            "claude-opus-5-5": (4.0, 20.0),
            "claude-opus-5": (5.0, 25.0),
            "claude-sonnet-5": (2.0, 10.0),
            "claude-haiku-4-5": (1.0, 5.0),
        }
    )


class DatabaseSettings(BaseModel):
    # Desarrollo: SQLite en data/ (cero infraestructura). Producción: Postgres de Supabase,
    # p. ej. postgresql+psycopg://postgres.xxx:PASS@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
    url: str = ""
    echo: bool = False


class AuthSettings(BaseModel):
    # dev: token "dev:<email>" sin contraseña (solo local). supabase: JWT de Supabase Auth.
    mode: Literal["dev", "supabase"] = "dev"
    supabase_url: str = ""  # https://<proyecto>.supabase.co
    # Solo proyectos con claves JWT heredadas (HS256). Si está vacío se validan con las claves públicas (JWKS).
    supabase_jwt_secret: str = ""
    audience: str = "authenticated"


class StorageSettings(BaseModel):
    backend: Literal["local", "r2"] = "local"
    local_root: Path | None = None  # por defecto data/storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    # "eu": los datos se quedan en la UE (bucket creado con jurisdicción EU en Cloudflare).
    r2_jurisdiction: Literal["eu", "default"] = "eu"


class ApiSettings(BaseModel):
    public_url: str = "http://localhost:8000"  # URL pública de la API (enlaces firmados en dev)
    web_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    # Firma de URLs de almacenamiento local y otros tokens internos. Cambiar en producción.
    secret_key: str = "dev-insecure-change-me"
    signed_url_ttl_seconds: int = 3600


class WorkerSettings(BaseModel):
    dispatcher: Literal["local", "modal"] = "local"
    poll_seconds: float = 2.0
    # Un job 'running' sin latido en este tiempo se considera huérfano (worker caído).
    stale_after_seconds: int = 900
    max_attempts: int = 2


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMARTCUTS_",
        env_nested_delimiter="__",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    log_json: bool = False
    sentry_dsn: str = ""  # vacío = Sentry desactivado

    data_dir: Path = PROJECT_ROOT / "data"
    output_dir: Path = PROJECT_ROOT / "output"
    profiles_dir: Path = PROJECT_ROOT / "configs" / "output_profiles"

    language: str = "es"
    default_profile: str = "vertical_9x16"
    default_clips: int = 5

    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    selection: SelectionSettings = Field(default_factory=SelectionSettings)
    budget: BudgetSettings = Field(default_factory=BudgetSettings)

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)

    @model_validator(mode="after")
    def _production_safety(self) -> Settings:
        if self.env != "prod":
            return self
        problems = []
        if self.api.secret_key == ApiSettings().secret_key:
            problems.append("SMARTCUTS_API__SECRET_KEY sigue con el valor por defecto")
        if self.auth.mode != "supabase":
            problems.append("SMARTCUTS_AUTH__MODE debe ser 'supabase'")
        if self.llm.provider == "claude_cli":
            problems.append("el proveedor 'claude_cli' (suscripción personal) no puede servir a otros usuarios")
        if not self.database.url.startswith("postgresql"):
            problems.append("SMARTCUTS_DATABASE__URL debe apuntar a Postgres")
        if self.storage.backend != "r2":
            problems.append("SMARTCUTS_STORAGE__BACKEND debe ser 'r2'")
        if problems:
            raise ValueError("Configuración de producción insegura: " + "; ".join(problems))
        return self

    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def database_url(self) -> str:
        return self.database.url or f"sqlite:///{(self.data_dir / 'smartcuts.db').as_posix()}"

    def storage_root(self) -> Path:
        return self.storage.local_root or self.data_dir / "storage"

    def load_profile(self, name: str) -> OutputProfile:
        path = self.profiles_dir / f"{name}.yaml"
        if not path.exists():
            available = ", ".join(self.list_profiles()) or "(ninguno)"
            raise ConfigurationError(f"Perfil de salida '{name}' no existe. Disponibles: {available}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw.setdefault("name", name)
        return OutputProfile.model_validate(raw)

    def list_profiles(self) -> list[str]:
        if not self.profiles_dir.exists():
            return []
        return sorted(p.stem for p in self.profiles_dir.glob("*.yaml"))


@lru_cache
def get_settings() -> Settings:
    # Vuelca también el .env al entorno del proceso: así los SDK de terceros
    # (p. ej. ANTHROPIC_API_KEY para Anthropic) lo encuentran sin más.
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return Settings()
