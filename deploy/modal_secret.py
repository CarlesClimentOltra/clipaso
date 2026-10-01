"""Crea (o actualiza) el secreto `clipaso-worker` de Modal a partir de tu `.env`.

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
NAME = "clipaso-worker"
WEB_URL = "https://clipaso.com"  # enlaces de los emails al usuario
COPY = [
    "CLIPASO_DATABASE__URL",
    "CLIPASO_AUTH__SUPABASE_URL",
    "CLIPASO_STORAGE__R2_ACCOUNT_ID",
    "CLIPASO_STORAGE__R2_ACCESS_KEY_ID",
    "CLIPASO_STORAGE__R2_SECRET_ACCESS_KEY",
    "CLIPASO_STORAGE__R2_BUCKET",
    "CLIPASO_STORAGE__R2_JURISDICTION",
    "CLIPASO_SENTRY_DSN",
    "CLIPASO_LLM__MODEL",
    "CLIPASO_LLM__EFFORT",
    "CLIPASO_BUDGET__MAX_USD_PER_JOB",
    "ANTHROPIC_API_KEY",
    "CLIPASO_NOTIFICATIONS__BREVO_API_KEY",
    "CLIPASO_NOTIFICATIONS__SENDER_EMAIL",
]
REQUIRED = ["CLIPASO_DATABASE__URL", "CLIPASO_STORAGE__R2_ACCESS_KEY_ID", "ANTHROPIC_API_KEY"]


def main() -> int:
    env = dotenv_values(ROOT / ".env")
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        print(f"Faltan en .env: {', '.join(missing)}")
        return 1
    values = {k: env[k] for k in COPY if env.get(k)}
    values |= {
        "CLIPASO_ENV": "prod",
        "CLIPASO_AUTH__MODE": "supabase",
        "CLIPASO_STORAGE__BACKEND": "r2",
        "CLIPASO_LLM__PROVIDER": "anthropic",
        # El worker no firma URLs propias (usa R2), pero la configuración de prod exige una clave.
        "CLIPASO_API__SECRET_KEY": secrets.token_urlsafe(48),
        "CLIPASO_NOTIFICATIONS__WEB_URL": WEB_URL,
    }
    if env.get("CLIPASO_NOTIFICATIONS__BREVO_API_KEY") and env.get("CLIPASO_NOTIFICATIONS__SENDER_EMAIL"):
        values["CLIPASO_NOTIFICATIONS__PROVIDER"] = "brevo"
    else:
        print("Aviso: sin CLIPASO_NOTIFICATIONS__BREVO_API_KEY/SENDER_EMAIL en .env no se enviarán emails.")
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
