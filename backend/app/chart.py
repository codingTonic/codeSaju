"""Stateless chart preview: local calendar arithmetic, without AI or task storage.

The year/month comparison converts a fixed UTC+9 Korean birth clock to the
library's UTC+8 solar-term table. Day/hour retain the entered local clock. This
is not an independently verified Korean almanac; the response states the rules.
"""

from __future__ import annotations

from collections import Counter, deque
from datetime import date, time
from importlib.metadata import version
import math
import re
import time as clock
from typing import Any, Literal

from fastapi import HTTPException
from lunar_python import Lunar, Solar
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from .saju import (
    DAY_MASTER_ARCHETYPES,
    ELEMENT_ORDER,
    GAN_ELEMENT,
    GAN_READING,
    SajuCalculationError,
    _branch_ten_god_details,
    _pillar,
    _ten_god,
    analysis_today,
)
from .security import token_digest


CHART_VERSION = 1
POLICY_VERSION = "2026-09-08"
ENGINE_VERSION = version("lunar-python")


class ChartRequest(BaseModel):
    """Only birth details and the site's existing adult/processing consent.

    A lunar date is not a Gregorian date: February 30 can be a valid input.
    Library conversion happens after independent preview admission control.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    birth_date: str
    birth_time: time | None = None
    birth_time_unknown: StrictBool = False
    calendar_type: Literal["solar", "lunar"] = "solar"
    is_leap_month: StrictBool = False
    gender: Literal["male", "female"] | None = None
    birth_region: Literal["KR"] = "KR"
    processing_consent: StrictBool = False
    privacy_policy_version: Literal["2026-09-08"] | None = None
    age_confirmed: StrictBool = False

    @field_validator("birth_date")
    @classmethod
    def date_shape(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("생년월일은 YYYY-MM-DD 형식으로 입력해주세요.")
        year, month, day = map(int, value.split("-"))
        if not 1900 <= year <= analysis_today().year or not 1 <= month <= 12 or not 1 <= day <= 31:
            raise ValueError("생년월일은 1900-01-01부터 오늘 사이여야 합니다.")
        return value

    @model_validator(mode="after")
    def input_rules(self):
        if not self.processing_consent or self.privacy_policy_version != POLICY_VERSION:
            raise ValueError("개인정보 처리 안내를 확인하고 분석에 동의해주세요.")
        if not self.age_confirmed:
            raise ValueError("만 18세 이상인 경우에 이용할 수 있습니다.")
        if self.birth_time_unknown:
            self.birth_time = None
        elif self.birth_time is None:
            raise ValueError("태어난 시간을 입력하거나 시간 모름을 선택해주세요.")
        elif self.birth_time.tzinfo is not None or self.birth_time.second or self.birth_time.microsecond:
            raise ValueError("태어난 시간은 시간대 없는 시와 분으로 입력해주세요.")
        if self.calendar_type == "solar":
            if self.is_leap_month:
                raise ValueError("본인의 윤달은 음력을 선택했을 때만 사용할 수 있습니다.")
            date.fromisoformat(self.birth_date)
        return self


class ChartRateLimit:
    """Process-local, bounded, independent of paid reading/AI allowances.

    Mutations run on the single application's event loop, just like the existing
    admission control. Each identity retains at most ``requests`` timestamps.
    Replicas require a shared edge limit before this process-local guard.
    """

    def __init__(self, requests: int = 20, window_seconds: int = 60, max_identities: int = 4096):
        if min(requests, window_seconds, max_identities) <= 0:
            raise ValueError("Chart rate limits must be positive")
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_identities = max_identities
        self.by_client: dict[str, deque[float]] = {}

    def clear(self) -> None:
        self.by_client.clear()

    def admit(self, client: str) -> None:
        now = clock.monotonic()
        cutoff = now - self.window_seconds
        for identity, stamps in list(self.by_client.items()):
            while stamps and stamps[0] <= cutoff:
                stamps.popleft()
            if not stamps:
                del self.by_client[identity]
        key = token_digest(client)
        stamps = self.by_client.get(key)
        if stamps is not None and len(stamps) >= self.requests:
            wait = max(1, math.ceil(stamps[0] + self.window_seconds - now))
        elif stamps is None and len(self.by_client) >= self.max_identities:
            wait = self.window_seconds
        else:
            if stamps is None:
                stamps = self.by_client[key] = deque()
            stamps.append(now)
            return
        raise HTTPException(
            429,
            "원국 조회 요청이 많습니다. 잠시 후 다시 시도해주세요.",
            headers={"Retry-After": str(wait)},
        )


chart_admission = ChartRateLimit()


def _calendar(payload: ChartRequest) -> tuple[Any, Any]:
    year, month, day = map(int, payload.birth_date.split("-"))
    selected_time = payload.birth_time or time(12, 0)
    try:
        if payload.calendar_type == "lunar":
            lunar = Lunar.fromYmdHms(
                year, -month if payload.is_leap_month else month, day,
                selected_time.hour, selected_time.minute, 0,
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(year, month, day, selected_time.hour, selected_time.minute, 0)
            lunar = solar.getLunar()
    except Exception as exc:
        raise SajuCalculationError(
            "생년월일을 변환할 수 없습니다. 날짜와 양력·음력·윤달 여부를 확인해주세요."
        ) from exc
    birthday = date(solar.getYear(), solar.getMonth(), solar.getDay())
    today = analysis_today()
    if birthday < date(1900, 1, 1) or birthday > today:
        raise SajuCalculationError("생년월일은 1900-01-01부터 오늘 사이여야 합니다.")
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    if age < 18:
        raise SajuCalculationError("만 18세 이상인 경우에 이용할 수 있습니다.")
    return lunar, solar


def _uncertain_pillars(solar: Any) -> list[str]:
    """A noon placeholder cannot resolve a solar-term transition birth day."""
    start = Solar.fromYmdHms(solar.getYear(), solar.getMonth(), solar.getDay(), 0, 0, 0).nextHour(-1).getLunar().getEightChar()
    end = Solar.fromYmdHms(solar.getYear(), solar.getMonth(), solar.getDay(), 23, 59, 59).nextHour(-1).getLunar().getEightChar()
    return [key for key in ("year", "month") if getattr(start, f"get{key.capitalize()}")() != getattr(end, f"get{key.capitalize()}")()]


def build_chart(payload: ChartRequest) -> dict[str, Any]:
    lunar, solar = _calendar(payload)
    eight_char = lunar.getEightChar()
    eight_char.setSect(2)  # Pin the existing report's midnight day-pillar convention.
    # LunarYear's solar-term instants are Beijing time (UTC+8). Compare KST
    # births one hour earlier, without shifting the birth's day/hour pillars.
    term_eight_char = solar.nextHour(-1).getLunar().getEightChar()
    day_gan = eight_char.getDayGan()
    time_known = not payload.birth_time_unknown
    uncertain = [] if time_known else _uncertain_pillars(solar)
    pillars = [
        _pillar(term_eight_char if key in {"year", "month"} else eight_char, key=key, label=label)
        for key, label in (("year", "연주"), ("month", "월주"), ("day", "일주"), ("time", "시주"))
        if key != "time" or time_known
    ]
    counts = Counter({element: 0 for element in ELEMENT_ORDER})
    for pillar in pillars:
        # The UTC+8 comparison may land on the previous day. All ten gods still
        # use the user's original day stem, including year/month hidden stems.
        hidden = _branch_ten_god_details(day_gan, pillar["zhi"])
        pillar.update(
            stem_ten_god="일간" if pillar["key"] == "day" else _ten_god(day_gan, pillar["gan"]),
            branch_main_ten_god=hidden[0]["ten_god"],
            hidden_stems=hidden,
            hidden_ten_gods=[item["ten_god"] for item in hidden],
        )
        pillar["estimated"] = pillar["key"] in uncertain
        counts[pillar["gan_element"]] += 1
        counts[pillar["zhi_element"]] += 1
    day_element = GAN_ELEMENT[day_gan]
    limitations = [
        "참고용 계산입니다. lunar-python의 중국 음력·절기표를 사용하며 한국 음력과의 전체 날짜 대조 검증은 완료하지 않았습니다.",
        "한국 표준시 UTC+9를 고정 적용합니다. 다른 지역 출생은 지원하지 않습니다.",
        "출생지 경도, 진태양시, 과거 한국 표준시 변경과 서머타임을 보정하지 않습니다.",
        "오행 수치는 보이는 글자 수입니다. 세력·성격의 강약, 용신 또는 미래 사건의 확률을 뜻하지 않습니다.",
    ]
    if not time_known:
        limitations.append("시간 모름: 시주는 제외하고 정오를 임시값으로 사용합니다. 절기 경계 날짜의 연주·월주는 추정값입니다.")
    return {
        "version": CHART_VERSION,
        "generation_mode": "local_calculation",
        "profile": {
            "calendar_input": "음력" if payload.calendar_type == "lunar" else "양력",
            "is_leap_month": payload.is_leap_month,
            "solar_birth": solar.toYmdHms() if time_known else solar.toYmd(),
            "lunar_birth": lunar.toString(),
            "time_known": time_known,
            "pillars": pillars,
            "missing_pillars": [] if time_known else ["시주"],
            "uncertain_pillars": uncertain,
            "day_master": {
                "gan": day_gan,
                "reading": GAN_READING[day_gan],
                "element": day_element,
                "polarity": "양" if list(GAN_ELEMENT).index(day_gan) % 2 == 0 else "음",
                "label": f"{GAN_READING[day_gan]}{day_element} 일간",
                "archetype": DAY_MASTER_ARCHETYPES[day_gan],
            },
            "element_counts": dict(counts),
            "element_count_total": sum(counts.values()),
            "element_counts_estimated": bool(uncertain),
            "element_note": (
                "천간과 지지의 대표 오행을 각 1자로 집계합니다. 지장간은 별도 표시하며 합산하지 않습니다."
                + (" 출생 시간이 없어 절기 경계의 연주·월주를 정오 기준으로 추정했습니다. 해당 십성과 오행 수치는 실제 출생 시간에 따라 달라질 수 있습니다." if uncertain else "")
            ),
        },
        "method": {
            "engine": "lunar-python",
            "engine_version": ENGINE_VERSION,
            "calculation_version": "yeoul-chart-1",
            "year_boundary": "입춘 시각 · UTC+8 절기표를 한국 표준시 UTC+9로 환산",
            "month_boundary": "절입 시각 · UTC+8 절기표를 한국 표준시 UTC+9로 환산",
            "day_boundary": "sect=2 · 일주는 00시에 변경, 23시 시주의 천간은 라이브러리의 다음 날 기준",
            "timezone": "UTC+9 고정 · 연주·월주 절기 비교만 UTC+8로 환산 · 일주·시주는 입력 시각 적용",
            "ten_gods": "일간 기준 천간 십성 · 지지는 본기 십성과 지장간 십성을 구분",
            "limitations": limitations,
            "source": "https://github.com/6tail/lunar-python",
        },
        "yongshin": {
            "status": "not_calculated",
            "reason": "월령·통근·조후·합충 등을 종합하는 용신 판단은 지원하지 않습니다. 적은 오행을 용신으로 대신 표시하지 않습니다.",
        },
        "shinsal": {
            "status": "not_calculated",
            "reason": "신살별 기준과 해석 검증이 완료되지 않아 신살을 산출하지 않습니다.",
        },
    }
