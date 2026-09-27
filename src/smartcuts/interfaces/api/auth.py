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

import jwt

from smartcuts.infra.config import AuthSettings
from smartcuts.saas.errors import AppError


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
