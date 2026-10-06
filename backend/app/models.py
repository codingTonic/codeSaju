from __future__ import annotations

from datetime import date, time
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


MBTI_PATTERN = re.compile(r"^[EI][NS][TF][JP]$")


class SajuRequest(BaseModel):
    """Validated input accepted by the Personal OS frontend."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=50)
    birth_date: date
    birth_time: time | None = None
    birth_time_unknown: bool = False
    gender: Literal["male", "female"]
    relationship_status: Literal["single", "dating", "married"]
    mbti: str | None = None
    focus_concern: str | None = Field(default=None, max_length=200)
    calendar_type: Literal["solar", "lunar"] = "solar"
    is_leap_month: bool = False
    processing_consent: StrictBool = False
    privacy_policy_version: Literal["2026-09-07"] | None = None
    email_notification_consent: StrictBool = False

    partner_name: str | None = Field(default=None, max_length=50)
    partner_birth_date: date | None = None
    partner_birth_time: time | None = None
    partner_birth_time_unknown: bool = False
    partner_gender: Literal["male", "female"] | None = None
    partner_mbti: str | None = None
    partner_calendar_type: Literal["solar", "lunar"] = "solar"
    partner_is_leap_month: bool = False

    @field_validator("birth_date", "partner_birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return value
        if value < date(1900, 1, 1) or value > date.today():
            raise ValueError("생년월일은 1900-01-01부터 오늘 사이여야 합니다.")
        return value

    @field_validator("mbti", "partner_mbti")
    @classmethod
    def normalize_mbti(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.upper()
        if not MBTI_PATTERN.fullmatch(normalized):
            raise ValueError("올바른 MBTI 형식이 아닙니다.")
        return normalized

    @field_validator("focus_concern", mode="before")
    @classmethod
    def normalize_focus_concern(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_birth_time(self) -> SajuRequest:
        if self.birth_time_unknown:
            self.birth_time = None
        if self.partner_birth_time_unknown:
            self.partner_birth_time = None
        if self.birth_time is None and not self.birth_time_unknown:
            raise ValueError("태어난 시간을 입력하거나 시간 모름을 선택해주세요.")
        self._validate_lunar_input(
            self.birth_date,
            self.birth_time,
            self.birth_time_unknown,
            self.calendar_type,
            self.is_leap_month,
            "본인",
        )
        if self.partner_birth_date:
            self._validate_lunar_input(
                self.partner_birth_date,
                self.partner_birth_time,
                self.partner_birth_time_unknown,
                self.partner_calendar_type,
                self.partner_is_leap_month,
                "연인",
            )
        return self

    @staticmethod
    def _validate_lunar_input(
        birth_date: date,
        birth_time: time | None,
        time_unknown: bool,
        calendar_type: str,
        is_leap_month: bool,
        subject: str,
    ) -> None:
        if calendar_type != "lunar":
            if is_leap_month:
                raise ValueError(f"{subject}의 윤달은 음력을 선택했을 때만 사용할 수 있습니다.")
            return

        from lunar_python import Lunar

        selected_time = birth_time if not time_unknown else None
        selected_time = selected_time or time(12, 0)
        lunar_month = -birth_date.month if is_leap_month else birth_date.month
        try:
            Lunar.fromYmdHms(
                birth_date.year,
                lunar_month,
                birth_date.day,
                selected_time.hour,
                selected_time.minute,
                0,
            )
        except Exception as exc:
            raise ValueError(
                f"{subject}의 음력 날짜를 변환할 수 없습니다. 날짜와 윤달 여부를 확인해주세요."
            ) from exc


class TaskAccepted(BaseModel):
    access_token: str
    task_id: str
    status: Literal["queued"]


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    mode: str
    durable_tasks: bool
    ai_configured: bool
    email_enabled: bool
    email_configured: bool
