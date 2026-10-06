from __future__ import annotations

import asyncio
from datetime import date, time
from email.message import EmailMessage
from pathlib import Path
import sys

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import email_service
from app.email_service import EmailSettings
from app.models import SajuRequest


def make_request(**overrides: object) -> SajuRequest:
    values: dict[str, object] = {
        "name": "테스트 사용자",
        "birth_date": date(1992, 4, 20),
        "birth_time": time(11, 40),
        "gender": "female",
        "relationship_status": "single",
        "mbti": "INFP",
        "calendar_type": "solar",
        "email_notification_consent": True,
    }
    values.update(overrides)
    return SajuRequest(**values)


def make_settings(**overrides: object) -> EmailSettings:
    values: dict[str, object] = {
        "enabled": True,
        "smtp_user": "sender@gmail.com",
        "app_password": "private-app-password",
        "recipients": ("owner@gmail.com",),
    }
    values.update(overrides)
    return EmailSettings(**values)


def test_message_excludes_user_and_partner_information() -> None:
    request = make_request(
        relationship_status="dating",
        focus_concern="이직과 커리어 전환",
        partner_name="연인",
        partner_birth_date=date(1993, 1, 2),
        partner_birth_time_unknown=True,
        partner_gender="male",
        partner_mbti="ENTJ",
    )

    message = email_service.build_user_info_message("task-123", request, make_settings())
    body = message.get_content()

    assert message["To"] == "owner@gmail.com"
    assert "새 분석 요청" in str(message["Subject"])
    assert "테스트 사용자" not in str(message["Subject"])
    assert "작업 ID: task-123" in body
    assert "생년월일: 1992-04-20 (양력)" not in body
    assert "[연인 정보]" not in body
    assert "이름: 연인" not in body
    assert "태어난 시간: 시간 모름" not in body
    assert "가장 궁금한 고민: 이직과 커리어 전환" not in body
    assert "private-app-password" not in body


def test_delivery_uses_configured_gmail_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    captured: dict[str, object] = {}

    monkeypatch.setattr(email_service, "get_email_settings", lambda: settings)

    def fake_send(message: EmailMessage, active_settings: EmailSettings) -> None:
        captured["message"] = message
        captured["settings"] = active_settings

    monkeypatch.setattr(email_service, "_send_message_sync", fake_send)

    status = asyncio.run(
        email_service.deliver_user_info_notification("task-123", make_request())
    )

    assert status == "sent"
    assert captured["settings"] == settings


def test_delivery_skips_email_without_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(email_service, "get_email_settings", make_settings)
    called = False

    def fake_send(message: EmailMessage, active_settings: EmailSettings) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(email_service, "_send_message_sync", fake_send)

    status = asyncio.run(
        email_service.deliver_user_info_notification(
            "task-123",
            make_request(email_notification_consent=False),
        )
    )

    assert status == "not_consented"
    assert called is False
