from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re

from .models import SajuRequest
from .saju import TEN_GOD_SHADOWS, build_saju_profile, build_saju_special_dates
from .content import ROLE_LENSES, action_plan, interpretation_brief
from .narrative import narrative_moments
from .portraits import ROLE_PORTRAITS


@dataclass(frozen=True)
class SectionDefinition:
    section_id: str
    title: str


CHAPTERS: tuple[tuple[int, str, tuple[SectionDefinition, ...]], ...] = (
    (
        1,
        "타고난 기질과 세상이 보는 나",
        (
            SectionDefinition("section_1_1", "태어날 때부터 지닌 본연의 기운"),
            SectionDefinition("section_1_2", "세상과 사람들이 바라보는 나"),
            SectionDefinition("section_1_3", "겉으로 보이는 행동과 혼자 있을 때의 생각"),
        ),
    ),
    (
        2,
        "지금의 흐름과 선택을 점검하기",
        (
            SectionDefinition("section_2_1", "지금 확인할 흐름과 진행 조건"),
            SectionDefinition("section_2_2", "반복되는 상황과 조정할 수 있는 조건"),
            SectionDefinition("section_2_3", "나의 강점을 활용하는 작은 전환"),
        ),
    ),
    (
        3,
        "일과 재물이 풀리는 전략적 방향",
        (
            SectionDefinition("section_3_1", "나는 어떤 환경에서 일해야 가장 빛날까?"),
            SectionDefinition("section_3_2", "내 고유한 재능이 성과와 돈으로 바뀌는 순간"),
            SectionDefinition("section_3_3", "버텨야 할 타이밍과 과감히 움직여야 할 타이밍"),
            SectionDefinition("section_3_4", "들어온 돈을 지키는 흐름과 관리 습관"),
        ),
    ),
    (
        4,
        "나를 채워주는 관계와 환경의 힘",
        (
            SectionDefinition("section_4_1", "마음이 열리는 순간과 나의 표현 방식"),
            SectionDefinition("section_4_2", "앞으로 내 삶에 들어올 좋은 인연의 신호"),
            SectionDefinition("section_4_3", "나를 살려주는 공간 에너지와 일상 정돈법"),
        ),
    ),
    (
        5,
        "일상의 회복과 90일 실행 계획",
        (
            SectionDefinition("section_5_1", "내 생활 리듬과 회복을 돕는 쉼 루틴"),
            SectionDefinition("section_5_2", "앞으로 3개월, 내가 주목해야 할 월별 타이밍"),
            SectionDefinition("section_5_3", "선택한 변화를 이어가는 90일 실행 계획"),
            SectionDefinition("section_5_4", "나만의 속도로 나아가기 위한 마지막 제언"),
        ),
    ),
)

FOCUS_SECTION = SectionDefinition("section_5_5", "지금 가장 궁금한 이야기")

FOCUS_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "career": ("이직", "취업", "직장", "커리어", "퇴사", "직무", "승진", "사업"),
    "relationship": ("연애", "사랑", "결혼", "만남", "소개팅", "재회", "이별", "배우자", "남편", "아내", "부부", "이혼", "연인"),
    "money": ("돈", "재물", "투자", "부업", "금전", "수입", "지출", "빚", "대출", "저축"),
    "study": ("공부", "시험", "수험", "학업", "진학", "자격증"),
    "health": ("건강", "몸 상태", "증상", "불면", "번아웃", "진단", "질병", "불안장애"),
    "family": ("가족", "부모", "자녀", "육아", "엄마", "아빠", "형제"),
}

RELATIONSHIP_SECTION_TITLES: dict[str, dict[str, str]] = {
    "single": {
        "section_4_1": "어떤 대화에서 마음이 열리고 가까워질까?",
        "section_4_2": "새로운 인연을 알아채는 기회 신호",
        "section_4_3": "나를 살려주는 공간 에너지와 일상 정돈법",
    },
    "dating": {
        "section_4_1": "연인 관계에서 반복되는 나의 소통 패턴",
        "section_4_2": "두 사람의 애정을 깊게 만드는 긍정 신호",
        "section_4_3": "함께 머무는 공간 에너지와 일상 정돈법",
    },
    "married": {
        "section_4_1": "부부 생활에서 마주하는 현실적인 상호작용 패턴",
        "section_4_2": "함께 삶을 가꾸어가는 든든한 동반자 신호",
        "section_4_3": "가정의 안정감을 높이는 공간 에너지와 정돈법",
    },
}

TIMING_SECTION_TITLES = {
    "section_5_1": "내 생활 리듬과 회복을 돕는 쉼 루틴",
    "section_5_2": "앞으로 3개월, 내가 주목해야 할 월별 타이밍",
    "section_5_3": "선택한 변화를 이어가는 90일 실행 계획",
    "section_5_4": "나만의 속도로 나아가기 위한 마지막 제언",
}


def section_title_for_request(section: SectionDefinition, request: SajuRequest) -> str:
    if section.section_id == FOCUS_SECTION.section_id and request.focus_concern:
        normalized = re.sub(r"\s+", " ", request.focus_concern).strip()
        short_topic = normalized if len(normalized) <= 22 else f"{normalized[:22].rstrip()}…"
        return f"{short_topic} · 추가 해석"
    relationship_title = RELATIONSHIP_SECTION_TITLES.get(
        request.relationship_status,
        {},
    ).get(section.section_id)
    if relationship_title:
        return relationship_title
    return TIMING_SECTION_TITLES.get(section.section_id, section.title)


def chapter_sections_for_request(
    request: SajuRequest,
    chapter_number: int,
) -> tuple[SectionDefinition, ...]:
    for number, _, chapter_sections in CHAPTERS:
        if number != chapter_number:
            continue
        if number == 5 and request.focus_concern:
            return (*chapter_sections[:-1], FOCUS_SECTION, chapter_sections[-1])
        return chapter_sections
    return ()


def section_ids(request: SajuRequest | None = None) -> list[str]:
    """Return all section IDs in logical book order."""
    ids: list[str] = []
    for chapter_number, _, chapter_sections in CHAPTERS:
        if request:
            for section in chapter_sections_for_request(request, chapter_number):
                ids.append(section.section_id)
        else:
            for section in chapter_sections:
                ids.append(section.section_id)
    return ids


def focus_domain_for_request(request: SajuRequest) -> str:
    concern = (request.focus_concern or "").lower()
    scores = {domain: sum(len(keyword) for keyword in keywords if keyword in concern)
              for domain, keywords in FOCUS_DOMAIN_KEYWORDS.items()}
    return max(scores, key=scores.get) if any(scores.values()) else "general"


def build_local_focus_section(request: SajuRequest) -> str:
    """Use the same domain and relationship plan as the summary and paid report."""
    from .content import local_focus_section

    return local_focus_section(request, build_saju_profile(request))


def build_special_dates(
    request: SajuRequest,
    *,
    reference_date: date | None = None,
    profile: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    """Expose the five calculated daily-stem action dates used by the report."""

    return build_saju_special_dates(request, reference_date=reference_date, profile=profile)


TEN_GOD_INTUITIVE_LABELS = {role: lens[0] for role, lens in ROLE_LENSES.items()}
TEN_GOD_STRENGTHS = {
    role: f"{lens[1]}에서 {lens[2]} 확인해볼 수 있습니다."
    for role, lens in ROLE_LENSES.items()
}
TEN_GOD_WATCHOUTS = TEN_GOD_SHADOWS


def build_quick_summary(
    request: SajuRequest,
    sections: dict[str, str],
    profile: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a transparent 60-second summary from calculated and supplied facts."""

    active_profile = profile or build_saju_profile(request)
    day_master = active_profile["day_master"]
    luck = active_profile["luck"]
    current_decade = luck.get("current_decade")
    next_decade = luck.get("next_decade")
    monthly_flow = list(luck.get("monthly_flow") or [])

    brief = interpretation_brief(active_profile)
    plan = action_plan(request, active_profile)
    leading_roles = brief["leading_roles"]

    domain = focus_domain_for_request(request)
    # The first answer must stay direct and structurally stable even when a generated
    # focus chapter starts with a disclaimer or an essay-style introduction.
    direct_answer = plan["direct_answer"]

    current_luck = "현재의 긴 흐름을 계산하지 못했습니다."
    if current_decade:
        current_theme = TEN_GOD_INTUITIVE_LABELS.get(
            current_decade["stem_ten_god"],
            "익숙한 역할을 다시 살피는 힘",
        )
        current_luck = (
            f"{current_decade['transition_date']}부터 {current_decade['end_date']}까지는 "
            f"‘{current_theme}’이 생활에서 어떻게 나타나는지 살펴보는 시기입니다."
        )
    if next_decade:
        next_theme = TEN_GOD_INTUITIVE_LABELS.get(
            next_decade["stem_ten_god"],
            "새로운 역할을 시험하는 힘",
        )
        current_luck += (
            f" {next_decade['transition_date']}부터는 ‘{next_theme}’을 확인하는 다음 시기로 넘어갑니다."
        )

    relationship_label = {
        "single": "솔로",
        "dating": "연애 중",
        "married": "기혼",
    }[request.relationship_status]
    user_basis = [f"현재 관계 상태: {relationship_label}"]
    if request.focus_concern:
        user_basis.insert(0, f"직접 입력한 고민: {request.focus_concern}")
    if request.mbti:
        user_basis.append(f"선택 입력 MBTI: {request.mbti.upper()} (명리 근거와 분리해 참고)")

    saju_basis = [
        f"일간: {day_master['label']} · {day_master['archetype']}",
        f"월령: {active_profile['month_command']['label']}",
    ]
    if current_decade:
        saju_basis.append(
            f"현재 대운: {current_decade['gan_zhi']} · 천간 {current_decade['stem_ten_god']} · "
            f"지지 본기 {current_decade['branch_main_ten_god']}"
        )
    if next_decade:
        saju_basis.append(
            f"다음 대운: {next_decade['gan_zhi']} · {next_decade['transition_date']} 교운"
        )

    special_dates = build_special_dates(request, profile=active_profile)
    context_domain = domain if domain in {"career", "relationship", "money"} else "general"
    action_user_context = {
        "career": "입력한 커리어 고민을 바로 퇴사 결론으로 연결하지 않고, 비교·대화·검증 행동으로 좁혔습니다.",
        "relationship": "입력한 관계 고민과 현재 관계 상태를 바탕으로, 상대를 단정하지 않고 대화·경계 확인 행동으로 좁혔습니다.",
        "money": "입력한 재물 고민을 수익 예측으로 바꾸지 않고, 현금 흐름과 감당 가능한 범위를 확인하는 행동으로 좁혔습니다.",
        "general": "입력한 고민에서 확인 가능한 과제를 골랐습니다." if request.focus_concern else "별도 고민이 입력되지 않아 생활 사례로 해석을 확인하는 과제를 제안했습니다.",
    }[context_domain]
    verification_questions = {
        "career": [
            "현재 불만은 회사·직무·업무량 중 어디에서 반복되나요?",
            "다음 선택을 바꿀 실제 정보는 무엇인가요?",
        ],
        "relationship": [
            "말보다 반복해서 확인되는 행동은 무엇인가요?",
            "내 경계가 존중된다고 느낀 장면이 있었나요?",
        ],
        "money": [
            "최근 석 달 동안 실제로 남은 돈은 얼마인가요?",
            "결론을 바꿀 수 있는 최대 손실은 어느 정도인가요?",
        ],
        "general": [
            "이 해석 중 실제 생활과 맞는 부분은 무엇인가요?",
            "다르거나 아직 잘 모르겠는 부분은 무엇인가요?",
        ],
    }[context_domain]
    answer_window_start = date.fromisoformat(active_profile["reference_date"])
    answer_window_end = answer_window_start + timedelta(days=29)
    good_signals = {
        "career": ["원하는 역할을 한 문장으로 설명할 수 있음", "시장 대화에서 현재 경험의 쓸모가 반복 확인됨", "생활 조건을 해치지 않는 제안이 생김"],
        "relationship": ["말과 행동이 반복해서 일치함", "질문과 관심이 한쪽으로 치우치지 않음", "개인 시간과 거절의 경계를 존중함"],
        "money": ["목적·비용·중단 조건을 설명할 수 있음", "실제 현금 흐름 안에서 감당 가능함", "조급함 없이 다시 검토할 수 있음"],
        "general": ["확인한 사실이 추측보다 늘어남", "되돌릴 수 있는 작은 시도를 마침", "결정 뒤 생활 리듬이 유지됨"],
    }[context_domain]
    decision_changers = {
        "career": ["현재 직무·연차", "목표 역할과 필수 조건", "소득 공백을 감당할 개월 수"],
        "relationship": ["현재 관계 상태", "반복되는 갈등 장면", "지키고 싶은 경계"],
        "money": ["실제 가처분소득", "월 고정 지출", "원금 손실 감당 한도"],
        "general": ["가장 에너지를 많이 쓰는 장면", "이번 달 바꾸고 싶은 한 가지", "거절하고 싶은 요청"],
    }[context_domain]

    quick_actions = plan["actions"]

    strengths = [
        f"{TEN_GOD_INTUITIVE_LABELS.get(role, role)}: {TEN_GOD_STRENGTHS.get(role, '')}"
        for role in leading_roles
        if role in TEN_GOD_STRENGTHS
    ]
    if not strengths:
        strengths = [f"기질의 중심: {day_master.get('archetype', '자기 신뢰와 독립적 실행력')}"]

    watchouts = [
        f"{TEN_GOD_INTUITIVE_LABELS.get(role, role)}: {TEN_GOD_WATCHOUTS.get(role, '')}"
        for role in leading_roles
        if role in TEN_GOD_WATCHOUTS
    ]
    if not watchouts:
        watchouts = ["내면의 긴장: 과도한 완벽주의로 스스로를 소진시키는 패턴"]

    one_line = brief["one_line"]
    portrait_title, _, portrait_closing = narrative_moments(brief["primary_role"])["section_1_1"]

    return {
        "direct_answer": direct_answer,
        "current_luck": current_luck,
        "confidence": "medium" if active_profile["time_known"] else "low",
        "confidence_note": "출생 시간 입력 범위의 표시이며 예측 정확도나 해석의 확률이 아닙니다.",
        "strengths": strengths,
        "watchouts": watchouts,
        "one_line": one_line,
        "self_portrait": {
            "headline": portrait_title,
            "body": ROLE_PORTRAITS[brief["primary_role"]][0],
            "scene": ROLE_PORTRAITS[brief["primary_role"]][1],
            "closing": portrait_closing,
        },
        "saju_basis": saju_basis,
        "user_basis": user_basis,
        "user_context_basis": user_basis,
        "leading_roles": leading_roles,
        "special_dates": special_dates,
        "action_user_context": action_user_context,
        "verification_questions": verification_questions,
        "answer_window": {
            "label": f"{answer_window_start.strftime('%Y년 %m월')} ~ {answer_window_end.strftime('%m월')} 30일 관찰",
            "start": answer_window_start.isoformat(),
            "end": answer_window_end.isoformat(),
        },
        "answer_window_start": answer_window_start.isoformat(),
        "answer_window_end": answer_window_end.isoformat(),
        "good_signals": good_signals,
        "decision_changers": decision_changers,
        "timing_windows": monthly_flow,
        "actions": quick_actions,
    }


ELEMENT_MEANINGS: dict[str, str] = {
    "목": "시작하고 기획하며 확장하는 추진력",
    "화": "표현하고 확산하며 열정을 발휘하는 힘",
    "토": "중심을 잡고 신뢰를 다지며 포용하는 힘",
    "금": "결단하고 정돈하며 원칙을 지키는 힘",
    "수": "유연하게 흐르고 깊이 통찰하며 지혜를 모으는 힘",
}


def build_practical_summary(
    request: SajuRequest,
    sections: dict[str, str],
    quick_summary: dict[str, object] | None = None,
    profile: dict[str, object] | None = None,
) -> dict[str, object]:
    profile = profile or build_saju_profile(request)
    active_summary = quick_summary or build_quick_summary(request, sections, profile)
    day_master = profile["day_master"]
    day_archetype = day_master.get("archetype", "기질의 중심")
    type_label = f"{day_master['reading']}{day_master['element']} · {day_archetype}"
    element_hanja = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}
    role_traits = [
        TEN_GOD_INTUITIVE_LABELS.get(role, role)
        for role in list(active_summary.get("leading_roles") or [])[:3]
    ]
    if not role_traits:
        role_traits = ["자기 기준", "현실 점검", "작은 실행"]
    quick_actions = list(active_summary.get("actions") or [])
    first_strength = str((active_summary.get("strengths") or ["나만의 강점"])[0])
    one_line = str(active_summary.get("one_line") or f"{day_master['label']}의 기질이 중심이 됩니다.")

    max_count = max(1, max(profile["element_counts"].values()))
    element_chart = [
        {
            "key": elem,
            "element": elem,
            "label": f"{elem} · {element_hanja.get(elem, elem)}",
            "count": count,
            "value": count,
            "bar_percent": int(round((count / max_count) * 100)),
            "is_month_command": elem == profile["month_command"]["element"],
            "element_meaning": ELEMENT_MEANINGS.get(elem, ""),
        }
        for elem, count in profile["element_counts"].items()
    ]

    action_cards = quick_actions or action_plan(request, profile)["actions"]

    social_summary = f"나는 {type_label}입니다. {one_line}"
    hashtags = ["#나의결", f"#{day_master['reading']}{day_master['element']}", "#90일실행나침반"]
    social_profile = {
        "headline": f"나의 결 | {type_label}",
        "title": f"나의 결 | {type_label}",
        "summary": social_summary,
        "hashtags": hashtags,
        "share_text": (
            f"[나의 결 요약]\n"
            f"• 타고난 기질: {type_label}\n"
            f"• 핵심 강점: {first_strength}\n"
            f"• 3개월 실천 테마: 선택한 변화를 이어가는 90일 실행 계획\n"
            + " ".join(hashtags)
        ),
    }

    return {
        "type": {
            "label": type_label,
            "element": day_master["element"],
            "summary": f"{day_master['label']}의 기운을 바탕으로 주도적인 삶의 전략을 설계합니다.",
            "tagline": one_line,
            "traits": role_traits,
        },
        "chart": element_chart,
        "chart_note": f"명식에 나타난 {profile['element_count_total']}글자 오행 분포이며, 강약 백분율이나 길흉 점수로 환산하지 않습니다.",
        "actions": action_cards,
        "social_profile": social_profile,
    }


def build_analysis_result(
    task_id: str,
    request: SajuRequest,
    sections: dict[str, str],
    *,
    generation_mode: str = "gemini_book",
    profile: dict[str, object] | None = None,
) -> dict[str, object]:
    """Assemble the stable response shape consumed by the frontend."""

    saju_profile = profile or build_saju_profile(request)

    table_of_contents = {
        "chapters": [
            {
                "chapter": chapter_number,
                "title": chapter_title,
                "sections": [
                    {
                        "id": section.section_id,
                        "title": section_title_for_request(section, request),
                    }
                    for section in chapter_sections_for_request(request, chapter_number)
                ],
            }
            for chapter_number, chapter_title, chapter_sections in CHAPTERS
        ]
    }

    quick_summary = build_quick_summary(request, sections, saju_profile)
    result: dict[str, object] = {
        "task_id": task_id,
        "user_data": {
            "name": request.name,
            "mbti": request.mbti,
            "relationship_status": request.relationship_status,
            "focus_concern": request.focus_concern,
        },
        "generation_mode": generation_mode,
        "saju_profile": saju_profile,
        "special_dates": quick_summary["special_dates"],
        "quick_summary": quick_summary,
        "practical_summary": build_practical_summary(request, sections, quick_summary, saju_profile),
        "table_of_contents": table_of_contents,
        **sections,
    }
    return result


def build_local_analysis(
    task_id: str,
    request: SajuRequest,
    *,
    generation_mode: str = "local_template",
) -> dict[str, object]:
    """Build a chart-specific report using the same editorial plan as the AI."""
    from .content import local_sections

    profile = build_saju_profile(request)
    sections = local_sections(request, profile)
    if request.focus_concern:
        sections[FOCUS_SECTION.section_id] = build_local_focus_section(request)
    return build_analysis_result(
        task_id, request, sections, generation_mode=generation_mode, profile=profile,
    )
