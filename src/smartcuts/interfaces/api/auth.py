"""Verificación de identidad.

- supabase: el frontend inicia sesión con Supabase Auth y envía su JWT; aquí
  solo se verifica (firma, caducidad, audiencia). Las contraseñas nunca pasan
  por nuestra API.
- dev: `Authorization: Bearer dev:<email>`, sin contraseña. Solo desarrollo
  local; la configuración de producción lo prohíbe.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt

from smartcuts.infra.config import AuthSettings
from smartcuts.infra.logging import get_logger
from smartcuts.saas.errors import AppError

log = get_logger(__name__)


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_token(token: str, cfg: AuthSettings) -> Identity:
    if cfg.mode == "dev":
        if not token.startswith("dev:") or "@" not in token:
            raise AppError("auth_required", 401)
        email = token.removeprefix("dev:").strip().lower()
        return Identity(subject=f"dev|{email}", email=email)

    try:
        if cfg.supabase_jwt_secret:
            claims = jwt.decode(token, cfg.supabase_jwt_secret, algorithms=["HS256"], audience=cfg.audience)
        else:
            jwks = _jwks_client(f"{cfg.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
            key = jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience=cfg.audience)
    except jwt.PyJWTError as exc:
        raise AppError("auth_required", 401, detail=str(exc)) from exc

    subject = claims.get("sub")
    if not subject:
        raise AppError("auth_required", 401)
    return Identity(subject=subject, email=claims.get("email", ""))


def delete_identity(subject: str, cfg: AuthSettings) -> None:
    """Borra el usuario del proveedor de identidad (email y contraseña). En dev no hay nada que borrar."""
    if cfg.mode == "dev":
        return
    key = cfg.supabase_service_key
    if not key:
        raise AppError("internal_error", 503, detail="Falta SMARTCUTS_AUTH__SUPABASE_SERVICE_KEY")
    # Las claves nuevas (sb_secret_…) van solo en `apikey`; las heredadas (JWT service_role) también como Bearer.
    headers = {"apikey": key}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    r = httpx.delete(f"{cfg.supabase_url.rstrip('/')}/auth/v1/admin/users/{subject}", headers=headers, timeout=15)
    if r.status_code == 404:
        return  # ya no existía
    if r.is_error:
        raise AppError("internal_error", 502, detail=f"Supabase admin {r.status_code}: {r.text[:300]}")
    log.info("auth.identity_deleted")
