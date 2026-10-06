"""Public readiness and explicitly enabled test-only guest checkout routes."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .commerce import (
    CommerceError, OrderStore, TossTestGateway, confirm_order, order_view,
    public_config, require_sandbox,
)

router = APIRouter(prefix="/api/v2/commerce", tags=["commerce preparation"])


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: Literal["premium-report"]


class ConfirmOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_key: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    amount: StrictInt = Field(gt=0)


class WebhookData(BaseModel):
    orderId: str = Field(min_length=6, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    paymentKey: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")


class PaymentWebhook(BaseModel):
    eventType: Literal["PAYMENT_STATUS_CHANGED"]
    data: WebhookData


def fail(error: CommerceError):
    raise HTTPException(error.status, {"code": error.code, "message": error.message}) from None


def bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else ""


@router.get("/config")
def commerce_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return public_config()


@router.post("/orders", status_code=201)
def create_order(payload: CreateOrder, response: Response):
    try:
        settings = require_sandbox()
        order, token = OrderStore(settings.database_path).create()
        response.headers["Cache-Control"] = "no-store"
        return {**order_view(order), "access_token": token, "client_key": settings.client_key}
    except CommerceError as error:
        fail(error)


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request, response: Response):
    try:
        settings = require_sandbox()
        order = OrderStore(settings.database_path).authorize(order_id, bearer(request))
        response.headers["Cache-Control"] = "no-store"
        return order_view(order)
    except CommerceError as error:
        fail(error)


@router.post("/orders/{order_id}/confirm")
async def confirm(order_id: str, payload: ConfirmOrder, request: Request, response: Response):
    try:
        settings = require_sandbox()
        store = OrderStore(settings.database_path)
        store.authorize(order_id, bearer(request))
        result = await confirm_order(store, TossTestGateway(settings), order_id, payload.payment_key, payload.amount)
        response.headers["Cache-Control"] = "no-store"
        return result
    except CommerceError as error:
        fail(error)


@router.post("/webhooks/toss")
async def toss_webhook(payload: PaymentWebhook):
    """Untrusted notification triggers a server query; its status is never used."""
    try:
        settings = require_sandbox()
        store = OrderStore(settings.database_path)
        try:
            order = store.get(payload.data.orderId)
        except CommerceError as error:
            if error.status == 404:
                return {"received": True, "updated": False}
            raise
        if order["payment_key"] != payload.data.paymentKey:
            return {"received": True, "updated": False}
        payment = await TossTestGateway(settings).lookup(order["payment_key"])
        if payment is None:
            raise CommerceError(502, "PAYMENT_NOT_VERIFIED", "결제 상태를 다시 확인해주세요.")
        store.apply_verified_payment(order["order_id"], payment)
        return {"received": True, "updated": True}
    except CommerceError as error:
        fail(error)
