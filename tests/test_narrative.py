from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.analysis import build_local_analysis
from app.content import ROLE_LENSES, interpretation_brief
from app.gemini import (
    _build_chapter_prompt, _chapter_scope_issues, _hard_quality_issues,
    _normalize_generated_copy, _request_body, _section_meets_action_contract,
)
from app.portraits import ROLE_PORTRAITS, role_interplay
from app.models import SajuRequest
from app.narrative import ROLE_OPENINGS, narrative_claim_issues, narrative_moments
from app.saju import build_saju_profile


def reader(**updates):
    return SajuRequest.model_validate(dict(
        name="문체 검증", birth_date="1990-05-15", birth_time="14:30",
        gender="male", relationship_status="single",
    ) | updates)


@pytest.mark.parametrize("chapter", range(1, 6))
def test_voice_reaches_every_chapter_without_changing_generation_budget(chapter):
    request = reader()
    body = _request_body(request, chapter, "test-model")
    assert "몰입형 문체" in body["input"]
    assert "강렬한 제목 → 구체적인 조건형 장면" in body["input"]
    assert "제목에도 사실 기준" in body["system_instruction"]
    assert body["generation_config"]["max_output_tokens"] == 12288
    assert "별도 `### 사주 근거`" in body["input"]


def test_all_chart_roles_have_distinct_opening_contrasts():
    assert ROLE_OPENINGS.keys() == ROLE_LENSES.keys()
    assert len({moment[0] for moment in ROLE_OPENINGS.values()}) == 10
    for role, moment in ROLE_OPENINGS.items():
        assert narrative_moments(role)["section_1_1"] == moment
        assert not narrative_claim_issues("\n".join(moment))


@pytest.mark.parametrize("status", ["single", "dating", "married"])
def test_local_fallback_preserves_chart_copy_and_choice_structure(status):
    request = reader(relationship_status=status)
    profile = build_saju_profile(request)
    role = interpretation_brief(profile)["primary_role"]
    result = build_local_analysis("voice-test", request)
    for section_id, (hook, scene, criterion) in narrative_moments(role).items():
        text = result[section_id]
        assert f"### {hook}" in text
        assert scene in text
        assert f"**{criterion}**" in text
        assert text.index(scene) < text.index(criterion)
        assert text.endswith(f"**{criterion}**")
        assert "### 지금 할 일" not in text
        assert not _hard_quality_issues({section_id: text}, (section_id,), request, {})
    assert profile["day_master"]["label"] in result["section_1_1"]
    assert "전 연인" not in result["section_4_2"]


@pytest.mark.parametrize("text", [
    "올해 반드시 돈이 들어옵니다.",
    "### 10월에 귀인이 찾아옵니다",
    "곧 운명의 상대를 만납니다.",
    "이 기회를 놓치면 평생 후회합니다.",
    "재회는 확정입니다.",
    "확정할 수는 없지만 반드시 합격합니다.",
])
def test_explicit_predictions_and_fear_hooks_reach_existing_repair_path(text):
    assert narrative_claim_issues(text)
    assert "확정 예언 또는 공포 유도 표현" in _chapter_scope_issues("section_3_3", text, reader())


@pytest.mark.parametrize("text", [
    "### 당신을 찾는 곳과, 당신이 빛나는 곳은 다를 수 있습니다",
    "다시 연락이 온다면, 반가움보다 달라진 행동을 보세요.",
    "올해 반드시 돈이 들어온다는 뜻은 아닙니다.",
    "반드시 합격한다고 보장할 수 없습니다.",
    "30일 뒤 실제로 달라진 조건을 확인해보세요.",
    "귀인이 오는 시기를 확정하지 않습니다.",
])
def test_metaphors_conditional_scenes_and_disclaimers_are_not_predictions(text):
    assert not narrative_claim_issues(text)


def test_normalization_keeps_literary_heading_and_choice_line():
    text = "### 익숙한 이름보다 달라진 행동\n\n연락이 온다면 행동을 살펴보세요.\n\n**다시 왔다는 사실보다 달라진 증거를 보세요.**"
    assert _normalize_generated_copy(text) == text


def test_prompt_examples_stay_within_their_chapter():
    assert "당신을 찾는 곳과" in _build_chapter_prompt(reader(), 3)
    assert "당신을 찾는 곳과" not in _build_chapter_prompt(reader(), 4)
    assert "인연의 이름보다" in _build_chapter_prompt(reader(), 4)


def test_reflective_copy_passes_without_homework_but_not_without_substance():
    text = build_local_analysis("reflective", reader())["section_1_1"]
    assert _section_meets_action_contract("section_1_1", text)
    assert not _section_meets_action_contract("section_1_1", "### 제목\n\n**당신을 이해하는 데 필요한 한 문장입니다.**")
    assert not _section_meets_action_contract("section_1_1", text + "\n\n1. 매일 일기를 쓰세요.")
    assert not _section_meets_action_contract("section_1_1", text.rsplit("\n\n", 1)[0])


def test_regular_sections_have_no_action_lists_but_final_plans_are_preserved():
    result = build_local_analysis("less-homework", reader(focus_concern="연애와 관계"))
    import re
    for section_id, value in result.items():
        if not re.fullmatch(r"section_[1-5]_\d", section_id):
            continue
        if section_id in {"section_5_2", "section_5_3", "section_5_4", "section_5_5"}:
            continue
        assert "### 지금 할 일" not in value
        assert not re.search(r"(?m)^\d+\. ", value)
        assert value.endswith("**")
    assert "30일 점검" in result["section_5_3"]
    assert "첫 14일" in result["section_5_5"]
    assert result["quick_summary"]["actions"] == result["practical_summary"]["actions"]


def test_portrait_summary_and_detail_share_the_same_calculated_role():
    assert ROLE_PORTRAITS.keys() == ROLE_LENSES.keys()
    for birth_date in ("1990-05-15", "1990-05-16", "1991-08-12"):
        request = reader(birth_date=birth_date)
        result = build_local_analysis("portrait", request)
        role = interpretation_brief(build_saju_profile(request))["primary_role"]
        portrait = result["quick_summary"]["self_portrait"]
        assert portrait["body"] == ROLE_PORTRAITS[role][0]
        assert portrait["body"] in result["section_1_1"]
        assert portrait["scene"] in result["section_1_1"]
    assert role_interplay("비견", "정재") != role_interplay("정재", "비견")
    assert "두 관점" not in role_interplay("정재", "정재")


def test_observable_warnings_are_allowed_without_identifying_an_evil_person():
    for copy in (
        "거절 뒤에도 압박이 반복된다면, 호의와 별개로 경계를 지킬 필요가 있습니다.",
        "책임은 늘어나는데 권한이 없다면 감당하기 어려운 조건일 수 있습니다.",
    ):
        assert not narrative_claim_issues(copy)
