"""Carga en Fly.io los secretos de la API a partir de tu `.env` y de tu sesión de Modal.

    .venv\\Scripts\\python deploy\\fly_secrets.py

La API necesita: base de datos, Supabase, R2, Sentry y un token de Modal (para enviar
los vídeos al worker) y la clave de Anthropic para las miniaturas sin subir el vídeo
(la IA de los clips corre en el worker).
Ningún valor se imprime.
"""

from __future__ import annotations

import secrets
import subprocess
import sys
import tomllib
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
FLYCTL = Path.home() / ".fly" / "bin" / ("flyctl.exe" if sys.platform == "win32" else "flyctl")
COPY = [
    "CLIPASO_DATABASE__URL",
    "CLIPASO_AUTH__SUPABASE_URL",
    "CLIPASO_AUTH__SUPABASE_SERVICE_KEY",  # para eliminar cuentas
    "CLIPASO_STORAGE__R2_ACCOUNT_ID",
    "CLIPASO_STORAGE__R2_ACCESS_KEY_ID",
    "CLIPASO_STORAGE__R2_SECRET_ACCESS_KEY",
    "CLIPASO_STORAGE__R2_BUCKET",
    "CLIPASO_SENTRY_DSN",
    "ANTHROPIC_API_KEY",  # miniaturas sin subir el vídeo: la API elige el fotograma y escribe el texto
]
REQUIRED = ["CLIPASO_DATABASE__URL", "CLIPASO_AUTH__SUPABASE_URL", "CLIPASO_STORAGE__R2_ACCESS_KEY_ID"]


def modal_token() -> dict[str, str]:
    config = tomllib.loads((Path.home() / ".modal.toml").read_text(encoding="utf-8"))
    profile = next((p for p in config.values() if p.get("active")), None) or next(iter(config.values()))
    return {"MODAL_TOKEN_ID": profile["token_id"], "MODAL_TOKEN_SECRET": profile["token_secret"]}


def main() -> int:
    env = dotenv_values(ROOT / ".env")
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        print(f"Faltan en .env: {', '.join(missing)}")
        return 1
    values = {k: env[k] for k in COPY if env.get(k)}
    values |= modal_token()
    # Solo firma URLs del almacenamiento local (no se usa con R2), pero prod exige una clave propia.
    values["CLIPASO_API__SECRET_KEY"] = secrets.token_urlsafe(48)

    payload = "\n".join(f"{k}={v}" for k, v in values.items())
    # --stage: se aplican en el próximo despliegue (no reinicia nada ahora).
    result = subprocess.run([str(FLYCTL), "secrets", "import", "--stage", "--config", str(ROOT / "fly.toml")],
                            input=payload, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return result.returncode
    print(f"Secretos cargados en Fly ({len(values)}): {', '.join(sorted(values))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
