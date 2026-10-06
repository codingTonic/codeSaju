"""Bounded, single-worker admission control and transport safeguards."""
from __future__ import annotations

import asyncio
from collections import deque
import hashlib
import os
import time

from fastapi import HTTPException
from starlette.responses import JSONResponse


def positive_setting(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


MAX_BODY_BYTES = positive_setting("MAX_REQUEST_BODY_BYTES", 16384)
MAX_ACTIVE_TASKS = positive_setting("MAX_ACTIVE_TASKS", 3)
MAX_STORED_TASKS = positive_setting("MAX_STORED_TASKS", 200)
TASK_TIMEOUT_SECONDS = positive_setting("TASK_TIMEOUT_SECONDS", 600)
RATE_WINDOW_SECONDS = 600
RATE_REQUESTS = positive_setting("RATE_REQUESTS_PER_10_MINUTES", 5)
DAILY_REQUESTS = positive_setting("MAX_DAILY_ANALYSES", 100)
MAX_RATE_IDENTITIES = 4096


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AdmissionControl:
    """All mutations run synchronously on the application's event loop.

    Limits are process-local. Run one worker; replicas require shared quotas.
    Failed and cancelled generations still count against the cost allowance.
    """

    def __init__(self) -> None:
        self.by_client: dict[str, deque[float]] = {}
        self.daily: deque[float] = deque()
        self.active: set[str] = set()

    def clear(self) -> None:
        self.by_client.clear()
        self.daily.clear()
        self.active.clear()

    def cleanup(self) -> None:
        now = time.monotonic()
        for key, stamps in list(self.by_client.items()):
            while stamps and stamps[0] <= now - RATE_WINDOW_SECONDS:
                stamps.popleft()
            if not stamps:
                del self.by_client[key]
        while self.daily and self.daily[0] <= now - 86400:
            self.daily.popleft()

    def admit(self, client: str, task_id: str, stored_count: int) -> None:
        self.cleanup()
        now = time.monotonic()
        key = token_digest(client)
        stamps = self.by_client.get(key, deque())
        wait = 0
        if len(stamps) >= RATE_REQUESTS:
            wait = max(1, int(stamps[0] + RATE_WINDOW_SECONDS - now) + 1)
        elif len(self.daily) >= DAILY_REQUESTS:
            wait = max(1, int(self.daily[0] + 86400 - now) + 1)
        elif (
            len(self.active) >= MAX_ACTIVE_TASKS
            or stored_count >= MAX_STORED_TASKS
            or (key not in self.by_client and len(self.by_client) >= MAX_RATE_IDENTITIES)
        ):
            wait = 60
        if wait:
            raise HTTPException(429, "요청 한도에 도달했습니다. 잠시 후 다시 시도해주세요.",
                                headers={"Retry-After": str(wait)})
        stamps.append(now)
        self.by_client[key] = stamps
        self.daily.append(now)
        self.active.add(task_id)


admission = AdmissionControl()


class RequestSecurityMiddleware:
    def __init__(self, app, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                protected = {
                    b"cache-control": b"no-store",
                    b"referrer-policy": b"no-referrer",
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                }
                message["headers"] = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() not in protected
                ] + list(protected.items())
            await send(message)

        async def reject(code, detail):
            await JSONResponse({"detail": detail}, status_code=code)(scope, receive, secure_send)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                await reject(403, "허용되지 않은 요청 출처입니다.")
                return
        if scope["method"] == "POST":
            if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                await reject(415, "application/json 요청만 허용됩니다.")
                return
        try:
            length = int(headers.get("content-length", "0"))
            if length < 0:
                raise ValueError
        except ValueError:
            await reject(400, "잘못된 요청 길이입니다.")
            return
        if length > MAX_BODY_BYTES:
            await reject(413, "요청 데이터가 너무 큽니다.")
            return

        # Enforce the actual bytes too, including chunked or absent Content-Length.
        body = bytearray()
        oversized = False

        async def read_body():
            nonlocal oversized
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return False
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    oversized = True
                    return False
                body.extend(chunk)
                if not message.get("more_body", False):
                    return True

        try:
            complete = await asyncio.wait_for(read_body(), timeout=10)
        except TimeoutError:
            await reject(408, "요청 수신 시간이 초과되었습니다.")
            return
        if not complete:
            if oversized:
                await reject(413, "요청 데이터가 너무 큽니다.")
            return
        delivered = False

        async def replay_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, secure_send)
