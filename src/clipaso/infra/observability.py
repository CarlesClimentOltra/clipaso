"""Envío de errores a Sentry (región UE). Sin DSN configurado no hace nada."""

from __future__ import annotations

from clipaso.infra.config import Settings


def init_sentry(settings: Settings, component: str) -> bool:
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        server_name=component,  # "api" o "worker": permite filtrar en Sentry
        send_default_pii=False,  # sin emails, IPs ni cabeceras de usuarios (RGPD)
        traces_sample_rate=0.0,  # solo errores; el rendimiento no se mide por ahora
        max_request_body_size="never",
    )
    sentry_sdk.set_tag("component", component)
    return True
