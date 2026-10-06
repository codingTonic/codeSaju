"""Test-only commerce: no real payment requests, private keys or customer data."""
import asyncio
from pathlib import Path
import sys

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import commerce, commerce_routes


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TOSS_TEST_CHECKOUT", "true")
    monkeypatch.setenv("TOSS_CLIENT_KEY", "test_ck_fixture")
    monkeypatch.setenv("TOSS_SECRET_KEY", "test_sk_fixture")
    monkeypatch.setenv("COMMERCE_DB_PATH", str(tmp_path / "commerce.sqlite3"))
    app = FastAPI()
    app.include_router(commerce_routes.router)
    return TestClient(app)


def order(client):
    response = client.post("/api/v2/commerce/orders", json={"product_id": "premium-report"})
    assert response.status_code == 201
    return response.json()


def auth(created):
    return {"Authorization": "Bearer " + created["access_token"]}


def payment(created, **changes):
    return {"orderId": created["order_id"], "paymentKey": "test_payment_1", "totalAmount": commerce.TEST_AMOUNT,
            "balanceAmount": commerce.TEST_AMOUNT, "currency": "KRW", "status": "DONE", **changes}


def confirm(client, created, **changes):
    return client.post(f"/api/v2/commerce/orders/{created['order_id']}/confirm", headers=auth(created),
                       json={"payment_key": "test_payment_1", "amount": created["amount"], **changes})


def fake_lookup(monkeypatch, result):
    async def lookup(self, key):
        return result
    monkeypatch.setattr(commerce.TossTestGateway, "lookup", lookup)


def test_public_config_never_enables_sales_or_exposes_secrets(sandbox):
    response = sandbox.get("/api/v2/commerce/config")
    assert response.json()["enabled"] is False
    assert response.json()["sandbox_enabled"] is True
    assert response.json()["product"]["price"] == 7900
    assert response.json()["fulfillment_enabled"] is False
    assert "test_sk_" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("name,value", [
    ("TOSS_TEST_CHECKOUT", "false"), ("APP_ENV", "production"),
    ("TOSS_SECRET_KEY", "live_sk_fixture"), ("TOSS_CLIENT_KEY", "live_ck_fixture"),
    ("COMMERCE_DB_PATH", "relative.sqlite3"),
])
def test_disabled_or_live_configuration_cannot_create_orders(sandbox, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    response = sandbox.post("/api/v2/commerce/orders", json={"product_id": "premium-report"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CHECKOUT_NOT_AVAILABLE"


def test_order_amount_is_server_owned_and_private_token_is_hashed(sandbox):
    bad = sandbox.post("/api/v2/commerce/orders", json={"product_id": "premium-report", "amount": 1})
    assert bad.status_code == 422
    created = order(sandbox)
    store = commerce.OrderStore(commerce.require_sandbox().database_path)
    saved = store.get(created["order_id"])
    assert saved["amount"] == created["amount"] == commerce.PRODUCT_PRICE_KRW == 7900
    assert saved["token_digest"] != created["access_token"]
    assert saved["token_digest"] == commerce.digest(created["access_token"])
    assert created["report_access"] is False


def test_order_authorization_and_persistence(sandbox):
    created = order(sandbox)
    path = f"/api/v2/commerce/orders/{created['order_id']}"
    assert sandbox.get(path).status_code == 404
    assert sandbox.get(path + "?access_token=" + created["access_token"]).status_code == 404
    response = sandbox.get(path, headers=auth(created))
    assert response.status_code == 200
    assert "access_token" not in response.json()
    assert "payment_key" not in response.json()
    assert commerce.OrderStore(commerce.require_sandbox().database_path).authorize(created["order_id"], created["access_token"])


def test_amount_mismatch_does_not_call_gateway(sandbox, monkeypatch):
    created = order(sandbox)
    async def unexpected(*args):
        pytest.fail("Tampered amount must not call gateway")
    monkeypatch.setattr(commerce.TossTestGateway, "lookup", unexpected)
    assert confirm(sandbox, created, amount=1).status_code == 400
    assert confirm(sandbox, created, amount=True).status_code == 422


def test_authorization_needed_before_approval(sandbox):
    created = order(sandbox)
    response = sandbox.post(f"/api/v2/commerce/orders/{created['order_id']}/confirm",
                            json={"payment_key": "test_payment_1", "amount": commerce.TEST_AMOUNT})
    assert response.status_code == 404


def test_confirmation_rechecks_provider_and_idempotent_retries(sandbox, monkeypatch):
    created = order(sandbox)
    state = {"lookups": 0, "approvals": 0}
    async def lookup(self, key):
        state["lookups"] += 1
        return payment(created) if state["approvals"] else None
    async def approve(self, saved):
        state["approvals"] += 1
        return payment(created)
    monkeypatch.setattr(commerce.TossTestGateway, "lookup", lookup)
    monkeypatch.setattr(commerce.TossTestGateway, "confirm", approve)
    for _ in range(2):
        response = confirm(sandbox, created)
        assert response.status_code == 200
        assert response.json()["status"] == "test_paid"
        assert response.json()["report_access"] is False
        assert response.json()["fulfillment_status"] == "not_configured"
    assert state == {"lookups": 3, "approvals": 1}


@pytest.mark.parametrize("changes", [{"totalAmount": 1}, {"orderId": "another_order"}, {"currency": "USD"},
                                     {"paymentKey": "another_key"}, {"balanceAmount": 1}])
def test_provider_mismatch_never_marks_paid(sandbox, monkeypatch, changes):
    created = order(sandbox)
    fake_lookup(monkeypatch, payment(created, **changes))
    assert confirm(sandbox, created).status_code == 502
    assert commerce.OrderStore(commerce.require_sandbox().database_path).get(created["order_id"])["status"] == "pending"


def test_expired_order_cannot_start_approval(sandbox, monkeypatch):
    created = order(sandbox)
    monkeypatch.setattr(commerce.time, "time", lambda: created["expires_at"] + 1)
    assert confirm(sandbox, created).status_code == 410


def test_payment_key_is_unique_and_cannot_change(sandbox, monkeypatch):
    first = order(sandbox)
    second = order(sandbox)
    fake_lookup(monkeypatch, payment(first))
    assert confirm(sandbox, first).status_code == 200
    assert confirm(sandbox, first, payment_key="different_key").status_code == 409
    assert confirm(sandbox, second).status_code == 409


def test_timeout_recovery_does_not_repeat_completed_approval(sandbox, monkeypatch):
    created = order(sandbox)
    fake_lookup(monkeypatch, None)
    async def ambiguous(self, saved):
        raise commerce.CommerceError(502, "PAYMENT_PROVIDER_UNAVAILABLE", "retry")
    monkeypatch.setattr(commerce.TossTestGateway, "confirm", ambiguous)
    assert confirm(sandbox, created).status_code == 502
    fake_lookup(monkeypatch, payment(created))
    assert confirm(sandbox, created).json()["status"] == "test_paid"


def test_webhook_uses_gateway_status_not_claimed_status(sandbox, monkeypatch):
    created = order(sandbox)
    store = commerce.OrderStore(commerce.require_sandbox().database_path)
    store.bind_payment(created["order_id"], "test_payment_1", commerce.TEST_AMOUNT)
    fake_lookup(monkeypatch, payment(created, status="CANCELED", balanceAmount=0))
    body = {"eventType": "PAYMENT_STATUS_CHANGED", "data": payment(created)}
    for _ in range(2):
        assert sandbox.post("/api/v2/commerce/webhooks/toss", json=body).status_code == 200
    assert store.get(created["order_id"])["status"] == "canceled"
    fake_lookup(monkeypatch, payment(created))
    assert confirm(sandbox, created).status_code == 409
    assert store.get(created["order_id"])["status"] == "canceled"


def test_unbound_webhook_cannot_grant_payment(sandbox, monkeypatch):
    created = order(sandbox)
    async def unexpected(*args):
        pytest.fail("Unbound notification must not call gateway")
    monkeypatch.setattr(commerce.TossTestGateway, "lookup", unexpected)
    response = sandbox.post("/api/v2/commerce/webhooks/toss", json={"eventType": "PAYMENT_STATUS_CHANGED", "data": payment(created)})
    assert response.json() == {"received": True, "updated": False}


def test_gateway_uses_fixed_origin_basic_auth_and_stable_idempotency(sandbox, monkeypatch):
    settings = commerce.require_sandbox()
    store = commerce.OrderStore(settings.database_path)
    created, _ = store.create()
    saved = store.bind_payment(created["order_id"], "test_payment_1", commerce.TEST_AMOUNT)
    requests = []
    original_client = httpx.AsyncClient
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payment(created))
    monkeypatch.setattr(commerce.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    asyncio.run(commerce.TossTestGateway(settings).confirm(saved))
    assert str(requests[0].url) == "https://api.tosspayments.com/v1/payments/confirm"
    assert requests[0].headers["Idempotency-Key"] == created["order_id"]
    assert requests[0].headers["Authorization"].startswith("Basic ")


def test_development_readings_require_local_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_FREE_DEVELOPMENT_READINGS", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(HTTPException):
        commerce.assert_development_readings_enabled()
    monkeypatch.setenv("ALLOW_FREE_DEVELOPMENT_READINGS", "true")
    commerce.assert_development_readings_enabled()
    assert commerce.public_config()["development_readings_enabled"] is True
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(HTTPException):
        commerce.assert_development_readings_enabled()
