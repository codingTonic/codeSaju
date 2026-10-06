"""Calendar boundary and stateless admission guarantees for the free chart."""

from datetime import date
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import chart, main, security, yeoul_routes


def payload(**overrides):
    return {
        "birth_date": "1990-05-15",
        "birth_time": "09:30",
        "calendar_type": "solar",
        "processing_consent": True,
        "privacy_policy_version": "2026-09-08",
        "age_confirmed": True,
        **overrides,
    }


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    main.tasks.clear()
    security.admission.clear()
    chart.chart_admission.clear()
    monkeypatch.setattr(chart, "analysis_today", lambda: date(2026, 9, 29))
    yield
    main.tasks.clear()
    security.admission.clear()
    chart.chart_admission.clear()


def post(**overrides):
    return TestClient(main.app).post("/api/v2/chart", json=payload(**overrides))


def pillars(result):
    return {p["key"]: p for p in result["profile"]["pillars"]}


def test_preview_requires_no_ai_key_and_never_creates_tasks_or_spends_ai_quota(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Chart preview must not call AI or its admission control")

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(yeoul_routes, "generate_reading", forbidden)
    monkeypatch.setattr(security.admission, "admit", forbidden)
    response = post()
    assert response.status_code == 200
    result = response.json()
    assert result["generation_mode"] == "local_calculation"
    assert len(result["profile"]["pillars"]) == 4
    assert result["profile"]["element_count_total"] == 8
    assert sum(result["profile"]["element_counts"].values()) == 8
    assert result["method"]["engine_version"] == "1.4.8"
    assert result["yongshin"]["status"] == "not_calculated"
    assert result["shinsal"]["status"] == "not_calculated"
    assert response.headers["cache-control"] == "no-store"
    assert not main.tasks and not security.admission.daily and not security.admission.active
    assert len(chart.chart_admission.by_client) == 1
    assert all(len(identity) == 64 for identity in chart.chart_admission.by_client)


def test_unknown_time_omits_hour_and_does_not_return_placeholder_as_actual_birth():
    result = post(birth_time="09:30", birth_time_unknown=True).json()
    assert len(result["profile"]["pillars"]) == 3
    assert "time" not in pillars(result)
    assert result["profile"]["element_count_total"] == 6
    assert result["profile"]["missing_pillars"] == ["시주"]
    assert result["profile"]["solar_birth"] == "1990-05-15"
    assert result["profile"]["time_known"] is False
    assert any("정오" in note for note in result["method"]["limitations"])


@pytest.mark.parametrize("overrides", [
    {"processing_consent": False},
    {"processing_consent": "true"},
    {"age_confirmed": False},
    {"age_confirmed": "true"},
    {"privacy_policy_version": "2026-09-07"},
    {"birth_date": "2020-05-15"},
    {"birth_date": "2030-05-15"},
    {"birth_date": "1899-12-31"},
    {"birth_date": "2000-02-30"},
    {"birth_date": "1990-5-15"},
    {"birth_date": "2000-01-01T00:00:00"},
    {"birth_time": None},
    {"birth_time": "09:30:01"},
    {"birth_time": "09:30+09:00"},
    {"is_leap_month": True},
    {"calendar_type": "lunar", "is_leap_month": True, "birth_date": "2000-02-15"},
    {"calendar_type": "lunar", "birth_date": "2000-02-31"},
    {"birth_region": "US"},
    {"partner_name": "third-party-private-input"},
])
def test_invalid_inputs_rejected_without_echo_or_ai_cost(overrides):
    response = post(**overrides)
    assert response.status_code == 422
    assert "third-party-private-input" not in response.text
    assert not main.tasks and not security.admission.daily


def test_real_lunar_february_30_is_valid_and_equals_converted_solar_chart():
    lunar_response = post(birth_date="2000-02-30", calendar_type="lunar")
    assert lunar_response.status_code == 200
    lunar = lunar_response.json()
    solar = post(birth_date="2000-04-04").json()
    assert lunar["profile"]["solar_birth"] == "2000-04-04 09:30:00"
    assert lunar["profile"]["pillars"] == solar["profile"]["pillars"]
    assert lunar["profile"]["element_counts"] == solar["profile"]["element_counts"]


def test_valid_leap_month_has_distinct_conversion_from_regular_month():
    regular = post(birth_date="1990-05-15", calendar_type="lunar").json()
    leap_response = post(birth_date="1990-05-15", calendar_type="lunar", is_leap_month=True)
    assert leap_response.status_code == 200
    leap = leap_response.json()
    assert regular["profile"]["solar_birth"] == "1990-06-07 09:30:00"
    assert leap["profile"]["solar_birth"] == "1990-07-07 09:30:00"


def test_age_limit_uses_converted_lunar_date_and_exact_solar_birthday():
    # Lunar 2008-09-01 is solar 2008-09-29, not the date suggested by its digits.
    assert post(birth_date="2008-09-01", calendar_type="lunar").status_code == 200
    assert post(birth_date="2008-09-02", calendar_type="lunar").status_code == 422
    assert post(birth_date="2008-09-29").status_code == 200
    assert post(birth_date="2008-09-30").status_code == 422


def test_ipchun_year_and_month_change_at_korean_clock_not_beijing_clock():
    # lunar-python 1.4.8 table: 2000-02-04 20:40:24 UTC+8 = 21:40:24 KST.
    early = pillars(post(birth_date="2000-02-04", birth_time="20:41").json())
    before = pillars(post(birth_date="2000-02-04", birth_time="21:40").json())
    after = pillars(post(birth_date="2000-02-04", birth_time="21:41").json())
    assert early["year"]["gan_zhi"] == before["year"]["gan_zhi"] == "己卯"
    assert before["month"]["gan_zhi"] == "丁丑"
    assert after["year"]["gan_zhi"] == "庚辰"
    assert after["month"]["gan_zhi"] == "戊寅"
    assert before["day"]["gan_zhi"] == after["day"]["gan_zhi"] == "壬辰"


def test_month_changes_at_jeolip_not_gregorian_month_start():
    # 2000 경칩: 14:42:40 UTC+8 = 15:42:40 KST.
    before = pillars(post(birth_date="2000-03-05", birth_time="15:42").json())
    after = pillars(post(birth_date="2000-03-05", birth_time="15:43").json())
    assert before["month"]["gan_zhi"] == "戊寅"
    assert after["month"]["gan_zhi"] == "己卯"
    assert before["year"]["gan_zhi"] == after["year"]["gan_zhi"] == "庚辰"


def test_timezone_conversion_does_not_shift_day_master_or_ten_gods_at_midnight():
    result = post(birth_date="2000-03-05", birth_time="00:30").json()
    values = pillars(result)
    assert values["day"]["gan_zhi"] == "壬戌"
    assert values["time"]["gan_zhi"] == "庚子"
    assert values["year"]["stem_ten_god"] == "편인"  # 庚 relative to 壬, not preceding 辛 day.
    assert values["month"]["stem_ten_god"] == "편관"
    assert values["month"]["hidden_stems"][0]["ten_god"] == "식신"


def test_late_zi_rule_is_explicit_and_day_rolls_at_midnight():
    late = post(birth_date="2000-03-05", birth_time="23:30").json()
    next_day = post(birth_date="2000-03-06", birth_time="00:30").json()
    assert pillars(late)["day"]["gan_zhi"] == "壬戌"
    assert pillars(next_day)["day"]["gan_zhi"] == "癸亥"
    assert pillars(late)["time"]["gan_zhi"] == pillars(next_day)["time"]["gan_zhi"] == "壬子"
    assert "sect=2" in late["method"]["day_boundary"]


@pytest.mark.parametrize("birthday,uncertain", [
    ("2000-02-04", ["year", "month"]),
    ("2000-03-05", ["month"]),
    ("2000-03-06", []),
])
def test_unknown_birth_time_marks_only_ambiguous_term_pillars(birthday, uncertain):
    result = post(birth_date=birthday, birth_time=None, birth_time_unknown=True).json()
    assert result["profile"]["uncertain_pillars"] == uncertain
    assert [key for key, p in pillars(result).items() if p["estimated"]] == uncertain
    assert result["profile"]["element_counts_estimated"] is bool(uncertain)
    assert ("추정" in result["profile"]["element_note"]) is bool(uncertain)


def test_preview_rate_limit_returns_retry_after_and_does_not_consume_ai_limit(monkeypatch):
    monkeypatch.setattr(chart.chart_admission, "requests", 1)
    assert post().status_code == 200
    blocked = post()
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    assert not security.admission.daily and not security.admission.by_client


def test_rate_limit_memory_is_bounded_and_recovers_after_window(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(chart.clock, "monotonic", lambda: now[0])
    limiter = chart.ChartRateLimit(requests=2, window_seconds=10, max_identities=2)
    limiter.admit("first")
    limiter.admit("second")
    limiter.admit("first")
    for client in ("first", "third"):
        with pytest.raises(HTTPException) as caught:
            limiter.admit(client)
        assert caught.value.status_code == 429
    assert len(limiter.by_client) == 2
    assert sum(map(len, limiter.by_client.values())) == 3
    now[0] = 110.0
    limiter.admit("third")
    assert len(limiter.by_client) == 1
