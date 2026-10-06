from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.analysis import build_local_analysis, build_quick_summary, build_practical_summary, focus_domain_for_request, section_ids
from app.gemini import _draft_rank, _hard_quality_issues, _saju_domain_issues, _chapter_scope_issues, _normalize_generated_copy
from app.models import SajuRequest
from app.saju import REPORT_DATE, build_saju_profile


def reader(**updates):
    values = dict(name="내용 검증", birth_date="1990-05-15", birth_time="14:30", gender="male", relationship_status="single")
    return SajuRequest.model_validate(values | updates)


@pytest.mark.parametrize("reference", [date(2026, 1, 1), date(2026, 9, 6), date(2026, 9, 8), date(2026, 12, 31)])
def test_monthly_windows_start_in_current_luck_and_have_no_gaps(reference):
    profile = build_saju_profile(reader(), reference_date=reference)
    windows = profile["luck"]["monthly_flow"]
    assert len(windows) == 12
    assert windows[0]["gan_zhi"] == profile["luck"]["current_month"]["gan_zhi"]
    assert windows[0]["boundary_start"]["date"] <= reference.isoformat() <= windows[0]["boundary_end"]["date"]
    assert len({window["gan_zhi"] for window in windows}) == 12
    for first, second in zip(windows, windows[1:]):
        assert first["boundary_end"] == second["boundary_start"]


def test_annual_luck_before_spring_does_not_skip_the_upcoming_year():
    luck = build_saju_profile(reader(), reference_date=date(2026, 1, 1))["luck"]
    assert luck["current_year"]["year"] == 2025
    assert luck["next_year"]["year"] == 2026
    assert luck["next_year"]["gan_zhi"] == "丙午"


def test_unknown_time_overrides_stale_time_and_uses_six_characters():
    request = reader(birth_time_unknown=True)
    assert request.birth_time is None
    profile = build_saju_profile(request, reference_date=date(2026, 9, 6))
    summary = build_quick_summary(request, {}, profile)
    practical = build_practical_summary(request, {}, summary, profile)
    assert summary["confidence"] == "low"
    assert summary["answer_window_start"] == "2026-09-06"
    assert "6글자" in practical["chart_note"]
    assert "일간" not in summary["leading_roles"]
    assert practical["actions"] == summary["actions"]


@pytest.mark.parametrize("status", ["single", "dating", "married"])
@pytest.mark.parametrize("concern", [None, "이직과 커리어 전환", "연애와 관계", "투자와 저축", "시험과 학업", "건강과 불면", "가족과 부모"])
def test_every_local_repair_passes_the_same_editorial_checks_as_ai(status, concern):
    request = reader(relationship_status=status, focus_concern=concern)
    result = build_local_analysis("quality", request)
    assert not _hard_quality_issues(result, tuple(section_ids(request)), request, {})
    assert result["quick_summary"]["actions"] == result["practical_summary"]["actions"]
    assert result["special_dates"] == result["quick_summary"]["special_dates"]
    for section_id in section_ids(request):
        assert len(result[section_id]) >= 280
        assert "### 사주 근거" not in result[section_id]


def test_personalization_changes_with_chart_and_relationship_status():
    first = build_local_analysis("one", reader())
    second = build_local_analysis("two", reader(birth_date="1990-05-16"))
    assert first["section_1_1"] != second["section_1_1"]
    assert first["section_3_1"] != second["section_3_1"]
    summaries = [build_quick_summary(reader(relationship_status=status, focus_concern="연애와 관계"), {}) for status in ("single", "dating", "married")]
    assert len({summary["direct_answer"] for summary in summaries}) == 3
    assert len({summary["actions"][1]["action"] for summary in summaries}) == 3
    assert "배우자" in summaries[2]["direct_answer"]


@pytest.mark.parametrize(("concern", "domain"), [("시험 공부", "study"), ("가족과 부모", "family"), ("건강과 불면", "health"), ("이직 후 투자와 대출, 저축", "money")])
def test_concern_domain_uses_relevance_instead_of_first_keyword(concern, domain):
    assert focus_domain_for_request(reader(focus_concern=concern)) == domain


def test_no_diagnostic_claim_is_inferred_from_visible_elements():
    profile = build_saju_profile(reader())
    assert profile["organ_profile"]["weak_organs"] == []
    assert all("0자" not in item or "능력이 부족하다는 뜻도 아닙니다" in item for item in profile["shadow_profile"]["element_imbalances"])
    assert _chapter_scope_issues("section_5_1", "수 기운이 부족하므로 신장이 약합니다.", reader())
    assert not _chapter_scope_issues("section_5_1", "오행으로 취약 장기를 판단하지 않습니다.", reader())


def test_korean_ten_god_errors_and_wrong_day_master_are_rejected():
    assert _saju_domain_issues("지지 진토(정재)를 활용합니다.", reader())
    assert not _saju_domain_issues("지지 진토(편인)를 참고합니다.", reader())
    assert _saju_domain_issues("당신은 갑목 일간입니다.", reader())
    assert not _saju_domain_issues("경금 일간을 참고합니다.", reader())


def test_correct_draft_beats_longer_inaccurate_or_repetitive_draft():
    request = reader()
    valid = build_local_analysis("draft", request)["section_1_1"]
    invalid = valid + "\n\n당신은 갑목 일간입니다."
    repeated = valid + ("\n\n생활에서 반복되는 장면을 통해 실제 조건을 확인하고 오늘 사용할 수 있는 행동을 찾으세요." * 5)
    assert _draft_rank("section_1_1", valid, request) > _draft_rank("section_1_1", invalid, request)
    assert _draft_rank("section_1_1", valid, request) > _draft_rank("section_1_1", repeated, request)
    assert "단단한_강철" not in _normalize_generated_copy("#기질키워드 #페르소나\n\n본문")


def test_shared_report_date_is_used_for_summary_and_calendar():
    token = REPORT_DATE.set(date(2026, 12, 31))
    try:
        result = build_local_analysis("clock", reader())
        assert result["saju_profile"]["reference_date"] == "2026-12-31"
        assert result["quick_summary"]["answer_window_start"] == "2026-12-31"
        assert "2027-01-29" in result["section_5_3"]
        assert all(item["date"] > "2026-12-31" for item in result["special_dates"])
    finally:
        REPORT_DATE.reset(token)


@pytest.mark.parametrize("concern", ["연애와 새로운 만남", "이직과 커리어 전환", "투자와 저축"])
def test_focus_and_90_day_plan_keep_summary_actions_in_their_original_periods(concern):
    request = reader(focus_concern=concern)
    result = build_local_analysis("timeline", request)
    today, week, month = [item["action"] for item in result["quick_summary"]["actions"]]
    focus = result["section_5_5"]
    plan = result["section_5_3"]
    assert f"**1~2일차**: {today}" in focus
    assert f"**5~7일차**: {week}" in focus
    assert f"**14일차**: {month}" not in focus
    assert f"오늘은 {today}" in plan
    assert f"이번 주에는 {week}" in plan
    assert f"30일 점검**: {month}" in plan
    assert f"30일 점검**: {today}" not in plan
    assert f"60일 점검**: {week}" not in plan
