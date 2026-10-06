from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys

import httpx
import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.analysis import (
    build_local_analysis,
    build_local_focus_section,
    build_practical_summary,
    build_quick_summary,
    build_special_dates,
    section_ids,
)
from app.gemini import (
    _build_chapter_prompt,
    _chapter_scope_issues,
    _focus_meets_contract,
    _normalize_generated_copy,
    _quality_issues,
    _saju_domain_issues,
    _section_meets_action_contract,
    generate_gemini_analysis,
)
from app.models import SajuRequest
from app.saju import build_saju_profile
from app.content import interpretation_brief


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def disable_default_fallback_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")


def request_data() -> SajuRequest:
    return SajuRequest.model_validate(
        {
            "name": "테스트 사용자",
            "birth_date": "1990-05-15",
            "birth_time": "14:30",
            "gender": "male",
            "relationship_status": "single",
            "mbti": "infp",
            "calendar_type": "solar",
        }
    )


def request_with_concern(concern: str = "이직과 커리어 전환") -> SajuRequest:
    values = request_data().model_dump()
    values["focus_concern"] = concern
    return SajuRequest.model_validate(values)


DISTINCT_SECTION_ACTIONS: dict[str, tuple[str, str]] = {
    "section_1_1": ("타고난 본연의 기운을 점검하여 일간의 중심을 잡습니다.", "첫인상과 본모습의 차이를 일기장에 기록합니다."),
    "section_1_2": ("오행의 글자수를 대조하여 불균형의 원인을 관찰합니다.", "결핍된 기운이 부르는 현실적 습관을 살핍니다."),
    "section_1_3": ("지장간 십신의 역할을 파악하여 번아웃을 줄입니다.", "속마음의 무의식적 욕구를 세 문장으로 정리합니다."),
    "section_2_1": ("에너지의 정체 구간을 파악하여 현재 병목을 확인합니다.", "올해 세운에서 오는 자극과 막힘을 면밀히 분석합니다."),
    "section_2_2": ("스트레스 이면의 원인을 분석하여 맹점을 살핍니다.", "표면적 갈등 뒤에 숨은 심리적 압박을 점검합니다."),
    "section_2_3": ("오행의 유통 과제를 정하여 실천 기준을 세웁니다.", "정체를 뚫어낼 첫 번째 돌파 행동을 마련합니다."),
    "section_3_1": ("최적의 업무 몰입 환경을 탐색하여 적성을 찾습니다.", "나와 맞지 않는 조직 문화 요소를 배제합니다."),
    "section_3_2": ("고유 재능을 시장 가치로 전환할 구조를 만듭니다.", "성과를 현금 흐름으로 연결하는 방안을 찾습니다."),
    "section_3_3": ("버텨야 할 시점과 움직일 시점을 명확히 가릅니다.", "이직과 새로운 도전에 대한 판단 기준을 둡니다."),
    "section_3_4": ("평생의 자산 흐름을 읽고 금전 누수를 차단합니다.", "위험 관리와 비상금 원칙을 철저히 점검합니다."),
    "section_4_1": ("친밀한 관계에서 반복되는 방어기제를 살핍니다.", "상호작용할 때 나타나는 무의식적 습관을 씁니다."),
    "section_4_2": ("좋은 인연의 관찰 가능한 신호를 세 가지 봅니다.", "나를 채워주는 귀인과의 만남을 준비합니다."),
    "section_4_3": ("공간 에너지를 정돈하여 일상의 활력을 되찾습니다.", "시각적 인지 부하를 줄이는 데스크 셋업을 합니다."),
    "section_5_1": ("실제 생활 기록에서 회복에 도움이 된 활동을 확인합니다.", "하루의 활동과 쉬는 시간을 비교하고 조정 가능한 부담을 찾습니다."),
    "section_5_2": ("앞으로 석 달간 집중할 테마를 명확히 정리합니다.", "월별 기회 포인트를 다이어리에 적어둡니다."),
    "section_5_3": ("선택한 변화를 이어가는 90일 실행 계획을 선택합니다.", "시나리오별 마일스톤 체크리스트를 실행합니다."),
    "section_5_4": ("나만의 고유한 속도를 믿고 묵묵히 걷습니다.", "인생 나침반의 마지막 제언을 가슴에 새깁니다."),
    "section_5_5": ("직접 적은 고민의 선택지와 마감일을 세웁니다.", "실천 가능한 방어 행동 계획을 시작합니다."),
}


def gemini_response(required_ids: tuple[str, ...] = section_ids()) -> dict[str, object]:
    sections = {}
    for section_id in required_ids:
        act1, act2 = DISTINCT_SECTION_ACTIONS.get(
            section_id,
            (f"{section_id} 고유의 분석 과제를 차분히 수행합니다.", f"{section_id} 확인 포인트를 기록합니다."),
        )
        sections[section_id] = (
            "## 계산된 흐름의 핵심\n\n"
            "사람은 누구나 태어날 때 우주가 건넨 고유한 에너지의 결을 품고 세상에 첫발을 내딛습니다. "
            "나의 본연의 기질을 이해하는 일은 부족함을 탓하기 위함이 아니라 가장 강력한 무기를 언제 꺼내 써야 할지 지혜를 얻는 여정입니다.\n\n"
            "### 한눈에 보는 핵심\n\n일간과 명식의 타고난 기운을 바탕으로 생각을 실제 행동으로 옮길 때 무엇이 편하고 어려운지 확인하는 시기입니다. "
            + "생활에서 반복되는 장면을 먼저 살펴보면 어려운 용어를 몰라도 방향을 이해할 수 있습니다. "
            + "같은 방식이 도움이 되었던 경험과 그렇지 않았던 경험을 나누고 그때의 역할과 자원을 비교해보세요. "
            + "\n\n### 현실에서 보이는 신호\n\n준비가 된 일과 아직 확인이 필요한 일을 나누면 "
            + "운의 가능성을 실제 선택에 사용할 수 있습니다. "
            + "생각한 것과 다른 결과가 나왔다면 어떤 조건이 달랐는지 살펴보고 다음에 확인할 질문을 정합니다. "
            + "상대의 동의가 필요한 일이라면 의견을 먼저 묻고, 현재 감당할 수 있는 범위를 기준으로 실행의 크기를 조정하세요. "
            + "현재의 방식이 충분히 도움이 되고 있다면 새로운 과제를 더할 필요 없이 그 조건을 유지할 수 있습니다. "
            + f"\n\n### 지금 할 일\n\n- {act1}\n"
            + f"- {act2}\n\n"
            + "> 스스로에게 물어볼 질문: 지금 확인할 수 있는 가장 작은 사실은 무엇인가요?"
        )
    return {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "status": "done",
                "content": [{"type": "text", "text": json.dumps(sections)}],
            }
        ]
    }


def required_ids_from_request(request: httpx.Request) -> tuple[str, ...]:
    body = json.loads(request.content)
    return tuple(body["response_format"]["schema"]["required"])


def test_single_relationship_prompt_centers_the_single_experience() -> None:
    prompt = _build_chapter_prompt(request_data(), 4)

    assert "현재 솔로" in prompt
    assert "어떤 대화에서 마음이 열리고 가까워질까?" in prompt
    assert "새로운 인연을 알아채는 기회 신호" in prompt
    assert "나를 살려주는 공간 에너지와 일상 정돈법" in prompt
    assert "현재 연인이 있는 것처럼 쓰거나" in prompt
    assert "언제 연인이 생긴다고 예언하지 마세요" in prompt
    assert "거주 형태, 재정 상태, 생계 책임" in prompt


def test_identity_prompt_requests_an_intuitive_type_label() -> None:
    prompt = _build_chapter_prompt(request_data(), 1)

    assert "명식의 뼈대" in prompt
    assert "경금 일간" in prompt
    assert "庚午" in prompt
    assert "강렬한 제목 → 구체적인 조건형 장면 → 핵심 해석과 연결 조건 → 기억할 선택 기준" in prompt
    assert "작은 제안 하나" in prompt
    assert "### 지금 할 일" in prompt
    assert "예시 기준" in prompt


def essay_copy(section_id: str) -> str:
    return (
        "새로운 일을 시작할 때의 속도만으로 자신의 방식을 판단하기는 어렵습니다. "
        "직접 해 보며 답을 찾을 수 있는 상황과 여러 조건을 먼저 비교해야 하는 상황은 다를 수 있기 때문입니다. "
        "어떤 방식이 편했는지 떠올릴 때에는 결과뿐 아니라 당시 선택할 수 있었던 방법도 함께 살펴볼 수 있습니다.\n\n"
        "예를 들어 익숙한 도구로 작은 결과물을 만드는 일에서는 다음 순서가 쉽게 떠오를 수 있습니다. "
        "반면 결과를 누구에게 보여줄지 정해지지 않았다면 같은 도구를 쓰더라도 시작을 망설일 수 있습니다. "
        "이는 실제로 겪었다고 가정한 이력이 아니라 상황에 따라 달라지는 반응을 비교하기 위한 장면입니다.\n\n"
        "이 차이를 살필 때에는 일을 시작하기 전에 이미 알았던 정보와 나중에 알게 된 정보를 나누어 보세요. "
        "방법을 바꿔야 했던 이유가 보인다면 다음에는 필요한 정보를 먼저 찾을 수 있습니다. "
        "경험이 이 장면과 다르다면 자신의 경험을 우선하고, 도움이 된 방식이 무엇이었는지 다른 상황과 비교해 볼 수 있습니다.\n\n"
        f"### 지금 할 일\n\n1. {DISTINCT_SECTION_ACTIONS[section_id][0]}"
    )


def test_essay_layout_requires_prose_and_one_action_and_keeps_legacy_copy() -> None:
    essay = essay_copy("section_1_1")
    assert not _quality_issues({"section_1_1": essay}, ("section_1_1",), request_data())
    assert not _section_meets_action_contract("section_1_1", essay.split("### 지금 할 일")[0])
    assert not _section_meets_action_contract("section_1_1", essay + "\n2. 새 과제를 추가합니다.")
    assert not _section_meets_action_contract("section_1_1", "본문 한 문단입니다.\n\n### 지금 할 일\n\n1. 기록하세요.")
    legacy = build_local_analysis("legacy", request_data())["section_1_1"]
    assert _section_meets_action_contract("section_1_1", legacy)


@pytest.mark.anyio
async def test_new_essay_survives_generation_and_retry_without_template_repair(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    bodies = []
    first_chapter_attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal first_chapter_attempts
        bodies.append(json.loads(request.content))
        required = required_ids_from_request(request)
        sections = {sid: essay_copy(sid) for sid in required}
        if "section_1_1" in required:
            first_chapter_attempts += 1
            if first_chapter_attempts == 1:
                sections["section_1_1"] = sections["section_1_1"].split("### 지금 할 일")[0]
        return httpx.Response(200, json={
            "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(sections)}]}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis("essay", request_data(), client=client)

    assert len(bodies) == 6
    assert "quality_warnings" not in result
    assert result["section_1_1"] == essay_copy("section_1_1")
    assert "### 한눈에 보는 핵심" not in result["section_1_1"]
    retry = next(body["input"] for body in bodies if "[재집필 요청]" in body["input"])
    assert "작은 제안 하나" in retry.split("[재집필 요청]", 1)[1]
    assert "행동 과제 2~3개" not in retry


def test_shadow_profile_injected_into_reader_profile_and_prompt() -> None:
    req = request_data()
    profile = build_saju_profile(req)

    assert "shadow_profile" in profile
    shadow = profile["shadow_profile"]
    assert "day_master_shadow" in shadow
    assert "element_imbalances" in shadow
    assert "ten_god_shadows" in shadow
    assert len(shadow["element_imbalances"]) >= 1

    prompt = _build_chapter_prompt(req, 1)
    assert "[명식에서 확인할 질문 · 성격 진단이 아닌 관찰 가설]" in prompt
    assert "일간별 확인 질문:" in prompt
    assert "오행 분포를 읽을 때의 한계:" in prompt
    assert "주요 십신별 확인 질문:" in prompt


def test_generated_copy_normalizes_known_typos_and_duplicate_headings() -> None:
    normalized = _normalize_generated_copy(
        "## 같은 제목\n\n## 같은 제목\n\n토(토)와 지방 본기를 확인합니다."
    )

    assert normalized.count("## 같은 제목") == 1
    assert "토와 지지 본기" in normalized
    assert "土" not in normalized
    assert "지지 본기" in normalized


def test_generated_copy_normalization_removes_empty_reason_labels() -> None:
    normalized = _normalize_generated_copy(
        "> **사주에서 본 이유**:\n> **입력 정보에서 본 이유**:\n\n실제 설명"
    )

    assert "사주에서 본 이유" not in normalized
    assert "입력 정보에서 본 이유" not in normalized
    assert normalized == "실제 설명"


def test_generated_copy_removes_standalone_saju_basis_section() -> None:
    normalized = _normalize_generated_copy(
        "### 사주 근거와 운의 해석\n\n전문 근거를 길게 설명합니다.\n\n"
        "### 한눈에 보는 핵심\n\n지금 내릴 판단입니다."
    )

    assert "사주 근거와 운의 해석" not in normalized
    assert "전문 근거를 길게 설명합니다" not in normalized
    assert "### 한눈에 보는 핵심" in normalized


def test_timing_prompt_uses_exact_personal_calendar_dates() -> None:
    request = request_data()
    prompt = _build_chapter_prompt(request, 5)
    special_dates = build_special_dates(request)

    assert len(special_dates) == 5
    assert "일진 천간" in prompt
    assert "길일·흉일" in prompt
    assert all(item["date"] in prompt for item in special_dates)
    assert all(item["gan_zhi"] in prompt for item in special_dates)


def test_focus_concern_adds_a_dedicated_section_to_the_last_chapter() -> None:
    prompt = _build_chapter_prompt(request_with_concern(), 5)

    assert "지금 가장 궁금한 고민: 이직과 커리어 전환" in prompt
    assert "section_5_5" in prompt
    assert "위 5개 section ID" in prompt
    assert "성공 시기를 보장하지 마세요" in prompt
    assert "`### 사주 근거와 운의 해석`" not in prompt
    assert "별도 근거 절로 나열하지 말고" in prompt


def test_career_focus_rejects_vague_encouragement_and_accepts_action_plan() -> None:
    request = request_with_concern("이직과 커리어 전환")
    vague_draft = (
        "이직은 삶의 에너지를 재설정하는 통과의례입니다. 차분히 마음을 들여다보고 "
        "조급함을 내려놓으면 새로운 기회가 자연스럽게 열릴 것입니다. " * 30
    )

    assert _focus_meets_contract(vague_draft, request) is False
    assert _focus_meets_contract(build_local_focus_section(request), request) is True


def test_local_ten_god_repair_is_substantial_and_uses_verified_roles() -> None:
    section = build_local_analysis("local-repair", request_data())["section_1_3"]

    assert len(section) >= 450
    assert len([block for block in section.split("\n\n") if block.strip()]) >= 5
    assert "### 한눈에 보는 핵심" not in section
    assert "### 지금 할 일" not in section
    assert section.endswith("**")
    brief = interpretation_brief(build_saju_profile(request_data()))
    from app.portraits import ROLE_NEEDS
    assert ROLE_NEEDS[brief["primary_role"]] in section
    assert ROLE_NEEDS[brief["secondary_role"]] in section


def test_special_calendar_is_based_on_daily_stem_ten_gods() -> None:
    special_dates = build_special_dates(
        request_data(),
        reference_date=date(2026, 4, 1),
    )

    assert len(special_dates) == 5
    assert all(item["kind"] == "saju_action" for item in special_dates)
    assert all(item["gan_zhi"] and item["ten_god"] for item in special_dates)
    assert special_dates[0]["ten_god"] in {"비견", "겁재"}
    assert special_dates[1]["ten_god"] in {"식신", "상관"}
    assert special_dates[2]["ten_god"] in {"편재", "정재"}
    assert special_dates[3]["ten_god"] in {"편관", "정관"}
    assert special_dates[4]["ten_god"] in {"편인", "정인"}


def test_chart_calculates_four_pillars_and_current_luck() -> None:
    profile = build_saju_profile(request_data(), reference_date=date(2026, 8, 14))

    assert [pillar["gan_zhi"] for pillar in profile["pillars"]] == [
        "庚午",
        "辛巳",
        "庚辰",
        "癸未",
    ]
    assert profile["day_master"]["label"] == "경금 일간"
    assert profile["element_counts"] == {"목": 0, "화": 2, "토": 2, "금": 3, "수": 1}
    assert profile["luck"]["current_decade"]["gan_zhi"] == "甲申"
    assert profile["luck"]["current_year"]["gan_zhi"] == "丙午"
    assert profile["luck"]["current_decade"]["transition_date"] == "2017-08-04"
    assert profile["luck"]["next_decade"]["gan_zhi"] == "乙酉"
    assert profile["luck"]["next_decade"]["transition_date"] == "2027-08-04"
    assert len(profile["luck"]["monthly_flow"]) == 12
    assert profile["analysis_scope"].startswith("간편형")
    assert "출생지 미입력" in profile["calculation_standard"]
    assert all(item["boundary_start"]["name"] for item in profile["luck"]["monthly_flow"])
    assert all("입절" in item["basis"] for item in profile["luck"]["monthly_flow"])


def test_decade_transition_uses_the_exact_change_date_not_january_first() -> None:
    request = request_data()

    before = build_saju_profile(request, reference_date=date(2027, 8, 3))
    after = build_saju_profile(request, reference_date=date(2027, 8, 4))

    assert before["luck"]["current_decade"]["gan_zhi"] == "甲申"
    assert after["luck"]["current_decade"]["gan_zhi"] == "乙酉"


def test_quick_summary_separates_saju_basis_from_user_context() -> None:
    request = request_with_concern("이직과 커리어 전환")
    sections = {"section_5_4": build_local_focus_section(request)}

    summary = build_quick_summary(request, sections)

    assert summary["confidence"] == "medium"
    assert len(summary["timing_windows"]) == 12
    assert any("현재 대운" in item for item in summary["saju_basis"])
    assert any("직접 입력한 고민" in item for item in summary["user_context_basis"])
    assert all(action["selection_reason"] for action in summary["actions"])
    assert all(action["saju_basis"] for action in summary["actions"])
    assert all(action["user_context_basis"] for action in summary["actions"])
    assert summary["answer_window"]["label"].endswith("30일 관찰")
    assert summary["good_signals"]
    assert summary["decision_changers"]


def test_scope_guard_rejects_single_health_and_finance_overreach() -> None:
    single = request_data()
    assert _chapter_scope_issues(
        "section_4_1",
        "솔로라서 단독으로 생계를 유지하고 시간적 여유가 있습니다.",
        single,
    )
    assert _chapter_scope_issues(
        "section_5_1",
        "극심한 두통과 정신적 소진을 겪습니다.",
        single,
    )
    assert _chapter_scope_issues(
        "section_3_4",
        "가처분소득의 30%를 비상금으로 두세요.",
        single,
    )
    assert not _chapter_scope_issues(
        "section_3_4",
        "예시 기준으로 30%가 보일 수 있지만 실제 가처분소득에 맞게 직접 바꾸세요.",
        single,
    )


def test_quick_summary_does_not_lead_with_a_generated_disclaimer() -> None:
    request = request_with_concern("이직과 커리어 전환")
    sections = {
        "section_5_4": "특정 회사의 합격 가능성을 판단할 수 없습니다. 먼저 시장을 확인하세요."
    }

    summary = build_quick_summary(request, sections)

    assert "재직 상태" in summary["direct_answer"]
    assert "판단할 수 없습니다" not in summary["direct_answer"]


def test_local_report_has_a_bounded_health_and_burnout_section() -> None:
    section = build_local_analysis("health", request_data())["section_5_1"]

    assert "수면" in section
    assert "의료기관" in section
    assert "의료 전문가의 진단이나 치료를 대체하지 않습니다" in section
    assert "발병 시기" in section


def test_branch_main_ten_gods_are_separate_from_hidden_stems_for_gi_earth() -> None:
    values = request_data().model_dump()
    values["birth_date"] = "1990-05-14"
    request = SajuRequest.model_validate(values)

    profile = build_saju_profile(request, reference_date=date(2026, 8, 14))

    assert profile["day_master"]["gan"] == "己"
    assert profile["ten_god_reference"]["branches"]["巳"]["main_stem"] == "丙"
    assert profile["ten_god_reference"]["branches"]["巳"]["main_ten_god"] == "정인"
    assert profile["ten_god_reference"]["branches"]["酉"]["main_stem"] == "辛"
    assert profile["ten_god_reference"]["branches"]["酉"]["main_ten_god"] == "식신"
    assert any(
        item["stem"] == "庚" and item["ten_god"] == "상관" and not item["is_main"]
        for item in profile["ten_god_reference"]["branches"]["巳"]["hidden_stems"]
    )


def test_domain_guard_rejects_wrong_branch_ten_gods_and_unverified_relations() -> None:
    values = request_data().model_dump()
    values["birth_date"] = "1990-05-14"
    request = SajuRequest.model_validate(values)

    assert _saju_domain_issues("巳火(상관) 기운이 강합니다.", request)
    assert _saju_domain_issues("酉金은 정재로 작용합니다.", request)
    assert _saju_domain_issues("巳와 巳는 합을 이룹니다.", request)
    assert not _saju_domain_issues(
        "巳의 본기 丙은 정인이고, 지장간 庚은 상관입니다.",
        request,
    )
    assert not _saju_domain_issues(
        "천간 己는 비견, 지지 巳의 본기 丙은 정인입니다.",
        request,
    )


def test_domain_guard_accepts_ten_god_for_the_stem_in_a_gan_zhi_label() -> None:
    values = request_data().model_dump()
    values["birth_date"] = "1990-05-14"
    request = SajuRequest.model_validate(values)

    assert not _saju_domain_issues("2026-09-15 · 壬辰 정재 행동일입니다.", request)
    assert _saju_domain_issues("지지 辰은 정재입니다.", request)


def test_timing_actions_do_not_leak_a_career_focus_into_chapter_four() -> None:
    request = request_with_concern("이직과 커리어 전환")
    timing_section = build_local_analysis("timing-scope", request)["section_4_2"]

    assert not _chapter_scope_issues("section_4_2", timing_section, request)
    assert not _saju_domain_issues(timing_section, request)


def test_prompt_isolates_focus_concern_and_mbti_by_chapter() -> None:
    request = request_with_concern("이직과 커리어 전환")

    assert "이직과 커리어 전환" not in _build_chapter_prompt(request, 2)
    assert "INFP" not in _build_chapter_prompt(request, 2).upper()
    assert "이직과 커리어 전환" not in _build_chapter_prompt(request, 4)
    assert "이직과 커리어 전환" in _build_chapter_prompt(request, 5)
    assert "십신 조견표" in _build_chapter_prompt(request, 1)
    assert "같은 지지의 중첩을 합이라고 부르지" in _build_chapter_prompt(request, 1)


def test_element_chart_uses_visible_counts_and_marks_month_command() -> None:
    summary = build_practical_summary(request_data(), {})

    assert [metric["value"] for metric in summary["chart"]] == [0, 2, 2, 3, 1]
    assert all(0 <= metric["bar_percent"] <= 100 for metric in summary["chart"])
    assert [metric["key"] for metric in summary["chart"] if metric["is_month_command"]] == ["화"]
    assert "강약 백분율" in summary["chart_note"]


def test_quality_guard_rejects_repeated_action_from_an_earlier_chapter() -> None:
    text = (
        "## 관계 흐름\n\n### 한눈에 보는 핵심\n\n관계의 흐름을 파악합니다. " * 8
        + "\n\n### 현실에서 보이는 신호\n\n말과 행동의 일치를 두 번 이상 확인합니다. " * 22
        + "\n\n### 지금 할 일\n\n- 14일 안에 판단표를 완성합니다.\n"
        + "- 만남 뒤 편안함을 세 문장으로 기록합니다.\n\n"
        + "> 한 번의 행동만으로 상대의 마음을 단정하지 않습니다."
    )

    issues = _quality_issues(
        {"section_2_1": text},
        ("section_2_1",),
        request_data(),
        {"section_1_1": "- 30일 안에 판단표를 완성합니다."},
    )

    assert issues == ["section_2_1"]


def test_unknown_birth_time_omits_time_pillar_and_marks_luck_start_estimated() -> None:
    values = request_data().model_dump()
    values.update(birth_time=None, birth_time_unknown=True)
    request = SajuRequest.model_validate(values)

    profile = build_saju_profile(request, reference_date=date(2026, 8, 14))

    assert [pillar["label"] for pillar in profile["pillars"]] == ["연주", "월주", "일주"]
    assert profile["missing_pillars"] == ["시주"]
    assert profile["luck"]["start"]["estimated"] is True

@pytest.mark.anyio
async def test_gemini_uses_header_auth_and_returns_all_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    captured: list[httpx.Request] = []
    progress: list[tuple[int, int]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=gemini_response(required_ids_from_request(request)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis(
            "task-1",
            request_data(),
            client=client,
            progress_callback=lambda completed, total: progress.append((completed, total)),
        )

    assert len(captured) == 5
    assert all(request.headers["x-goog-api-key"] == "test-secret-key" for request in captured)
    assert all("test-secret-key" not in str(request.url) for request in captured)
    request_bodies = [json.loads(request.content) for request in captured]
    assert [
        len(body["response_format"]["schema"]["required"])
        for body in request_bodies
    ] == [3, 3, 4, 3, 4]
    assert all(
        f"Chapter {index}" in body["input"]
        for index, body in enumerate(request_bodies, start=1)
    )
    assert all(body["store"] is False for body in request_bodies)
    assert all(body["model"] == "gemini-test" for body in request_bodies)
    assert all(request.url.path == "/v1beta/interactions" for request in captured)
    assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert result["generation_mode"] == "gemini_book"
    assert "model" not in result
    assert "requested_model" not in result
    assert "models_used" not in result
    assert all(result[section_id] for section_id in section_ids())


@pytest.mark.anyio
async def test_gemini_generates_focus_section_without_an_extra_api_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    captured: list[httpx.Request] = []
    focus_request = request_with_concern("연애와 새로운 만남")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        required_ids = required_ids_from_request(request)
        payload = gemini_response(required_ids)
        if "section_5_5" in required_ids:
            content = json.loads(payload["steps"][0]["content"][0]["text"])
            content["section_5_5"] = build_local_focus_section(focus_request)
            payload["steps"][0]["content"][0]["text"] = json.dumps(content)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis(
            "task-focus",
            focus_request,
            client=client,
        )

    assert len(captured) == 5
    required_per_chapter = [required_ids_from_request(request) for request in captured]
    assert [len(required) for required in required_per_chapter[:4]] == [3, 3, 4, 3]
    assert required_per_chapter[4][-2:] == ("section_5_5", "section_5_4")
    assert len(required_per_chapter[4]) == 5
    assert result["section_5_5"]
    assert result["user_data"]["focus_concern"] == "연애와 새로운 만남"
    last_sections = result["table_of_contents"]["chapters"][4]["sections"]
    assert last_sections[-2]["id"] == "section_5_5"
    assert last_sections[-1]["id"] == "section_5_4"
    assert "연애와 새로운 만남" in last_sections[-2]["title"]


@pytest.mark.anyio
async def test_gemini_retries_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0"},
                json={"error": {"message": "rate limited"}},
            )
        return httpx.Response(200, json=gemini_response(required_ids_from_request(request)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis("task-2", request_data(), client=client)

    assert attempts == 6
    assert result["generation_mode"] == "gemini_book"


@pytest.mark.anyio
async def test_gemini_keeps_best_ai_draft_when_only_soft_quality_target_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        required = required_ids_from_request(request)
        sections = {
            section_id: (
                "권장 분량보다 짧지만 확인할 질문과 행동이 있는 AI 원고입니다.\n\n"
                "### 한눈에 보는 핵심\n\n현재 방식이 잘 맞는지 실제 경험으로 확인합니다. "
                "상황이 다르다면 설명을 억지로 적용하지 않고 자신의 경험을 우선하세요.\n\n"
                "### 현실에서 보이는 신호\n\n원하는 결과가 나왔던 때와 그렇지 않았던 때를 비교합니다. "
                "같은 행동이라도 사용할 수 있는 시간과 도움에 따라 다를 수 있습니다. "
                "실행 결과에서 달라진 조건을 찾아 다음 판단에 반영하세요.\n\n"
                f"### 지금 할 일\n\n1. {DISTINCT_SECTION_ACTIONS[section_id][0]}\n"
                f"2. {DISTINCT_SECTION_ACTIONS[section_id][1]}"
            )
            for section_id in required
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "status": "done",
                        "content": [{"type": "text", "text": json.dumps(sections)}],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis("task-soft-quality", request_data(), client=client)

    assert attempts == 15
    assert result["generation_mode"] == "gemini_book"
    assert len(result["quality_warnings"]) == 5
    assert all(result[section_id] for section_id in section_ids())
    assert "권장 분량보다 짧지만" in result["section_1_1"]


@pytest.mark.anyio
async def test_gemini_repairs_only_a_persistently_short_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        required = required_ids_from_request(request)
        payload = gemini_response(required)
        if "section_1_3" in required:
            sections = json.loads(payload["steps"][0]["content"][0]["text"])
            sections["section_1_3"] = "십신 설명이 너무 짧습니다."
            payload["steps"][0]["content"][0]["text"] = json.dumps(sections)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis(
            "task-section-repair",
            request_data(),
            client=client,
        )

    assert attempts == 7
    assert result["generation_mode"] == "gemini_book"
    assert len(result["section_1_3"]) >= 450
    assert "겉으로 보이는 행동과 혼자 있을 때의 생각" in result["section_1_3"]
    assert "계산된 흐름의 핵심" in result["section_1_1"]
    assert "section_1_3" in " ".join(result["quality_warnings"])


@pytest.mark.anyio
async def test_gemini_repairs_a_short_timing_chapter_without_losing_other_ai_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    attempts = 0
    career_request = request_with_concern("이직과 커리어 전환")

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        required = required_ids_from_request(request)
        payload = gemini_response(required)
        if "section_5_1" in required:
            sections = json.loads(payload["steps"][0]["content"][0]["text"])
            for section_id in required:
                sections[section_id] = "운의 흐름을 설명한 짧은 초안입니다."
            payload["steps"][0]["content"][0]["text"] = json.dumps(sections)
        elif "section_5_5" in required:
            sections = json.loads(payload["steps"][0]["content"][0]["text"])
            sections["section_5_5"] = build_local_focus_section(career_request)
            payload["steps"][0]["content"][0]["text"] = json.dumps(sections)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis(
            "task-timing-repair",
            career_request,
            client=client,
        )

    assert attempts == 7
    assert result["generation_mode"] == "gemini_book"
    assert "내 생활 리듬" in result["section_5_1"]
    assert "계산된 흐름의 핵심" in result["section_3_1"]
    assert "section_5_1" in " ".join(result["quality_warnings"])


@pytest.mark.anyio
async def test_gemini_switches_model_after_primary_high_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite")
    requested_models: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        requested_models.append(model)
        if model == "gemini-3.6-flash":
            return httpx.Response(
                503,
                json={"error": {"message": "This model is currently experiencing high demand."}},
            )
        return httpx.Response(200, json=gemini_response(required_ids_from_request(request)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis("task-failover", request_data(), client=client)

    assert "gemini-3.6-flash" in requested_models
    assert "gemini-3.5-flash-lite" in requested_models
    assert requested_models.count("gemini-3.5-flash-lite") == 5
    assert result["generation_mode"] == "gemini_book"
    assert "requested_model" not in result
    assert "model" not in result
    assert "models_used" not in result


@pytest.mark.anyio
async def test_gemini_switches_model_when_primary_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite")
    requested_models: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        requested_models.append(model)
        if model == "gemini-2.5-flash":
            return httpx.Response(
                404,
                json={
                    "error": {
                        "message": "This model is no longer available to new users."
                    }
                },
            )
        return httpx.Response(200, json=gemini_response(required_ids_from_request(request)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_gemini_analysis("task-unavailable", request_data(), client=client)

    assert "gemini-2.5-flash" in requested_models
    assert "gemini-3.5-flash-lite" in requested_models
    assert requested_models.count("gemini-3.5-flash-lite") == 5
    assert result["generation_mode"] == "gemini_book"
    assert "requested_model" not in result
    assert "model" not in result
    assert "models_used" not in result


def test_korean_gan_zhi_readings_in_prompt_and_profile() -> None:
    req = request_data()
    profile = build_saju_profile(req)

    # Verify profile includes Korean readings
    for pillar in profile["pillars"]:
        assert "gan_zhi_ko" in pillar
        assert "gan_ko" in pillar
        assert "zhi_ko" in pillar

    current_decade = profile["luck"]["current_decade"]
    if current_decade:
        assert "gan_zhi_ko" in current_decade

    prompt = _build_chapter_prompt(req, 1)
    # Check that Korean GanZhi readings are present in context
    assert "庚午(경오)" in prompt or "(경오)" in prompt
    # Check that Hanja prohibition is explicitly stated in prompt rules
    assert "한자(漢字)는 일절 쓰지 마세요" in prompt
    assert "한자(漢字)는 절대 쓰지 마세요" in prompt
