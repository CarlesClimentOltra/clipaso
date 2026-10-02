"""Formulario de contacto: dudas, sugerencias, errores y pagos.

Cada mensaje se guarda (panel /admin) y se envía al buzón de soporte con el email de quien escribe como
«responder a», para contestar directamente desde el correo. Quien escribe recibe un acuse de recibo.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timedelta
from html import escape

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from clipaso.domain.ports import Storage
from clipaso.infra.config import NotificationSettings
from clipaso.infra.logging import get_logger
from clipaso.saas.errors import AppError
from clipaso.saas.models import ContactMessage, User
from clipaso.saas.notifications import Email, Notifier, _layout, deliver

log = get_logger(__name__)

KINDS = ("question", "idea", "bug", "billing", "other")
MAX_MESSAGE = 5000
MAX_ATTACHMENT_BYTES = 6 * 1024 * 1024
ATTACHMENT_MAX_SIDE = 1800
DAILY_LIMIT = 10  # mensajes por persona o conexión en 24 h (evita spam sin pedir captcha)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CONTEXT_KEYS = ("page", "project", "browser", "plan", "language", "screen")

KIND_LABELS = {
    "es": {"question": "Duda", "idea": "Sugerencia", "bug": "Error", "billing": "Pagos", "other": "Otro"},
    "en": {"question": "Question", "idea": "Suggestion", "bug": "Bug", "billing": "Billing", "other": "Other"},
}
ACK = {
    "es": ("Hemos recibido tu mensaje", "Hemos recibido tu mensaje",
           "Gracias por escribirnos. Lo leemos todo y te responderemos a este email en un máximo de 3 días "
           "laborables.", "Esto es lo que nos enviaste:", "Recibes este email porque escribiste a Clipaso."),
    "en": ("We've received your message", "We've received your message",
           "Thanks for writing to us. We read everything and will reply to this email within 3 working days.",
           "This is what you sent us:", "You're receiving this email because you contacted Clipaso."),
}


def decode_image(data_url: str) -> bytes:
    """Captura adjunta (data URL de una imagen) → JPEG reducido. Error si no es una imagen válida."""
    _, _, payload = data_url.partition(",")
    try:
        raw = base64.b64decode(payload or data_url, validate=False)
    except ValueError as exc:
        raise AppError("validation_error", key="bad_image") from exc
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise AppError("validation_error", key="contact_image_too_big")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise AppError("validation_error", key="bad_image") from exc
    img = img.convert("RGB")
    img.thumbnail((ATTACHMENT_MAX_SIDE, ATTACHMENT_MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def check_limit(session: Session, user: User | None, ip_hash: str | None, now: datetime) -> None:
    who = [ContactMessage.ip_hash == ip_hash] if ip_hash else []
    if user is not None:
        who.append(ContactMessage.user_id == user.id)
    if not who:
        return
    sent = session.scalar(select(func.count()).select_from(ContactMessage).where(
        or_(*who), ContactMessage.created_at >= now - timedelta(days=1))) or 0
    if sent >= DAILY_LIMIT:
        raise AppError("rate_limited", 429)


def create_message(
    session: Session, storage: Storage, notifier: Notifier, settings: NotificationSettings, *,
    user: User | None, email: str | None, kind: str, message: str, context: dict, attachment: str | None,
    ip_hash: str | None, lang: str, now: datetime,
) -> ContactMessage:
    sender = (user.email if user is not None else (email or "")).strip().lower()
    message = message.strip()
    if kind not in KINDS or not message or len(message) > MAX_MESSAGE:
        raise AppError("validation_error")
    if not EMAIL_RE.match(sender):
        raise AppError("validation_error", key="contact_email")
    check_limit(session, user, ip_hash, now)
    image = decode_image(attachment) if attachment else None
    clean_context = {k: str(context[k])[:300] for k in CONTEXT_KEYS if context.get(k)}
    if user is not None and user.plan:
        clean_context["plan"] = user.plan.code
    msg = ContactMessage(user_id=user.id if user else None, email=sender, kind=kind, message=message,
                         context=clean_context, ip_hash=ip_hash, created_at=now, status="new")
    session.add(msg)
    session.flush()
    if image:
        msg.attachment_key = f"support/{msg.id}.jpg"
        storage.put_bytes(msg.attachment_key, image, "image/jpeg")

    deliver(notifier, _to_support(msg, settings, image))
    deliver(notifier, _ack(msg, lang))
    log.info("contact.received", kind=kind, logged_in=user is not None, attachment=bool(image))
    return msg


def _to_support(msg: ContactMessage, settings: NotificationSettings, image: bytes | None) -> Email:
    label = KIND_LABELS["es"][msg.kind]
    rows = "".join(f"<li><strong>{escape(k)}:</strong> {escape(v)}</li>" for k, v in msg.context.items())
    body = (f'<p style="white-space:pre-wrap">{escape(msg.message)}</p>'
            f"<p><strong>De:</strong> {escape(msg.email)}"
            f"{' (cuenta registrada)' if msg.user_id else ' (sin cuenta)'}</p>"
            + (f"<ul>{rows}</ul>" if rows else "")
            + ("<p>Captura adjunta.</p>" if image else "")
            + "<p>Responde a este email para contestar directamente.</p>")
    first_line = msg.message.splitlines()[0][:60]
    return Email(to=settings.support_email, subject=f"[{label}] {first_line}", reply_to=msg.email,
                 html=_layout(f"{label} de {msg.email}", body, None, "es",
                              footer="Mensaje del formulario de contacto."),
                 text=f"{msg.message}\n\nDe: {msg.email}\n{msg.context}",
                 attachments=(("captura.jpg", image),) if image else (), tag="contact")


def _ack(msg: ContactMessage, lang: str) -> Email:
    lang = lang if lang in ACK else "es"
    subject, title, lead, quote_intro, footer = ACK[lang]
    body = (f"<p>{escape(lead)}</p><p>{escape(quote_intro)}</p>"
            f'<blockquote style="margin:0;padding:12px 16px;background:#f4f6ee;border-radius:12px;'
            f'white-space:pre-wrap">{escape(msg.message)}</blockquote>')
    return Email(to=msg.email, subject=subject, html=_layout(title, body, None, lang, footer=footer),
                 text=f"{lead}\n\n{msg.message}", tag="contact")
