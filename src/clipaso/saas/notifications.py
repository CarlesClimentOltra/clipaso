"""Emails al usuario cuando su vídeo termina (clips listos o fallo con minutos devueltos).

Se envían con la API transaccional de Brevo (servidores en la UE). Un fallo al
enviar nunca afecta al procesamiento: se registra y se sigue.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Protocol

import httpx

from clipaso.infra.config import NotificationSettings
from clipaso.infra.logging import get_logger
from clipaso.saas.errors import user_message

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


TEXTS = {
    "es": {
        "footer": "Recibes este email porque subiste un vídeo a Clipaso.",
        "ready_title": "Tus clips están listos",
        "ready_subject": "Tus clips de «{title}» están listos",
        "ready_body": "Hemos terminado <strong>{title}</strong>: tienes {clips} listos para ver y descargar.",
        "ready_text": "Hemos terminado «{title}»: tienes {clips} listos.",
        "ready_keep": "Estarán disponibles durante {days} días.",
        "ready_button": "Ver mis clips",
        "open": "Ver y descargar",
        "clip_one": "1 clip",
        "clip_many": "{n} clips",
        "failed_title": "No hemos podido procesar tu vídeo",
        "failed_subject": "No hemos podido procesar «{title}»",
        "failed_body": "No hemos podido procesar <strong>{title}</strong>.",
        "failed_text": "No hemos podido procesar «{title}».",
        "refund": "Los minutos de este vídeo se han devuelto a tu cuenta.",
        "retry": "Probar de nuevo",
    },
    "en": {
        "footer": "You're receiving this email because you uploaded a video to Clipaso.",
        "ready_title": "Your clips are ready",
        "ready_subject": "Your clips from “{title}” are ready",
        "ready_body": "We've finished <strong>{title}</strong>: you have {clips} ready to watch and download.",
        "ready_text": "We've finished “{title}”: you have {clips} ready.",
        "ready_keep": "They'll be available for {days} days.",
        "ready_button": "See my clips",
        "open": "Watch and download",
        "clip_one": "1 clip",
        "clip_many": "{n} clips",
        "failed_title": "We couldn't process your video",
        "failed_subject": "We couldn't process “{title}”",
        "failed_body": "We couldn't process <strong>{title}</strong>.",
        "failed_text": "We couldn't process “{title}”.",
        "refund": "The minutes for this video have been returned to your account.",
        "retry": "Try again",
    },
}


def _t(lang: str) -> dict[str, str]:
    return TEXTS.get(lang, TEXTS["es"])


def _layout(title: str, body: str, button: tuple[str, str] | None, lang: str) -> str:
    cta = ""
    if button:
        label, url = button
        cta = (f'<p style="margin:28px 0"><a href="{escape(url)}" style="background:#b6e34a;color:#1f2d0c;'
               f'padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:600">{escape(label)}</a></p>')
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;padding:24px;'
        'color:#1a1a1a;line-height:1.5">'
        '<p style="font-weight:700;font-size:18px;margin:0 0 20px">Clip<span style="color:#4d7c0f">aso</span></p>'
        f'<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>{body}{cta}'
        f'<p style="color:#888;font-size:12px;margin-top:32px">{escape(_t(lang)["footer"])}</p></div>'
    )


def clips_ready(to: str, title: str, clip_count: int, retention_days: int, project_url: str,
                lang: str = "es") -> Email:
    tx = _t(lang)
    clips = tx["clip_one"] if clip_count == 1 else tx["clip_many"].format(n=clip_count)
    keep = tx["ready_keep"].format(days=retention_days)
    body = f"<p>{tx['ready_body'].format(title=escape(title), clips=clips)}</p><p>{keep}</p>"
    return Email(
        to=to,
        subject=tx["ready_subject"].format(title=title),
        html=_layout(tx["ready_title"], body, (tx["ready_button"], project_url), lang),
        text=f"{tx['ready_text'].format(title=title, clips=clips)}\n{tx['open']}: {project_url}\n{keep}",
    )


def processing_failed(to: str, title: str, error_code: str, new_project_url: str, lang: str = "es") -> Email:
    tx = _t(lang)
    reason = user_message(error_code, lang) or ""
    body = (f"<p>{tx['failed_body'].format(title=escape(title))}</p><p>{escape(reason)}</p>"
            f"<p>{tx['refund']}</p>")
    return Email(
        to=to,
        subject=tx["failed_subject"].format(title=title),
        html=_layout(tx["failed_title"], body, (tx["retry"], new_project_url), lang),
        text=f"{tx['failed_text'].format(title=title)} {reason}\n{tx['refund']}\n{tx['retry']}: {new_project_url}",
    )


def deliver(notifier: Notifier, email: Email) -> bool:
    try:
        notifier.send(email)
        return True
    except Exception as exc:
        log.warning("email.failed", error=str(exc)[:300])
        return False
