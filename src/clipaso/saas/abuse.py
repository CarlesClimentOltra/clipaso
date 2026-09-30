"""Protección contra abusos del plan gratis y de la API.

- Correos temporales: no se admiten para crear cuenta.
- Cuentas por conexión: como mucho `accounts_per_ip` cuentas gratis nuevas por IP cada
  `accounts_window_days` días. La IP nunca se guarda en claro, solo su huella HMAC.
- Límite de peticiones por minuto (por sesión y por IP), en memoria de cada máquina de la API.
- Mismo vídeo en varias cuentas gratis: se marca en el panel de costes (no se bloquea).
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clipaso.infra.config import AbuseSettings
from clipaso.saas.errors import AppError
from clipaso.saas.models import User
from clipaso.saas.plans import DEFAULT_PLAN

# Proveedores de correo temporal más usados (se admite también cualquier subdominio suyo).
_DISPOSABLE = """
10minutemail.com 10minutemail.net 10minutemail.co.uk 20minutemail.com 33mail.com
anonaddy.me burnermail.io byom.de dispostable.com discard.email disposablemail.com
dropmail.me email-fake.com emailfake.com emailondeck.com emailtemp.org fakeinbox.com
fakemail.net fakemailgenerator.com getairmail.com getnada.com guerrillamail.biz
guerrillamail.com guerrillamail.de guerrillamail.info guerrillamail.net guerrillamail.org
guerrillamailblock.com harakirimail.com inboxkitten.com incognitomail.org mail-temp.com
mail.tm mail7.io mailcatch.com maildrop.cc mailinator.com mailinator.net mailinator2.com
mailnesia.com mailpoof.com mailsac.com mailtemp.info meltmail.com mintemail.com moakt.com
mohmal.com mytemp.email mytrashmail.com nada.email nwytg.net oneoff.email pokemail.net
sharklasers.com spam4.me spambog.com spamgourmet.com spamex.com temp-mail.io temp-mail.org
tempail.com tempemail.co tempinbox.com tempmail.dev tempmail.net tempmail.plus tempmailo.com
tempr.email throwawaymail.com tmail.ws tmpmail.net tmpmail.org trash-mail.com trashmail.com
trashmail.de trashmail.io trashmail.net yopmail.com yopmail.fr yopmail.net emlhub.com
emltmp.com cuvox.de dayrep.com einrot.com fleckens.hu gustr.com jourrapide.com rhyta.com
superrito.com teleworm.us armyspy.com grr.la guerrillamail.email mailbox.in.ua mailforspam.com
spamfree24.org wegwerfmail.de wegwerfmail.net emailnax.com linshiyouxiang.net 1secmail.com
1secmail.net 1secmail.org esiix.com wwjmp.com xojxe.com yoggm.com kzccv.com qiott.com
tempmailaddress.com fakermail.com minuteinbox.com luxusmail.org inboxbear.com mailnull.com
"""
DISPOSABLE_DOMAINS = frozenset(_DISPOSABLE.split())


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""


def is_disposable(email: str, extra: list[str] = ()) -> bool:
    domain = email_domain(email)
    blocked = DISPOSABLE_DOMAINS | {d.strip().lower() for d in extra}
    return any(domain == d or domain.endswith("." + d) for d in blocked)


def client_ip(headers, fallback: str | None) -> str:
    """IP real del cliente. En Fly la pone su proxy en `Fly-Client-IP` (el cliente no puede falsearla)."""
    return (headers.get("fly-client-ip") or fallback or "").strip()


def ip_fingerprint(ip: str, secret: str) -> str | None:
    if not ip:
        return None
    return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def check_signup(
    session: Session, email: str, ip_hash: str | None, settings: AbuseSettings, now: datetime,
) -> None:
    """Antes de crear una cuenta: nada de correos temporales ni demasiadas cuentas gratis desde la misma red."""
    if is_disposable(email, settings.blocked_email_domains):
        raise AppError("email_disposable", 403)
    if ip_hash is None or settings.accounts_per_ip <= 0:
        return
    recent = session.scalar(
        select(func.count()).select_from(User).where(
            User.signup_ip == ip_hash, User.plan_code == DEFAULT_PLAN,
            User.created_at >= now - timedelta(days=settings.accounts_window_days),
        )
    ) or 0
    if recent >= settings.accounts_per_ip:
        raise AppError("too_many_accounts", 403)


class RateLimiter:
    """Ventana deslizante de 60 s por clave (en memoria; basta para frenar ráfagas y scripts)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if now - self._last_sweep > 300:  # olvida las claves inactivas
                self._hits = {k: q for k, q in self._hits.items() if q and now - q[-1] < 60}
                self._last_sweep = now
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True
