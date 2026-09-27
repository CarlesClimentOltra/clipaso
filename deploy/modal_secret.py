"""Crea (o actualiza) el secreto `smartcuts-worker` de Modal a partir de tu `.env`.

    .venv\\Scripts\\python deploy\\modal_secret.py

Copia solo lo que necesita el worker y fuerza la configuración de producción
(API de Anthropic en vez de la suscripción personal). Ningún valor se imprime.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
NAME = "smartcuts-worker"
COPY = [
    "SMARTCUTS_DATABASE__URL",
    "SMARTCUTS_AUTH__SUPABASE_URL",
    "SMARTCUTS_STORAGE__R2_ACCOUNT_ID",
    "SMARTCUTS_STORAGE__R2_ACCESS_KEY_ID",
    "SMARTCUTS_STORAGE__R2_SECRET_ACCESS_KEY",
    "SMARTCUTS_STORAGE__R2_BUCKET",
    "SMARTCUTS_STORAGE__R2_JURISDICTION",
    "SMARTCUTS_SENTRY_DSN",
    "SMARTCUTS_LLM__MODEL",
    "SMARTCUTS_LLM__EFFORT",
    "SMARTCUTS_BUDGET__MAX_USD_PER_JOB",
    "ANTHROPIC_API_KEY",
]
REQUIRED = ["SMARTCUTS_DATABASE__URL", "SMARTCUTS_STORAGE__R2_ACCESS_KEY_ID", "ANTHROPIC_API_KEY"]


def main() -> int:
    env = dotenv_values(ROOT / ".env")
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        print(f"Faltan en .env: {', '.join(missing)}")
        return 1
    values = {k: env[k] for k in COPY if env.get(k)}
    values |= {
        "SMARTCUTS_ENV": "prod",
        "SMARTCUTS_AUTH__MODE": "supabase",
        "SMARTCUTS_STORAGE__BACKEND": "r2",
        "SMARTCUTS_LLM__PROVIDER": "anthropic",
        # El worker no firma URLs propias (usa R2), pero la configuración de prod exige una clave.
        "SMARTCUTS_API__SECRET_KEY": secrets.token_urlsafe(48),
    }
    cli = [sys.executable, str(ROOT / "deploy" / "modal_cli.py")]
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(values, f)
        result = subprocess.run([*cli, "secret", "create", NAME, "--from-json", path, "--force"],
                                capture_output=True, text=True)
    finally:
        os.remove(path)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return result.returncode
    print(f"Secreto '{NAME}' actualizado con {len(values)} variables: {', '.join(sorted(values))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
