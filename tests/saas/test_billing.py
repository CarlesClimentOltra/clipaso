"""Cobros con Paddle: firma del webhook y el plan del usuario siguiendo a su suscripción."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from clipaso.infra.config import BillingSettings, Settings
from clipaso.interfaces.api.app import create_app
from clipaso.saas import billing

SECRET = "pdl_ntfset_test"
PRICES = {"pro_month": "pri_pro_m", "pro_year": "pri_pro_y", "ultra_month": "pri_ultra_m", "ultra_year": "pri_ultra_y"}
ANA = {"Authorization": "Bearer dev:ana@example.com"}


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None,
                        admin_emails=["yo@example.com"],
                        billing=BillingSettings(provider="paddle", paddle_webhook_secret=SECRET, paddle_api_key="k",
                                                paddle_client_token="test_tok", paddle_prices=PRICES))
    with TestClient(create_app(settings)) as c:
        yield c


def send(client, event_type: str, data: dict, occurred_at: str = "2026-10-02T10:00:00Z", secret: str = SECRET):
    body = json.dumps({"event_type": event_type, "occurred_at": occurred_at, "data": data}).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return client.post("/billing/paddle/webhook", content=body, headers={"Paddle-Signature": f"ts={ts};h1={sig}"})


def subscription(status="active", price="pri_pro_m", sub_id="sub_1", scheduled=None, user="dev|ana@example.com"):
    return {"id": sub_id, "customer_id": "ctm_1", "status": status, "custom_data": {"user_id": user},
            "items": [{"price": {"id": price}, "quantity": 1}], "next_billed_at": "2026-11-02T10:00:00Z",
            "scheduled_change": scheduled}


def me(client, headers=ANA):
    return client.get("/me", headers=headers).json()


def test_signature():
    body = b'{"a":1}'
    ts = "1700000000"
    good = hmac.new(b"s", b"1700000000:" + body, hashlib.sha256).hexdigest()
    assert billing.verify_signature(f"ts={ts};h1={good}", body, "s", now=1700000010)
    assert not billing.verify_signature(f"ts={ts};h1={good}", body + b" ", "s", now=1700000010)
    assert not billing.verify_signature(f"ts={ts};h1={good}", body, "s", now=1700009999)  # demasiado antigua
    assert not billing.verify_signature("", body, "s")


def test_webhook_rejects_bad_signature(client):
    me(client)
    assert send(client, "subscription.created", subscription(), secret="otro").status_code == 401
    assert me(client)["plan"]["code"] == "free"


def test_subscription_lifecycle(client):
    me(client)
    config = client.get("/billing/config").json()
    assert config["enabled"] and config["client_token"] == "test_tok" and config["prices"]["pro_year"] == "pri_pro_y"

    assert send(client, "subscription.created", subscription()).status_code == 200
    data = me(client)
    assert data["plan"]["code"] == "pro" and data["billing"]["interval"] == "month"
    assert data["billing"]["status"] == "active" and data["billing"]["cancels_at"] is None

    # Cambio a Ultra anual (evento posterior).
    send(client, "subscription.updated", subscription(price="pri_ultra_y"), occurred_at="2026-10-03T10:00:00Z")
    data = me(client)
    assert data["plan"]["code"] == "ultra" and data["billing"]["interval"] == "year"

    # Un evento atrasado no deshace el cambio.
    send(client, "subscription.updated", subscription(price="pri_pro_m"), occurred_at="2026-10-02T12:00:00Z")
    assert me(client)["plan"]["code"] == "ultra"

    # Cancelada a final de periodo: conserva el plan hasta entonces.
    cancel = {"action": "cancel", "effective_at": "2026-11-03T10:00:00Z"}
    send(client, "subscription.updated", subscription(price="pri_ultra_y", scheduled=cancel),
         occurred_at="2026-10-04T10:00:00Z")
    data = me(client)
    assert data["plan"]["code"] == "ultra" and data["billing"]["cancels_at"].startswith("2026-11-03")

    # Termina: vuelve a Gratis.
    send(client, "subscription.canceled", subscription(status="canceled", price="pri_ultra_y"),
         occurred_at="2026-11-03T10:00:01Z")
    data = me(client)
    assert data["plan"]["code"] == "free" and data["billing"]["status"] == "canceled"


def test_old_subscription_ending_keeps_new_one(client):
    me(client)
    send(client, "subscription.created", subscription(sub_id="sub_new"))
    send(client, "subscription.canceled", subscription(status="canceled", sub_id="sub_old"),
         occurred_at="2026-10-05T10:00:00Z")
    assert me(client)["plan"]["code"] == "pro"


def test_developer_account_keeps_its_plan(client):
    yo = {"Authorization": "Bearer dev:yo@example.com"}
    me(client, yo)
    send(client, "subscription.created", subscription(user="dev|yo@example.com"))
    data = me(client, yo)
    assert data["plan"]["code"] == "dev" and data["billing"]["status"] == "active"


def test_change_plan_and_portal(client, monkeypatch):
    me(client)
    calls = []

    def fake_call(self, method, path, json=None):
        calls.append((method, path, json))
        if path.endswith("/portal-sessions"):
            return {"urls": {"general": {"overview": "https://portal.example/ctm_1"}}}
        return subscription(price=json["items"][0]["price_id"])

    monkeypatch.setattr(billing.Paddle, "_call", fake_call)
    r = client.post("/billing/change-plan", json={"plan": "ultra", "interval": "month"}, headers=ANA)
    assert r.json()["error"]["code"] == "validation_error"  # sin suscripción: se paga con Paddle.js

    send(client, "subscription.created", subscription())
    r = client.post("/billing/change-plan", json={"plan": "ultra", "interval": "month"}, headers=ANA)
    assert r.status_code == 204
    assert calls[-1][0] == "PATCH" and calls[-1][2]["items"][0]["price_id"] == "pri_ultra_m"
    assert me(client)["plan"]["code"] == "ultra"
    assert client.post("/billing/portal", headers=ANA).json()["url"] == "https://portal.example/ctm_1"


def test_deleting_account_cancels_subscription(client, monkeypatch):
    me(client)
    send(client, "subscription.created", subscription())
    calls = []
    monkeypatch.setattr(billing.Paddle, "_call", lambda self, method, path, json=None: calls.append(path) or {})
    monkeypatch.setattr("clipaso.interfaces.api.routers.account.delete_identity", lambda *a, **k: None)
    assert client.delete("/me", headers=ANA).status_code == 204
    assert calls == ["/subscriptions/sub_1/cancel"]
