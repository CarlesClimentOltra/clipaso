"""Formulario de contacto: guarda el mensaje, avisa al buzón de soporte y acusa recibo."""

from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from clipaso.infra.config import Settings
from clipaso.interfaces.api.app import create_app
from clipaso.saas import support


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, email):
        self.sent.append(email)


@pytest.fixture
def setup(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None,
                        admin_emails=["yo@example.com"])
    with TestClient(create_app(settings)) as c:
        notifier = FakeNotifier()
        c.app.state.notifier = notifier
        yield c, notifier


def png_data_url() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (180, 220, 80)).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_anonymous_message_reaches_support_and_gets_ack(setup):
    client, notifier = setup
    r = client.post("/contact", json={"kind": "question", "message": "¿Funciona con vídeos de Zoom?\nGracias",
                                      "email": "Visitante@Example.com", "context": {"page": "/precios"}})
    assert r.status_code == 204
    to_support, ack = notifier.sent
    assert to_support.to == "hola@clipaso.com" and to_support.reply_to == "visitante@example.com"
    assert to_support.subject == "[Duda] ¿Funciona con vídeos de Zoom?" and "sin cuenta" in to_support.html
    assert ack.to == "visitante@example.com" and "Hemos recibido tu mensaje" in ack.subject


def test_logged_in_uses_account_email_and_attaches_screenshot(setup):
    client, notifier = setup
    headers = {"Authorization": "Bearer dev:ana@example.com"}
    client.get("/me", headers=headers)
    r = client.post("/contact", headers=headers, json={
        "kind": "bug", "message": "El editor no guarda", "email": "otro@example.com",
        "context": {"page": "/projects/abc", "project": "abc", "secreto": "no se guarda"},
        "attachment": png_data_url(),
    })
    assert r.status_code == 204
    to_support = notifier.sent[0]
    assert to_support.reply_to == "ana@example.com" and to_support.attachments[0][0] == "captura.jpg"
    assert "secreto" not in to_support.html and "plan" in to_support.html

    yo = {"Authorization": "Bearer dev:yo@example.com"}
    msgs = client.get("/admin/messages", headers=yo).json()
    assert msgs[0]["kind"] == "bug" and msgs[0]["has_account"] and msgs[0]["attachment_url"]
    assert client.patch(f"/admin/messages/{msgs[0]['id']}", json={"status": "resolved"}, headers=yo).status_code == 204
    assert client.get("/admin/messages", headers=yo).json()[0]["status"] == "resolved"
    assert client.get("/admin/messages", headers=headers).status_code == 404  # solo la cuenta de desarrollo


def test_validation_honeypot_and_daily_limit(setup, monkeypatch):
    client, notifier = setup
    bad = client.post("/contact", json={"kind": "idea", "message": "Hola", "email": "no-es-un-email"})
    assert bad.json()["error"]["code"] == "validation_error"
    bot = client.post("/contact", json={"kind": "idea", "message": "spam", "email": "a@b.com", "website": "x.com"})
    assert bot.status_code == 204 and notifier.sent == []  # el bot cree que ha funcionado
    bad_image = client.post("/contact", json={"kind": "bug", "message": "x", "email": "a@b.com",
                                              "attachment": "data:image/png;base64,bm8gZXMgdW5hIGltYWdlbg=="})
    assert bad_image.json()["error"]["code"] == "validation_error"

    monkeypatch.setattr(support, "DAILY_LIMIT", 2)
    for _ in range(2):
        assert client.post("/contact", json={"kind": "idea", "message": "Idea", "email": "a@b.com"}).status_code == 204
    r = client.post("/contact", json={"kind": "idea", "message": "Idea", "email": "otra@b.com"})
    assert r.status_code == 429  # misma conexión
