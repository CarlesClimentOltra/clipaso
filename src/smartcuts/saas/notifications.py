"""Emails al usuario cuando su vídeo termina (clips listos o fallo con minutos devueltos).

Se envían con la API transaccional de Brevo (servidores en la UE). Un fallo al
enviar nunca afecta al procesamiento: se registra y se sigue.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Protocol

import httpx

from smartcuts.infra.config import NotificationSettings
from smartcuts.infra.logging import get_logger
from smartcuts.saas.errors import user_message

log = get_logger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    html: str
    text: str


class Notifier(Protocol):
    def send(self, email: Email) -> None: ...


class NullNotifier:
    def send(self, email: Email) -> None:
        log.info("email.skipped", to_domain=email.to.rsplit("@", 1)[-1], subject=email.subject)


class BrevoNotifier:
    def __init__(self, api_key: str, sender_email: str, sender_name: str) -> None:
        self.api_key, self.sender_email, self.sender_name = api_key, sender_email, sender_name

    def send(self, email: Email) -> None:
        r = httpx.post(
            BREVO_URL,
            headers={"api-key": self.api_key, "accept": "application/json"},
            json={
                "sender": {"email": self.sender_email, "name": self.sender_name},
                "to": [{"email": email.to}],
                "subject": email.subject,
                "htmlContent": email.html,
                "textContent": email.text,
                "tags": ["job-notification"],
            },
            timeout=15,
        )
        r.raise_for_status()


def build_notifier(settings: NotificationSettings) -> Notifier:
    if settings.provider == "brevo" and settings.brevo_api_key and settings.sender_email:
        return BrevoNotifier(settings.brevo_api_key, settings.sender_email, settings.sender_name)
    return NullNotifier()


def _layout(title: str, body: str, button: tuple[str, str] | None) -> str:
    cta = ""
    if button:
        label, url = button
        cta = (f'<p style="margin:28px 0"><a href="{escape(url)}" style="background:#6d4aff;color:#fff;'
               f'padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600">{escape(label)}</a></p>')
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;padding:24px;'
        'color:#1a1a1a;line-height:1.5">'
        f'<p style="font-weight:700;font-size:18px;margin:0 0 20px">SmartCuts</p>'
        f'<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>{body}{cta}'
        '<p style="color:#888;font-size:12px;margin-top:32px">Recibes este email porque subiste un vídeo a '
        'SmartCuts.</p></div>'
    )


def clips_ready(to: str, title: str, clip_count: int, retention_days: int, project_url: str) -> Email:
    clips = "1 clip" if clip_count == 1 else f"{clip_count} clips"
    body = (f"<p>Hemos terminado <strong>{escape(title)}</strong>: tienes {clips} listos para ver y descargar.</p>"
            f"<p>Estarán disponibles durante {retention_days} días.</p>")
    return Email(
        to=to,
        subject=f"Tus clips de «{title}» están listos",
        html=_layout("Tus clips están listos", body, ("Ver mis clips", project_url)),
        text=(f"Hemos terminado «{title}»: tienes {clips} listos.\nVer y descargar: {project_url}\n"
              f"Estarán disponibles durante {retention_days} días."),
    )


def processing_failed(to: str, title: str, error_code: str, new_project_url: str) -> Email:
    reason = user_message(error_code) or ""
    body = (f"<p>No hemos podido procesar <strong>{escape(title)}</strong>.</p><p>{escape(reason)}</p>"
            "<p>Los minutos de este vídeo se han devuelto a tu cuenta.</p>")
    return Email(
        to=to,
        subject=f"No hemos podido procesar «{title}»",
        html=_layout("No hemos podido procesar tu vídeo", body, ("Probar de nuevo", new_project_url)),
        text=(f"No hemos podido procesar «{title}». {reason}\nLos minutos se han devuelto a tu cuenta.\n"
              f"Probar de nuevo: {new_project_url}"),
    )


def deliver(notifier: Notifier, email: Email) -> bool:
    try:
        notifier.send(email)
        return True
    except Exception as exc:
        log.warning("email.failed", error=str(exc)[:300])
        return False
