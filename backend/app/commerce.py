"""Durable guest-order preparation for Toss test payments only.

This module deliberately cannot enable live sales or grant report access. Test
payment receipts remain distinct from fulfillment, which is not configured yet.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import HTTPException

PRODUCT_ID = "premium-report"
PRODUCT_NAME = "여울 프리미엄 사주 리포트"
PRODUCT_PRICE_KRW = 7900  # Final launch price per report; live sales remain disabled.
TEST_AMOUNT = PRODUCT_PRICE_KRW  # Sandbox orders use the announced launch price.
ORDER_LIFETIME_SECONDS = 1800


class CommerceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


@dataclass(frozen=True)
class CommerceSettings:
    sandbox_enabled: bool
    client_key: str
    secret_key: str
    database_path: str


def get_commerce_settings() -> CommerceSettings:
    client_key = os.getenv("TOSS_CLIENT_KEY", "").strip()
    secret_key = os.getenv("TOSS_SECRET_KEY", "").strip()
    database_path = os.getenv("COMMERCE_DB_PATH", "").strip()
    sandbox_enabled = (
        os.getenv("TOSS_TEST_CHECKOUT", "").lower() == "true"
        and os.getenv("APP_ENV", "development").lower() in {"development", "test"}
        and client_key.startswith("test_ck_")
        and secret_key.startswith("test_sk_")
        and bool(database_path)
        and Path(database_path).is_absolute()
        and Path(database_path).parent.is_dir()
    )
    return CommerceSettings(sandbox_enabled, client_key, secret_key, database_path)


def public_config() -> dict[str, Any]:
    settings = get_commerce_settings()
    return {
        "enabled": False,
        "status": "preparing",
        "message": "프리미엄 리포트를 준비하고 있습니다. 현재는 결제가 진행되지 않습니다.",
        "product": {"id": PRODUCT_ID, "name": PRODUCT_NAME, "price": PRODUCT_PRICE_KRW, "currency": "KRW"},
        "methods": [
            {"id": "tosspay", "name": "토스페이", "enabled": False},
            {"id": "naverpay", "name": "네이버페이", "enabled": False},
        ],
        "sandbox_enabled": settings.sandbox_enabled,
        "fulfillment_enabled": False,
        "development_readings_enabled": development_readings_enabled(),
        "setup_required": [
            "운영 도메인과 사업자·판매 약관 설정",
            "PG 계약 및 간편결제 수단 심사",
            "결제·취소·환불 운영 검증",
            "유료 리포트 생성·PDF 저장·전달 및 실패 복구 구현",
        ],
    }


def development_readings_enabled() -> bool:
    return (
        os.getenv("APP_ENV", "development").lower() in {"development", "test"}
        and os.getenv("ALLOW_FREE_DEVELOPMENT_READINGS", "").lower() == "true"
    )


def assert_development_readings_enabled() -> None:
    """Existing free AI generation is an explicit local preview, never a paywall bypass."""
    if not development_readings_enabled():
        raise HTTPException(503, {"code": "PREMIUM_PREPARING", "message": "프리미엄 풀이를 준비하고 있습니다. 무료 원국을 먼저 확인해주세요."})


def require_sandbox() -> CommerceSettings:
    settings = get_commerce_settings()
    if not settings.sandbox_enabled:
        raise CommerceError(503, "CHECKOUT_NOT_AVAILABLE", "결제 서비스 준비 중입니다.")
    return settings


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class OrderStore:
    """Small durable sandbox ledger; no birth details, email, or phone storage."""

    def __init__(self, path: str):
        self.path = path
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS commerce_orders (
                order_id TEXT PRIMARY KEY, token_digest TEXT NOT NULL,
                product_id TEXT NOT NULL, amount INTEGER NOT NULL,
                status TEXT NOT NULL, payment_key TEXT UNIQUE,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )""")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def create(self) -> tuple[dict[str, Any], str]:
        now, token = int(time.time()), secrets.token_urlsafe(32)
        order_id = "yeoul_test_" + uuid4().hex
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            total = db.execute("SELECT COUNT(*) FROM commerce_orders").fetchone()[0]
            recent = db.execute("SELECT COUNT(*) FROM commerce_orders WHERE created_at > ?", (now - 3600,)).fetchone()[0]
            if total >= 2000 or recent >= 100:
                raise CommerceError(429, "ORDER_LIMIT", "테스트 주문 한도에 도달했습니다.")
            db.execute(
                "INSERT INTO commerce_orders VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                (order_id, digest(token), PRODUCT_ID, TEST_AMOUNT, "pending", now, now, now + ORDER_LIFETIME_SECONDS),
            )
        return self.get(order_id), token

    def get(self, order_id: str) -> dict[str, Any]:
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM commerce_orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise CommerceError(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
        return dict(row)

    def authorize(self, order_id: str, token: str) -> dict[str, Any]:
        order = self.get(order_id)
        if not token or not secrets.compare_digest(order["token_digest"], digest(token)):
            raise CommerceError(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
        return order

    def bind_payment(self, order_id: str, payment_key: str, amount: int) -> dict[str, Any]:
        """Bind one immutable key before I/O so retries use the same identity."""
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM commerce_orders WHERE order_id = ?", (order_id,)).fetchone()
            if row is None:
                raise CommerceError(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
            order = dict(row)
            if amount != order["amount"]:
                raise CommerceError(400, "AMOUNT_MISMATCH", "주문 금액이 일치하지 않습니다.")
            if order["payment_key"] and order["payment_key"] != payment_key:
                raise CommerceError(409, "PAYMENT_CONFLICT", "다른 결제 정보가 연결된 주문입니다.")
            if not order["payment_key"] and order["expires_at"] <= time.time():
                raise CommerceError(410, "ORDER_EXPIRED", "만료된 테스트 주문입니다.")
            try:
                db.execute("UPDATE commerce_orders SET payment_key = ? WHERE order_id = ?", (payment_key, order_id))
            except sqlite3.IntegrityError:
                raise CommerceError(409, "PAYMENT_CONFLICT", "이미 사용된 결제 정보입니다.") from None
        return self.get(order_id)

    def apply_verified_payment(self, order_id: str, payment: dict[str, Any]) -> dict[str, Any]:
        order = self.get(order_id)
        validate_payment(order, payment)
        provider_status = payment.get("status")
        mapped = {"DONE": "test_paid", "CANCELED": "canceled", "PARTIAL_CANCELED": "canceled", "ABORTED": "failed", "EXPIRED": "expired"}
        state = mapped.get(provider_status)
        if state:
            # A delayed DONE response cannot revive a locally recorded refund.
            with closing(self.connect()) as db, db:
                db.execute(
                    "UPDATE commerce_orders SET status = ?, updated_at = ? WHERE order_id = ? AND status != 'canceled'",
                    (state, int(time.time()), order_id),
                )
        return self.get(order_id)


def order_view(order: dict[str, Any]) -> dict[str, Any]:
    state = order["status"]
    if state == "pending" and order["expires_at"] <= time.time():
        state = "expired"
    return {
        "order_id": order["order_id"], "product_id": order["product_id"],
        "order_name": PRODUCT_NAME + " (테스트)", "amount": order["amount"],
        "currency": "KRW", "status": state, "test_mode": True,
        "expires_at": order["expires_at"], "fulfillment_status": "not_configured",
        "report_access": False,
    }


def validate_payment(order: dict[str, Any], payment: dict[str, Any]) -> None:
    if (
        payment.get("orderId") != order["order_id"]
        or payment.get("paymentKey") != order["payment_key"]
        or payment.get("currency") != "KRW"
        or type(payment.get("totalAmount")) is not int
        or payment.get("totalAmount") != order["amount"]
        or (payment.get("status") == "DONE" and payment.get("balanceAmount") != order["amount"])
    ):
        raise CommerceError(502, "PAYMENT_VERIFICATION_FAILED", "결제 정보 검증에 실패했습니다.")


class TossTestGateway:
    def __init__(self, settings: CommerceSettings):
        # Defense in depth: production keys can never reach the remote client.
        if not settings.sandbox_enabled or not settings.secret_key.startswith("test_sk_"):
            raise CommerceError(503, "CHECKOUT_NOT_AVAILABLE", "테스트 결제 설정이 필요합니다.")
        self.secret_key = settings.secret_key

    async def request(self, method: str, path: str, **kwargs) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(
                base_url="https://api.tosspayments.com", timeout=15,
                auth=httpx.BasicAuth(self.secret_key, ""), follow_redirects=False,
            ) as client:
                response = await client.request(method, path, **kwargs)
            if method == "GET" and response.status_code == 404:
                return None
            if response.status_code >= 400:
                raise CommerceError(502, "PAYMENT_PROVIDER_ERROR", "결제사 응답을 확인하지 못했습니다. 같은 주문으로 다시 확인해주세요.")
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Invalid payment response")
            return body
        except (httpx.HTTPError, ValueError):
            raise CommerceError(502, "PAYMENT_PROVIDER_UNAVAILABLE", "결제 상태 확인이 지연되고 있습니다. 같은 주문으로 다시 확인해주세요.") from None

    async def lookup(self, payment_key: str) -> dict[str, Any] | None:
        return await self.request("GET", "/v1/payments/" + quote(payment_key, safe=""))

    async def confirm(self, order: dict[str, Any]) -> dict[str, Any]:
        result = await self.request(
            "POST", "/v1/payments/confirm",
            headers={"Idempotency-Key": order["order_id"]},
            json={"paymentKey": order["payment_key"], "orderId": order["order_id"], "amount": order["amount"]},
        )
        assert result is not None
        return result


async def confirm_order(store: OrderStore, gateway: TossTestGateway, order_id: str, payment_key: str, amount: int) -> dict[str, Any]:
    order = store.bind_payment(order_id, payment_key, amount)
    # Query before retrying an ambiguous approval; a timeout is never failure proof.
    payment = await gateway.lookup(payment_key)
    if payment is not None:
        validate_payment(order, payment)
    if payment is None or payment.get("status") in {"READY", "IN_PROGRESS"}:
        if order["status"] != "pending" or order["expires_at"] <= time.time():
            raise CommerceError(409, "ORDER_NOT_CONFIRMABLE", "승인 가능한 테스트 주문이 아닙니다.")
        approved = await gateway.confirm(order)
        validate_payment(order, approved)
        payment = await gateway.lookup(payment_key)
    if payment is None:
        raise CommerceError(502, "PAYMENT_NOT_VERIFIED", "결제 상태를 다시 확인해주세요.")
    result = store.apply_verified_payment(order_id, payment)
    if result["status"] != "test_paid":
        raise CommerceError(409, "PAYMENT_NOT_COMPLETED", "완료된 테스트 결제가 아닙니다.")
    return order_view(result)
