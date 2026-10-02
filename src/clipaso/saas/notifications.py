"""Emails al usuario cuando su vídeo termina (clips listos o fallo con minutos devueltos).

Se envían con la API transaccional de Brevo (servidores en la UE). Un fallo al
enviar nunca afecta al procesamiento: se registra y se sigue.
"""

from __future__ import annotations

import base64
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
    reply_to: str | None = None
    attachments: tuple[tuple[str, bytes], ...] = ()  # (nombre, contenido)
    tag: str = "job-notification"


class Notifier(Protocol):
    def send(self, email: Email) -> None: ...


class NullNotifier:
    def send(self, email: Email) -> None:
        log.info("email.skipped", to_domain=email.to.rsplit("@", 1)[-1], subject=email.subject)


class BrevoNotifier:
    def __init__(self, api_key: str, sender_email: str, sender_name: str) -> None:
        self.api_key, self.sender_email, self.sender_name = api_key, sender_email, sender_name

    def send(self, email: Email) -> None:
        body = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": email.to}],
            "subject": email.subject,
            "htmlContent": email.html,
            "textContent": email.text,
            "tags": [email.tag],
        }
        if email.reply_to:
            body["replyTo"] = {"email": email.reply_to}
        if email.attachments:
            body["attachment"] = [{"name": name, "content": base64.b64encode(data).decode()}
                                  for name, data in email.attachments]
        r = httpx.post(BREVO_URL, headers={"api-key": self.api_key, "accept": "application/json"}, json=body,
                       timeout=30)
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
        # Modos en los que el resultado es el vídeo entero.
        "video_title": "Tu vídeo está listo",
        "video_subject": "Tu vídeo «{title}» está listo",
        "video_body": "Hemos terminado <strong>{title}</strong>: {what} está listo para ver y descargar.",
        "video_text": "Hemos terminado «{title}»: {what} está listo.",
        "video_keep": "Estará disponible durante {days} días.",
        "video_button": "Ver mi vídeo",
        "what_subtitle": "tu vídeo subtitulado",
        "what_clean": "tu vídeo sin silencios",
        "what_reframe": "tu vídeo en el nuevo formato",
        "what_trailer": "tu tráiler",
        "what_audiogram": "tu audiograma",
        "what_text": "el texto de tu vídeo (transcripción, resumen y más)",
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
        "video_title": "Your video is ready",
        "video_subject": "Your video “{title}” is ready",
        "video_body": "We've finished <strong>{title}</strong>: {what} is ready to watch and download.",
        "video_text": "We've finished “{title}”: {what} is ready.",
        "video_keep": "It'll be available for {days} days.",
        "video_button": "See my video",
        "what_subtitle": "your captioned video",
        "what_clean": "your video without silences",
        "what_reframe": "your video in its new format",
        "what_trailer": "your trailer",
        "what_audiogram": "your audiogram",
        "what_text": "your video's text (transcript, summary and more)",
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


def _layout(title: str, body: str, button: tuple[str, str] | None, lang: str, footer: str | None = None) -> str:
    """Mismo diseño que los emails de cuenta (deploy/supabase_emails.py): logo, tarjeta blanca y botón lima."""
    cta = ""
    if button:
        label, url = button
        cta = (f'<p style="margin:28px 0 0"><a href="{escape(url)}" style="display:inline-block;background:#b6e34a;'
               f'color:#1f2d0c;font-size:15px;font-weight:700;text-decoration:none;padding:14px 28px;'
               f'border-radius:999px">{escape(label)}</a></p>')
    return (
        '<div style="margin:0;padding:40px 16px;background:#f4f6ee;font-family:-apple-system,BlinkMacSystemFont,'
        "'Segoe UI',Roboto,Helvetica,Arial,sans-serif\">"
        '<div style="max-width:520px;margin:0 auto">'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 8px 20px"><tr>'
        '<td style="vertical-align:middle"><img src="https://clipaso.com/email-logo.png" width="32" height="32" '
        'alt="Clipaso" style="display:block;border:0;border-radius:9px"></td>'
        '<td style="padding-left:10px;font-size:19px;font-weight:700;color:#111">Clip'
        '<span style="color:#4d7c0f">aso</span></td></tr></table>'
        '<div style="background:#fff;border:1px solid #e6e9dc;border-radius:20px;overflow:hidden">'
        '<div style="height:6px;background:#b6e34a;font-size:0;line-height:0">&nbsp;</div>'
        '<div style="padding:40px;color:#404040;font-size:15px;line-height:1.6">'
        f'<h1 style="margin:0 0 12px;font-size:24px;line-height:1.25;color:#111">{escape(title)}</h1>{body}{cta}'
        '</div></div>'
        '<p style="text-align:center;color:#8a8f7c;font-size:12px;margin:20px 0 0">'
        f'{escape(footer or _t(lang)["footer"])}</p>'
        '</div></div>'
    )


def clips_ready(to: str, title: str, clip_count: int, retention_days: int, project_url: str,
                lang: str = "es", mode: str = "clips") -> Email:
    tx = _t(lang)
    if f"what_{mode}" in tx:  # el resultado es el vídeo entero (subtitulado o sin silencios)
        what = tx[f"what_{mode}"]
        keep = tx["video_keep"].format(days=retention_days)
        return Email(
            to=to,
            subject=tx["video_subject"].format(title=title),
            html=_layout(tx["video_title"], f"<p>{tx['video_body'].format(title=escape(title), what=what)}</p>"
                         f"<p>{keep}</p>", (tx["video_button"], project_url), lang),
            text=f"{tx['video_text'].format(title=title, what=what)}\n{tx['open']}: {project_url}\n{keep}",
        )
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
