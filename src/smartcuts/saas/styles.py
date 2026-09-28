"""Estilos de subtítulos del usuario: los de serie (que puede modificar) y los suyos propios.

Se guardan en `users.preferences`:
- `caption_styles`: lista de `{id, name, style}`. Si el id es de un estilo de serie, es la versión
  modificada por el usuario; si no, es un estilo propio (`u_…`).
- `default_style`: id del estilo que se usa por defecto en los proyectos nuevos.
"""

from __future__ import annotations

import secrets

from pydantic import BaseModel, Field

from smartcuts.saas.errors import AppError, NotFound
from smartcuts.saas.models import User
from smartcuts.saas.presets import DEFAULT_STYLE, PRESETS, PRESETS_BY_ID, CaptionStyle

MAX_CUSTOM_STYLES = 10
LEGACY_NAME = "Mi estilo"


class UserStyle(BaseModel):
    id: str
    name: str = Field(max_length=40)
    builtin: bool = Field(description="Estilo de serie (se puede modificar y restablecer, no borrar).")
    modified: bool = Field(False, description="Estilo de serie con cambios del usuario.")
    style: CaptionStyle


def _stored(user: User) -> list[dict]:
    _migrate_legacy(user)
    return list((user.preferences or {}).get("caption_styles", []))


def _save(user: User, stored: list[dict], default: str | None = None) -> None:
    prefs = {**(user.preferences or {}), "caption_styles": stored}
    if default is not None:
        prefs["default_style"] = default
    prefs.pop("caption_style", None)
    user.preferences = prefs


def _migrate_legacy(user: User) -> None:
    """Antes solo había un estilo por defecto suelto (`caption_style`): pasa a ser un estilo más."""
    prefs = user.preferences or {}
    legacy = prefs.get("caption_style")
    if not legacy or "default_style" in prefs:
        return
    style = CaptionStyle.model_validate(legacy)
    same = next((p.id for p in PRESETS if p.style == style), None)
    stored = list(prefs.get("caption_styles", []))
    if same is None:
        same = _new_id()
        stored.append({"id": same, "name": LEGACY_NAME, "style": style.model_dump()})
    user.preferences = {**{k: v for k, v in prefs.items() if k != "caption_style"},
                        "caption_styles": stored, "default_style": same}


def _new_id() -> str:
    return f"u_{secrets.token_hex(4)}"


def list_styles(user: User) -> list[UserStyle]:
    """Primero los de serie (con los cambios del usuario) y después los suyos, en orden de creación."""
    stored = {s["id"]: s for s in _stored(user)}
    out = []
    for p in PRESETS:
        own = stored.get(p.id)
        out.append(UserStyle(id=p.id, name=own["name"] if own else p.name, builtin=True, modified=own is not None,
                             style=CaptionStyle.model_validate(own["style"]) if own else p.style))
    out += [UserStyle(id=s["id"], name=s["name"], builtin=False, style=CaptionStyle.model_validate(s["style"]))
            for s in stored.values() if s["id"] not in PRESETS_BY_ID]
    return out


def default_style_id(user: User) -> str:
    _migrate_legacy(user)
    wanted = (user.preferences or {}).get("default_style")
    return wanted if wanted in {s.id for s in list_styles(user)} else PRESETS[0].id


def default_style(user: User) -> CaptionStyle:
    wanted = default_style_id(user)
    return next((s.style for s in list_styles(user) if s.id == wanted), DEFAULT_STYLE)


def create_style(user: User, name: str, style: CaptionStyle) -> UserStyle:
    stored = _stored(user)
    if sum(1 for s in stored if s["id"] not in PRESETS_BY_ID) >= MAX_CUSTOM_STYLES:
        raise AppError("validation_error", 409, key="style_limit", params={"max": str(MAX_CUSTOM_STYLES)})
    item = {"id": _new_id(), "name": _clean_name(name), "style": style.model_dump()}
    _save(user, [*stored, item])
    return UserStyle(id=item["id"], name=item["name"], builtin=False, style=style)


def update_style(user: User, style_id: str, name: str | None, style: CaptionStyle) -> UserStyle:
    stored = _stored(user)
    current = next((s for s in list_styles(user) if s.id == style_id), None)
    if current is None:
        raise NotFound()
    item = {"id": style_id, "name": _clean_name(name) if name else current.name, "style": style.model_dump()}
    others = [s for s in stored if s["id"] != style_id]
    if current.builtin:
        others.append(item)
        _save(user, others)
    else:  # conserva su sitio en la lista
        _save(user, [item if s["id"] == style_id else s for s in stored])
    return UserStyle(id=style_id, name=item["name"], builtin=current.builtin, modified=current.builtin,
                     style=style)


def delete_style(user: User, style_id: str) -> None:
    """Borra un estilo propio o restablece uno de serie a su versión original."""
    stored = _stored(user)
    if style_id not in PRESETS_BY_ID and not any(s["id"] == style_id for s in stored):
        raise NotFound()
    default = default_style_id(user)
    _save(user, [s for s in stored if s["id"] != style_id],
          default=PRESETS[0].id if default == style_id and style_id not in PRESETS_BY_ID else None)


def set_default(user: User, style_id: str) -> None:
    if style_id not in {s.id for s in list_styles(user)}:
        raise NotFound()
    _save(user, _stored(user), default=style_id)


def _clean_name(name: str) -> str:
    name = " ".join(name.split())[:40]
    if not name:
        raise AppError("validation_error", key="style_name")
    return name
