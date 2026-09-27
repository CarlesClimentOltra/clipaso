"""Usa el almacén de certificados del sistema operativo para TLS.

Antivirus y proxies corporativos que inspeccionan HTTPS instalan su propia CA
en Windows, pero Python usa por defecto el bundle de `certifi` y falla con
CERTIFICATE_VERIFY_FAILED. `truststore` hace que Anthropic, Cloudflare R2 y la
descarga de modelos confíen en lo mismo que el navegador.
"""

from __future__ import annotations

_done = False


def use_system_trust_store() -> None:
    global _done
    if _done:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # sin truststore se sigue con certifi
        pass
    _done = True
