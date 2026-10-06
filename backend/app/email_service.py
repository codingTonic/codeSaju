from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import getaddresses
import logging
import os
import smtplib
import ssl
from typing import Literal

from .models import SajuRequest


LOGGER = logging.getLogger("personal_os.email")

DeliveryStatus = Literal[
    "queued",
    "disabled",
    "not_consented",
    "misconfigured",
    "sent",
    "failed",
]


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    smtp_user: str
    app_password: str
    recipients: tuple[str, ...]
    host: str = "smtp.gmail.com"
    port: int = 587
    timeout_seconds: float = 15.0
    subject_prefix: str = "[나의 결]"

    @property
    def configured(self) -> bool:
        return bool(
            self.enabled
            and self.smtp_user
            and self.app_password
            and self.recipients
        )


def _env_flag(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if 1 <= parsed <= 65535 else default


def _safe_float(value: str, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_recipients(raw_value: str) -> tuple[str, ...]:
    normalized = raw_value.replace(";", ",")
    recipients: list[str] = []
    for _, address in getaddresses([normalized]):
        clean_address = address.strip()
        if "@" not in clean_address or any(char in clean_address for char in "\r\n"):
            continue
        if clean_address not in recipients:
            recipients.append(clean_address)
    return tuple(recipients)


def get_email_settings() -> EmailSettings:
    smtp_user = os.getenv("GMAIL_SMTP_USER", "").strip()
    recipient_value = os.getenv("EMAIL_NOTIFICATION_TO", "").strip() or smtp_user
    return EmailSettings(
        enabled=_env_flag("EMAIL_NOTIFICATIONS_ENABLED"),
        smtp_user=smtp_user,
        app_password=os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip(),
        recipients=_parse_recipients(recipient_value),
        host=os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com",
        port=_safe_int(os.getenv("GMAIL_SMTP_PORT", "587"), 587),
        timeout_seconds=_safe_float(os.getenv("EMAIL_SMTP_TIMEOUT_SECONDS", "15"), 15.0),
        subject_prefix=os.getenv("EMAIL_SUBJECT_PREFIX", "[나의 결]").strip() or "[나의 결]",
    )


def initial_delivery_status(request: SajuRequest, settings: EmailSettings | None = None) -> DeliveryStatus:
    active_settings = settings or get_email_settings()
    if not request.email_notification_consent:
        return "not_consented"
    if not active_settings.enabled:
        return "disabled"
    if not active_settings.configured:
        return "misconfigured"
    return "queued"


def _label(value: str | None, labels: dict[str, str]) -> str:
    if not value:
        return "미입력"
    return labels.get(value, value)


def _time_label(value: object, unknown: bool) -> str:
    if unknown:
        return "시간 모름"
    if value is None:
        return "미입력"
    return value.isoformat(timespec="minutes")


def build_user_info_message(
    task_id: str,
    request: SajuRequest,
    settings: EmailSettings,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"{settings.subject_prefix} 새 분석 요청"
    message["From"] = settings.smtp_user
    message["To"] = ", ".join(settings.recipients)
    message.set_content(
        "나의 결에 새 분석 요청이 접수되었습니다.\n"
        f"작업 ID: {task_id}\n"
        "개인정보와 결과 조회용 비밀 토큰은 메일에 포함하지 않습니다.\n"
    )
    return message


def _send_message_sync(message: EmailMessage, settings: EmailSettings) -> None:
    tls_context = ssl.create_default_context()
    with smtplib.SMTP(
        settings.host,
        settings.port,
        timeout=settings.timeout_seconds,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=tls_context)
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.app_password)
        smtp.send_message(message)


async def deliver_user_info_notification(
    task_id: str,
    request: SajuRequest,
) -> DeliveryStatus:
    settings = get_email_settings()
    initial_status = initial_delivery_status(request, settings)
    if initial_status != "queued":
        if initial_status == "misconfigured":
            LOGGER.warning(
                "Email notification is enabled but not fully configured",
                extra={"task_id": task_id},
            )
        return initial_status

    message = build_user_info_message(task_id, request, settings)
    try:
        await asyncio.to_thread(_send_message_sync, message, settings)
    except Exception:
        LOGGER.error(
            "Email notification delivery failed",
            extra={"task_id": task_id},
        )
        return "failed"

    LOGGER.info("Email notification delivered", extra={"task_id": task_id})
    return "sent"
