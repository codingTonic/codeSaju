"""Shared editorial decisions for the AI brief, local report and summary cards."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import re
from typing import Any

from .models import SajuRequest
from .saju import TEN_GOD_SHADOWS
from .narrative import narrative_moments
from .portraits import ROLE_PORTRAITS, role_interplay


# These are interpretive lenses, not psychometric scores or predictions.
ROLE_LENSES = {
    "비견": ("자기 주도성", "목표와 방법을 직접 정할 여지가 있는 환경", "스스로 시작한 일에서 진행 속도가 붙는지", "진행 중인 일의 결정권과 도움받을 부분을 각각 한 줄로 정리하세요."),
    "겁재": ("협력과 경쟁", "역할과 기여 기준이 공개된 협업 환경", "동료와 함께할 때 의욕이 높아지는지", "함께하는 일 하나의 담당자와 비용 분담 조건을 확인하세요."),
    "식신": ("꾸준한 완성", "반복해서 만들고 실제 반응을 확인할 수 있는 환경", "작은 결과물을 꾸준히 완성할 때 만족이 남는지", "이미 배운 것으로 작은 결과물 하나를 완성해 사용 반응을 받아보세요."),
    "상관": ("개선과 표현", "문제 제기와 작은 실험을 허용하는 환경", "비효율을 고친 제안이 실제로 받아들여지는지", "불편한 절차 하나를 골라 문제와 대안을 한 문장씩 작성하세요."),
    "편재": ("기회의 연결", "다양한 사람과 자원을 연결하되 범위를 정할 수 있는 환경", "새 제안을 연결한 뒤 유지 비용까지 챙기는지", "관심 있는 제안 하나의 기대 효과와 시간 비용을 나란히 적으세요."),
    "정재": ("현실적인 관리", "비용과 마감, 결과 기준이 명확한 환경", "계획과 실제 사용한 자원을 비교할 때 판단이 쉬워지는지", "반복해서 쓰는 시간이나 비용 하나의 계획과 실제 차이를 확인하세요."),
    "편관": ("책임과 결단", "어려운 과제에 권한과 지원이 함께 주어지는 환경", "책임이 분명한 과제를 처리한 뒤 회복할 여유가 남는지", "책임이 큰 요청 하나의 수락 조건과 지원 요청을 적으세요."),
    "정관": ("약속과 신뢰", "평가 기준과 약속이 일관된 환경", "역할이 명확해졌을 때 마음이 편해지는지", "모호한 약속 하나의 완료 기준과 서로의 책임을 확인하세요."),
    "편인": ("탐색과 재해석", "낯선 문제를 탐색한 뒤 검증할 기회가 있는 환경", "새 관점이 실제 문제 해결로 이어지는지", "아직 확인되지 않은 가설 하나를 사실과 추측으로 나누세요."),
    "정인": ("배움과 정리", "질문과 학습, 피드백을 활용할 수 있는 환경", "배운 내용을 설명할 때 이해가 깊어지는지", "최근 배운 개념 하나를 자신의 사례를 넣어 세 문장으로 설명하세요."),
}


def interpretation_brief(profile: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for pillar in profile["pillars"]:
        # The day stem is the reference point, not another personality role.
        if pillar["key"] != "day" and pillar["stem_ten_god"] in ROLE_LENSES:
            counts[pillar["stem_ten_god"]] += 1
        if pillar["branch_main_ten_god"] in ROLE_LENSES:
            counts[pillar["branch_main_ten_god"]] += 1
    month_role = profile["month_command"]["main_ten_god"]
    roles = sorted(counts, key=lambda role: (-counts[role], role != month_role, list(ROLE_LENSES).index(role)))[:3]
    primary = roles[0]
    secondary = roles[1] if len(roles) > 1 else primary
    label, environment, signal, action = ROLE_LENSES[primary]
    return {
        "leading_roles": roles,
        "primary_role": primary,
        "secondary_role": secondary,
        "label": label,
        "environment": environment,
        "signal": signal,
        "action": action,
        "question": TEN_GOD_SHADOWS[primary],
        "one_line": f"{profile['day_master']['archetype']}의 상징을 중심으로, {label}을 어떻게 쓰는지 살펴보는 명식입니다.",
        "interaction": (
            f"{label}과 {ROLE_LENSES[secondary][0]}을 함께 살펴보세요. "
            f"{environment}에서 {signal} 확인하고, "
            "잘 맞지 않는다면 능력의 결핍으로 보지 말고 경험과 환경의 차이를 먼저 확인합니다."
        ),
        "basis_note": "일간을 제외한 천간 십신과 지지 본기의 등장 횟수로 관찰 순서를 정했습니다. 동률이면 월지 본기를 먼저 참고하며 성격 강도나 길흉 점수는 아닙니다.",
    }


def action_plan(request: SajuRequest, profile: dict[str, Any]) -> dict[str, Any]:
    from .analysis import focus_domain_for_request

    domain = focus_domain_for_request(request)
    brief = interpretation_brief(profile)
    relationship = {
        "single": ("새로운 만남을 원한다면 접점을 하나 만들어보되, 관계를 정할 때는 상호 관심과 경계 존중을 함께 확인하세요.", "원하는 관계의 조건과 지킬 경계를 각각 세 가지 적으세요.", "부담이 적은 만남을 한 번 제안하고 상대가 자신의 의사를 존중하는지 관찰하세요."),
        "dating": ("현재 연인과 바꾸고 싶은 장면 하나를 정하고, 서로 수용할 수 있는 합의를 실제로 지키는지 확인하세요.", "최근 연인과 편했던 장면과 조율이 필요했던 장면을 하나씩 적으세요.", "연인에게 관찰한 사실·내 느낌·구체적 부탁을 한 문장씩 말하고 서로 가능한 합의 하나를 정하세요."),
        "married": ("배우자와 생활의 부담과 기대를 구체적으로 나누고, 서로에게 지속 가능한 합의인지 점검하세요.", "함께 조정하고 싶은 일정·생활비·집안일 중 한 가지를 선택하세요.", "배우자와 담당·빈도·부담을 확인하고 두 사람 모두 수용할 수 있는 조정 하나를 정하세요."),
    }[request.relationship_status]
    plans = {
        "career": (
            "재직 상태라면 원하는 역할과 조건을 현재 자리에서 조정할 수 있는지 확인하고, 구직 중이라면 경험과 모집 요건을 대조한 뒤 다음 지원을 정하세요.",
            "원하는 업무, 꼭 필요한 조건, 피하고 싶은 조건을 각각 한 줄로 적으세요.",
            "관심 있는 역할의 실제 사례 세 건과 자신의 경험을 비교해, 이미 설명할 수 있는 역량과 더 확인할 항목을 나누세요.",
            "지원이나 역할 조정의 반응을 비교해 유지·추가 탐색·전환 중 하나를 선택하고 다음 검토일을 정하세요.",
            "section_3_3",
        ),
        "relationship": (*relationship, "합의나 만남 뒤의 경험을 비교하고, 상호성·편안함·경계 존중을 기준으로 관계의 다음 속도를 정하세요.", "section_4_1"),
        "money": (
            "수익 전망에 앞서 실제 현금 흐름과 필요한 지출을 확인하고, 감당할 수 있는 범위 안에서 선택지를 비교하세요.",
            "최근 한 달의 수입과 필수 지출을 같은 표에 적어 실제로 남는 돈을 확인하세요.",
            "최근 석 달의 반복 지출에서 유지할 항목과 조정할 항목을 구분하고 계약 조건을 확인하세요.",
            "변경한 지출의 실제 효과를 확인하고, 새 선택은 비용·투입 시간·중단 조건이 적힌 경우에만 검토하세요.",
            "section_3_4",
        ),
        "study": (
            "성공 시기를 정하기보다 현재 실력과 목표 사이에서 확인 가능한 과제 하나를 골라 학습 방법을 시험하세요.",
            "목표와 관련된 문제나 과제 하나를 풀고 막힌 이유를 적으세요.",
            "같은 유형의 과제를 다시 수행해 이해 부족과 연습 부족을 구분하세요.",
            "수행 기록을 비교해 효과가 있었던 학습 방식 하나와 수정할 방식 하나를 정하세요.",
            "section_5_5",
        ),
        "health": (
            "몸 상태에 대한 고민은 사주로 원인을 정하지 말고 실제 변화와 생활 기록을 확인해 필요한 도움을 정하세요.",
            "궁금한 몸 상태의 변화와 시작 시점, 전문가에게 확인할 질문을 적으세요.",
            "실제 불편이 지속된다면 의료 전문가와 상담하고, 생활에서 조정 가능한 부담 한 가지를 확인하세요.",
            "전문가의 안내와 실제 생활 변화를 기준으로 계획을 조정하세요.",
            "section_5_1",
        ),
        "family": (
            "가족의 마음을 추측하기보다 반복되는 상황과 각자의 책임을 구분하고, 지킬 수 있는 합의 하나를 확인하세요.",
            "가족과 조율하고 싶은 상황에서 관찰한 사실과 바라는 변화를 각각 한 줄로 적으세요.",
            "안전하게 대화할 수 있는 경우, 맡을 수 있는 역할과 어려운 역할을 구분해 전달하세요.",
            "합의 이후 부담이 실제로 나뉘었는지 확인하고 맡는 역할을 다시 조정하세요.",
            "section_5_5",
        ),
        "general": (
            f"{brief['label']}을 활용할 수 있는 작은 과제를 하나 선택하고, 실행 뒤 실제 반응으로 다음 선택을 정하세요.",
            brief["action"],
            f"이번 주에 {brief['signal']} 보여주는 장면과 반대 장면을 하나씩 기록하세요.",
            "기록한 사례를 비교해 잘 맞는 방식 하나를 유지하고, 맞지 않는 방식 하나를 바꿔 다음 점검일을 정하세요.",
            "section_2_3",
        ),
    }
    answer, today, week, month, target = plans[domain]
    actions = [
        {"period": period, "timing": timing, "title": title, "action": action, "target_section": target,
         "selection_reason": "입력한 고민의 주제와 확인 가능한 결과물을 기준으로 정한 실천 제안입니다.",
         "saju_basis": brief["basis_note"],
         "user_context_basis": f"직접 입력한 고민: {request.focus_concern}" if request.focus_concern else "별도 고민 미입력 · 생활 사례로 해석을 확인하는 과제"}
        for period, timing, title, action in (
            ("TODAY", "오늘 · 한 가지", "첫 확인", today),
            ("THIS WEEK", "이번 주 · 한 가지", "작은 실험", week),
            ("THIS MONTH", "이번 달 · 한 가지", "결과를 보고 조정", month),
        )
    ]
    return {"domain": domain, "direct_answer": answer, "actions": actions}


def _section(
    title: str, opening: str, core: str, signals: str, actions: list[str],
    *, moment: tuple[str, str, str] | None = None,
    ending: str | None = None,
) -> str:
    if moment or ending:
        hook, scene, criterion = moment or ("", "", ending)
        # Preserve the canonical title and original chart interpretation; don't
        # manufacture predictions or overwrite the user's stored report.
        tags = ""
        if opening.startswith("#") and "\n\n" in opening:
            tags, opening = opening.split("\n\n", 1)
            tags += "\n\n"
        return (
            f"## {title}\n\n{tags}"
            + (f"### {hook}\n\n{scene}\n\n" if hook else "")
            + f"{opening}\n\n{core}\n\n{signals}\n\n**{criterion}**"
        )
    return (
        f"## {title}\n\n{opening}\n\n### 한눈에 보는 핵심\n\n{core}\n\n"
        f"### 현실에서 보이는 신호\n\n{signals}\n\n### 지금 할 일\n\n"
        "아래에서 지금 필요한 한 가지를 골라 실행해보세요. 횟수와 기간은 조정 가능한 실천 예시입니다.\n\n"
        + "\n".join(f"{index}. {action}" for index, action in enumerate(actions, 1))
    )


def local_focus_section(request: SajuRequest, profile: dict[str, Any]) -> str:
    from .analysis import build_special_dates

    plan = action_plan(request, profile)
    brief = interpretation_brief(profile)
    domain = plan["domain"]
    # Keep user text literal inside a Markdown heading.
    topic = re.sub(r"[<>#*`\[\]\\]", "", request.focus_concern or "지금의 고민")
    title = {"career": "이직 판단표" if "이직" in topic else "일과 진로 판단표", "relationship": "지금 확인할 관계 기준", "money": "지금 확인할 재정 기준"}.get(domain, "지금 내릴 판단")
    criteria = {
        "career": ["현재 역할에서 바꿀 수 있는 조건이 확인됐다면 유지를, 모집 요건이나 생활 조건이 불명확하다면 탐색을, 실제 제안과 실행 조건이 확인됐다면 전환을 검토합니다.", "재직 여부와 목표 직무는 입력만으로 확정하지 않습니다. 구직 중이라면 최근 경험과 관심 공고의 공통 요구를 먼저 비교하세요.", "기혼이고 변화가 공동생활에 영향을 준다면 배우자와 준비 시간·생활비·이동 범위를 함께 확인합니다."],
        "relationship": ["현재 관계 상태에 맞춰 행동을 고릅니다. 새로운 접점을 만드는 과제는 만남을 원하는 솔로에게만 해당합니다.", "말과 행동의 일치, 상호 관심, 거절 이후의 존중을 확인합니다. 상대의 마음이나 재회 가능성을 추측으로 확정하지 않습니다.", "통제·모욕·폭력이 있다면 이를 일반적인 의견 차이나 자신의 성격 탓으로 설명하지 말고 안전과 외부의 도움을 우선합니다."],
        "money": ["현재 수입·필수 지출·상환 일정에서 실제로 선택 가능한 범위를 확인합니다.", "예상 수익만이 아니라 총비용·회수 가능성·중단 조건을 비교합니다.", "사주로 투자 종목·비율·손실 허용액을 정하지 않고, 이해하지 못한 조건은 결정을 보류합니다."],
        "study": ["목표 과제에서 혼자 수행할 수 있는 부분과 설명이 필요한 부분을 나눕니다.", "공부 시간보다 틀린 이유를 설명하고 다음에 적용할 수 있는지 확인합니다.", "시험 결과와 합격 시기는 단정하지 않고 연습 결과로 방법을 조정합니다."],
        "health": ["실제 변화가 있다면 시작 시점과 지속 양상, 전문가에게 전달할 질문을 정리합니다.", "사주로 증상의 원인·취약 장기·치료법을 판단하지 않습니다.", "불편이 지속되거나 걱정된다면 의료 전문가의 평가를 기준으로 대응합니다."],
        "family": ["가족의 마음에 대한 추측과 실제로 관찰한 행동을 구분합니다.", "연령·돌봄 책임·가족 구성처럼 입력되지 않은 상황은 가정하지 않습니다.", "도울 수 있는 범위와 어려운 요청을 나누고, 안전하게 대화할 수 있는 상황에서만 합의를 시도합니다."],
        "general": ["이미 확인한 사실과 아직 확인하지 않은 추측을 나눕니다.", "지금 결정하지 않을 비용과 너무 빨리 결정할 비용을 비교합니다.", "다른 사람의 동의가 필요한 일인지, 직접 바꿀 수 있는 일인지 구분합니다."],
    }[domain]
    steps = [
        f"**1~2일차**: {plan['actions'][0]['action']}",
        "**3~4일차**: 결론을 바꿀 수 있는 정보 한 가지를 신뢰할 수 있는 자료나 직접 대화로 확인합니다.",
        f"**5~7일차**: {plan['actions'][1]['action']}",
        "**8~10일차**: 시도 전 예상과 실제 반응을 비교하고, 예상과 달랐던 사실 한 가지를 기록합니다.",
        "**11~13일차**: 유지할 조건과 중단할 조건을 한 문장씩 정하고 실제 시간과 부담을 다시 확인합니다.",
        "**14일차**: 첫 시도의 반응을 확인하고 이번 달 점검을 이어갈 날짜를 정합니다.",
    ]
    if domain == "career":
        steps[1] = "**3~4일차**: 관심 공고 세 건의 역할·필수 역량·근무 조건을 비교하고, 자신의 경험을 이력서 성과 문장으로 정리합니다."
        steps[3] = "**8~10일차**: 가능하다면 해당 역할을 아는 사람에게 실제 업무와 평가 기준을 묻고, 경험으로 설명할 수 있는 내용과 준비할 내용을 구분합니다."
    dates = build_special_dates(request, profile=profile)[:3]
    calendar = "\n".join(f"- **{item['date']} · {item['label']}**: {item['action']} 이후 확보한 정보로 현재 계획의 유지·수정 여부를 확인합니다." for item in dates)
    return (
        f"## ‘{topic}’을 결정 가능한 질문으로 바꾸기\n\n{plan['direct_answer']}\n\n"
        f"{brief['interaction']} 이 관점은 고민의 결론을 대신하지 않으며, 실제 경험이 다르면 경험을 우선합니다.\n\n"
        f"### 1. {title}\n\n" + ("유지·탐색·전환은 우열이 아니라 현재 확인된 조건에 따른 선택지입니다.\n\n" if domain == "career" else "") + "\n".join(f"- {item}" for item in criteria)
        + "\n\n### 2. 기회 신호와 멈춤 신호\n\n"
        "- **기회 신호**: 원하는 변화를 관찰 가능한 행동으로 설명할 수 있습니다.\n"
        "- **기회 신호**: 직접 확인한 사실이 늘어났고 실제 시간과 비용 안에서 시도할 수 있습니다.\n"
        "- **기회 신호**: 상대의 동의가 필요한 일이라면 동의와 역할이 확인됐습니다.\n"
        "- **멈춤 신호**: 확인하지 않은 기대가 결론의 대부분을 차지합니다.\n"
        "- **멈춤 신호**: 예상보다 부담이 크거나 자신의 경계가 반복해서 무시됩니다.\n"
        "- **멈춤 신호**: 조건이 달라졌는데도 계획을 바꾸지 못하고 있습니다.\n\n"
        "### 3. 첫 14일 준비 계획\n\n횟수와 기간은 조정 가능한 예시 기준입니다. 모든 과제를 끝내기보다 지금 필요한 확인부터 고르세요.\n\n"
        + "\n".join(f"- {step}" for step in steps)
        + "\n\n### 4. 추천일 확인 일정\n\n아래 날짜는 앞의 14일 계획과 별개인 점검 일정입니다. 사건이나 결과를 보장하는 길일이 아니며 생활 일정에 맞춰 바꿀 수 있습니다.\n\n"
        + calendar
        + f"\n\n> 다시 확인할 질문: ‘{topic}’에서 어떤 사실이 새로 확인되면 지금의 판단을 바꾸겠나요?"
    )


def local_sections(request: SajuRequest, profile: dict[str, Any]) -> dict[str, str]:
    from .analysis import CHAPTERS, section_title_for_request

    brief = interpretation_brief(profile)
    plan = action_plan(request, profile)
    day = profile["day_master"]
    role = brief["primary_role"]
    month_role = profile["month_command"]["main_ten_god"]
    day_branch = next(p for p in profile["pillars"] if p["key"] == "day")["branch_main_ten_god"]
    annual = profile["luck"]["current_year"]
    annual_label = ROLE_LENSES[annual["stem_ten_god"]][0]
    decade = profile["luck"]["current_decade"]
    decade_line = (
        f"현재 대운의 {decade['gan_zhi_ko']} 흐름은 {decade['transition_date']}부터 {decade['end_date']}까지이며, {ROLE_LENSES[decade['stem_ten_god']][0]}을 관찰 주제로 삼습니다."
        if decade else "현재는 계산된 첫 대운 이전이거나 대운 계산 범위 밖이므로 현재 대운에 관한 결론을 붙이지 않습니다."
    )
    relationship_scene = {
        "single": "새로운 만남을 원한다면, 알아가는 과정에서 질문을 주고받는지와 자신의 속도를 존중받는지 살펴보세요. 만남을 원하지 않는 시기라면 이를 과제로 삼지 않아도 됩니다.",
        "dating": "현재 연인과 함께 있을 때 의견이 달라도 말할 수 있는지, 부탁이나 거절 이후에도 서로 존중하는지 실제 대화로 확인하세요.",
        "married": "배우자와 일정·생활비·집안일을 조율할 때 부담을 누가 맡는지, 합의한 약속이 실제로 지켜지는지 살펴보세요.",
    }[request.relationship_status]
    data = {
        "section_1_1": (
            f"{' '.join(day['hashtags'])}\n\n{day['label']}을 전통적으로 ‘{day['archetype']}’의 상징으로 읽습니다. 이 이름은 자신의 경험을 설명해볼 출발점입니다.",
            ROLE_PORTRAITS[role][0],
            ROLE_PORTRAITS[role][1],
            ["최근 만족스러웠던 선택 하나에서 직접 정한 기준을 세 단어로 적으세요.", "같은 기준이 도움이 되지 않았던 사례를 찾아 적용 범위를 한 문장으로 고쳐보세요."],
        ),
        "section_1_2": (
            "타인의 평가는 명식만으로 알 수 없지만, 어떤 역할을 맡을 때 편안한지 확인할 단서는 만들 수 있습니다.",
            f"사람들과 함께 있을 때의 모습을 읽는 관점은 다음과 같습니다. {ROLE_PORTRAITS[month_role][0]} 다만 다른 사람이 실제로 어떤 인상을 받았는지는 그 사람의 반응과 대화로 알 수 있습니다.",
            "첫인상과 실제 협업 이후의 평가는 다를 수 있습니다. 편하게 일한 장면과 설명이 어긋난 장면을 비교해 환경의 차이를 보세요. 오행의 보이는 글자가 없다는 이유로 능력이나 사회성이 부족하다고 해석하지 않습니다.",
            ["함께 활동한 사람에게 내가 도움이 됐던 구체적 장면 한 가지를 물어보세요.", "내 의도와 상대가 이해한 내용이 달랐던 상황을 골라 다음에 먼저 말할 설명을 작성하세요."],
        ),
        "section_1_3": (
            "자주 맡는 역할과 정말 원하는 역할은 다를 수 있습니다. 명식의 역할어를 실제 선택과 비교해보면 두 가지를 구분하는 데 도움이 됩니다.",
            role_interplay(role, brief["secondary_role"]),
            f"{brief['question']} 잘하는 일을 맡았을 때 만족감이 남는지, 거절하기 어려워 맡았는지 구분하세요. 반복된 역할이 곧 숨겨진 욕구라는 뜻은 아닙니다. 역할이 편했다면 계속 활용하고, 부담이 있었다면 성격을 고치기 전에 업무량과 지원을 점검할 수 있습니다. 입력되지 않은 외로움이나 불안, 피로를 이미 겪는다고 가정하지 않습니다.",
            ["7일 동안 자발적으로 맡은 일 두 건과 맡은 이유를 기록하세요.", "그중 지속하고 싶은 역할과 줄이고 싶은 역할을 나눠 필요한 지원 한 가지를 적으세요.", "다음 역할을 맡기 전 완료 조건과 도움을 요청할 시점을 함께 정하세요."],
        ),
        "section_2_1": (
            decade_line,
            f"올해 {annual['gan_zhi_ko']} 세운에서는 {annual_label}을 점검 주제로 참고합니다. 이는 일이 막혔다고 진단하는 정보가 아닙니다. 현재 순조로운 영역은 유지하고 실제로 지연되는 일이 있을 때 원인을 나눠보세요.",
            "진행이 더디다면 정보가 없는지, 결정할 권한이 없는지, 실행 시간이 부족한지 각각 확인합니다. 외부 조건과 자신의 선택을 분리해야 바꿀 수 있는 지점이 보입니다. 같은 일이 반복되더라도 원인이 같다고 미리 결론짓지 마세요.",
            ["지연되는 일 한 건에서 마지막으로 진행된 단계와 기다리는 조건을 적으세요.", "정보·권한·시간 중 실제로 부족한 자원 하나를 담당자에게 확인하세요."],
        ),
        "section_2_2": (
            "불편한 상황을 곧바로 성격 탓으로 설명하면 바꿀 수 있는 환경 조건을 놓칠 수 있습니다.",
            f"{brief['label']}이 도움이 된 상황과 부담이 된 상황을 구분하는 것이 이번 역할 해석의 핵심입니다. {brief['question']}",
            "같은 과제가 다른 사람에게도 어렵다면 일정·규칙·자원이 원인일 수 있습니다. 충분한 지원이 있었는데도 반복된 선택이 있다면 그때 자신의 판단 습관을 살펴보세요. 개인의 의지만으로 해결할 수 없는 문제까지 책임질 필요는 없습니다.",
            ["반복된 문제 하나를 사실·환경 조건·내가 한 선택 세 칸으로 나누세요.", "바꿀 수 없는 조건 한 가지와 조정 요청이 가능한 조건 한 가지를 구분하세요."],
        ),
        "section_2_3": (
            "방향을 바꾸는 실험은 작을수록 결과를 비교하기 쉽습니다. 모든 오행을 같은 숫자로 맞추는 것이 목표는 아닙니다.",
            f"{brief['interaction']} 같은 기질도 과제의 범위와 피드백 방식에 따라 다르게 쓰일 수 있습니다.",
            "완료 기준이 명확해지면 진행이 쉬워지는지, 다른 사람의 반응을 확인하면 다음 판단이 쉬워지는지 살펴보세요. 실험 뒤 차이가 없다면 노력의 양보다 실험할 조건을 바꾸는 편이 낫습니다.",
            [brief["action"], "실행 전 예상과 실제 결과의 차이를 한 줄로 남기고 다음 실험에서 바꿀 조건 하나를 고르세요."],
        ),
        "section_3_1": (
            "직업 이름보다 일을 수행하는 조건을 비교하면 실제로 맞는 환경을 찾기 쉽습니다.",
            f"{role}의 {brief['label']}이라는 관점에서는 {brief['environment']}을 먼저 시험해볼 수 있습니다. 이것만으로 특정 직업의 적성이나 성공을 확정할 수는 없습니다.",
            f"{brief['signal']} 과거 프로젝트나 학습 경험과 대조하세요. 같은 분야라도 권한·마감·피드백 구조에 따라 경험이 달라집니다. 아직 직업 경험이 없다면 팀 과제나 개인 작업의 사례로 비교할 수 있습니다.",
            ["몰입했던 작업과 힘들었던 작업의 권한·마감·피드백 방식을 나란히 적으세요.", "다음 업무나 과제에서 바꿔볼 환경 조건 하나를 제안하고 수행 경험을 비교하세요."],
        ),
        "section_3_2": (
            "좋아하는 일과 다른 사람에게 유용한 일이 만나는 지점을 작게 확인해보세요.",
            f"{brief['label']}을 결과물로 연결하려면 누구의 어떤 문제를 해결하는지부터 정합니다. {brief['environment']}이라는 해석이 실제로 맞는지도 사용 반응으로 확인하세요.",
            "같은 결과물을 다시 요청받는지, 사용자가 어떤 부분에서 시간을 아끼는지 관찰합니다. 반응이 없다면 재능이 없다는 결론보다 대상과 문제 정의를 먼저 고쳐보세요. 칭찬과 실제 사용, 사용과 금전 보상은 각각 다른 신호입니다.",
            ["최근 만든 결과물 하나에 대상·문제·제공한 도움을 세 문장으로 붙이세요.", "사용할 사람 한 명에게 도움이 된 부분과 쓰지 않은 부분을 물어 다음 버전을 수정하세요."],
        ),
        "section_3_3": (
            decade_line,
            "운의 명칭만으로 유지나 전환을 권할 수는 없습니다. 재직 중이면 내부 조정과 외부 탐색을 비교하고, 구직 중이면 현재 경험과 목표 요건을 대조하세요.",
            "유지는 지금 자리에서 바꿀 수 있는 조건이 있을 때, 탐색은 더 확인할 정보가 있을 때, 전환은 원하는 역할·생활 조건·실제 기회가 함께 확인됐을 때 검토합니다. 수면이나 기분 한 번의 변화로 장기 결정을 확정하지 마세요.",
            ["다음 역할에 필요한 조건을 필수·협상 가능·거절 기준으로 구분하세요.", "생활에 미칠 시간과 소득 변화를 직접 계산한 뒤 선택지별 확인되지 않은 조건을 적으세요."],
        ),
        "section_3_4": (
            "재물에 관한 해석은 부의 크기보다 자원을 다루는 습관을 확인하는 데 활용할 수 있습니다.",
            f"명식에서 참고한 {brief['label']}이 시간과 비용의 선택에도 나타나는지 살펴보세요. 수입·자산·부채가 입력되지 않았으므로 투자 비율이나 손실 허용액을 정하지 않습니다.",
            "기대와 실제로 남는 돈이 다르다면 반복 지출과 변동 비용을 나눠 확인하세요. 잘 관리되고 있다면 추가 절약을 의무로 삼을 필요는 없습니다. 성과가 있었던 선택도 같은 결과를 보장하지 않으므로 비용과 종료 조건을 다시 확인합니다.",
            ["최근 석 달의 수입과 필수·선택 지출을 월별로 비교하세요.", "큰 지출을 정하기 전 목적·총비용·취소 조건을 한 장에 적고 실제 여유 자금과 대조하세요."],
        ),
        "section_4_1": (
            relationship_scene,
            f"가까운 관계에서는 ‘{ROLE_LENSES[day_branch][0]}’이라는 주제를 참고할 수 있습니다. {ROLE_PORTRAITS[day_branch][1]} 이것은 나의 모습을 돌아보는 설명이지 상대의 성격이나 마음을 알아낸 결과는 아닙니다.",
            "의견 차이가 있어도 서로 설명할 시간을 주는지 관찰합니다. 대화가 원활하다면 기존 방식을 유지해도 됩니다. 통제·모욕·폭력이 있다면 대화 기술의 부족이나 궁합 문제로 돌리지 말고 안전과 도움을 우선하세요.",
            ["편안한 대화를 위해 필요한 조건과 원치 않는 행동을 구분해 적으세요.", "대화가 안전한 경우에만 '나는 이런 상황에서 이렇게 느끼니 이렇게 해주면 좋겠어'라는 문장으로 부탁하세요."],
        ),
        "section_4_2": (
            "좋은 인연은 예정된 등장 시기보다 반복되는 행동에서 알아볼 수 있습니다.",
            f"{relationship_scene} 귀인이라는 말은 자신에게 도움을 주는 관계를 표현하는 상징으로만 사용합니다.",
            "약속을 지키는지, 관심과 질문이 오가는지, 거절 이후에도 존중하는지가 긍정 신호입니다. 반대로 죄책감을 이용한 압박이나 반복된 경계 침해는 주의할 신호입니다. 한 번의 실수만으로 사람 전체를 단정하지 말고 설명과 이후 행동을 함께 봅니다.",
            ["고마웠던 관계 한 가지에서 실제로 도움받은 행동을 짚어 감사 인사를 전하세요.", "앞으로 알아가거나 함께 지낼 때 확인할 약속·상호성·경계의 기준을 하나씩 정하세요."],
        ),
        "section_4_3": (
            "머무는 공간은 운의 방향보다 실제로 편하게 쓰는지부터 점검할 수 있습니다.",
            f"일간의 상징을 취향에 활용한다면 {profile['space_profile']['favorable_space']['color']}을 참고할 수 있습니다. 이는 선택 가능한 장식 아이디어이며 물건을 사거나 방위를 바꿔야 한다는 뜻은 아닙니다.",
            "집중하기 어려운 시간이 있다면 실제로 방해되는 소음·빛·물건을 구분하세요. 함께 쓰는 공간에서는 개인 취향보다 서로의 사용 시간과 동선이 중요할 수 있습니다. 변화가 도움이 되는지는 정리 전후의 실제 사용 경험으로 비교합니다.",
            ["자주 쓰는 자리 한 곳에서 반복해서 찾는 물건 하나의 위치를 고정하세요.", "사용 중 실제로 불편한 빛이나 소음을 하나 조정하고 체감 차이를 기록하세요."],
        ),
        "section_5_1": (
            "회복은 체질을 추측하기보다 실제 생활의 부담과 쉬는 방식을 이해하는 일에서 시작합니다. 수면 시간과 업무량, 쉬고 난 뒤의 느낌은 사람마다 다른 생활 맥락을 보여줍니다.",
            "사주의 오행이나 일간으로 취약 장기나 질병을 판단하지 않습니다. 입력 정보만으로 증상이나 원인을 알 수 없으므로 실제로 불편이 있다면 시작 시점과 생활 변화를 확인하세요.",
            "실제로 피로나 불편이 지속된다면 의료기관의 도움을 받을 수 있습니다. 이 해석은 발병 시기를 예측하거나 의료 전문가의 진단이나 치료를 대체하지 않습니다. 그렇지 않다면 부족한 점을 찾기보다 자신에게 잘 맞는 휴식 방식을 유지하세요. 업무량을 조정할 때에도 실제 책임과 가능한 지원을 함께 고려합니다.",
            ["며칠간 실제 활동·수면 시간과 쉬고 난 뒤의 느낌을 기록해 회복에 도움이 된 방식을 찾으세요.", "선택 가능한 일정 하나를 조정해 쉬는 시간을 만들고 생활이 더 편해졌는지 확인하세요."],
        ),
    }
    titles = {s.section_id: section_title_for_request(s, request) for _, _, sections in CHAPTERS for s in sections}
    moments = narrative_moments(role)
    endings = {
        "section_1_2": "사람들이 보는 한 장면이, 당신의 모든 모습을 설명하지는 않습니다.",
        "section_1_3": "밖에서 맡은 역할과 안에서 원하는 역할은 언제나 같을 필요가 없습니다.",
        "section_2_1": "진행이 느린 순간에도, 나의 속도와 환경의 속도는 구분할 수 있습니다.",
        "section_2_3": "기질은 채워야 할 빈칸보다, 상황에 따라 다르게 쓰이는 방식에 가깝습니다.",
        "section_3_1": "같은 재능도 어떤 방식으로 일하느냐에 따라 다른 경험을 남깁니다.",
        "section_3_2": "잘하는 일의 가치는 칭찬과 실제 쓰임 사이에서 더 선명해집니다.",
        "section_4_1": "가까운 관계에서도 나의 마음과 상대의 마음을 같은 답으로 정할 수는 없습니다.",
        "section_4_3": "나에게 맞는 공간은 정해진 방위보다 실제로 편안했던 경험에 가깝습니다.",
        "section_5_1": "회복의 기준은 명식이 정한 약점보다, 실제로 내 몸과 생활에 도움이 된 경험입니다.",
    }
    sections = {
        key: _section(titles[key], *values, moment=moments.get(key), ending=endings.get(key))
        for key, values in data.items()
    }
    windows = profile["luck"]["monthly_flow"][:3]
    monthly_copy = "\n\n".join(
        f"**{item['boundary_label']} · {item['gan_zhi_ko']}월 · {item['focus']}**\n"
        f"{item['use']} 실제로 확인할 장면은 {item['watch']}이 나타나는지입니다."
        for item in windows
    )
    sections["section_5_2"] = _section(
        titles["section_5_2"], "현재 적용되는 월운부터 세 구간을 살펴봅니다. 월운은 달력의 1일이 아닌 표시된 입절 경계에서 바뀝니다.",
        monthly_copy,
        "월운의 주제는 관찰 순서를 정하는 참고입니다. 같은 달에도 준비 상태와 현실 조건은 다르므로 계약·만남·성과를 보장하는 일정으로 쓰지 않습니다. 행동 날짜가 달라도 계획을 실패로 볼 필요가 없습니다.",
        ["세 구간 중 실제 계획과 관련된 주제 하나만 골라 달력에 적으세요.", "각 구간이 끝날 때 예상과 달랐던 사실 한 가지를 남겨 다음 계획을 조정하세요."],
    )
    start = date.fromisoformat(profile["reference_date"])
    milestones = "\n".join(
        f"- **{(start + timedelta(days=days - 1)).isoformat()} · {days}일 점검**: {checkpoint}"
        for days, checkpoint in (
            (30, plan["actions"][2]["action"]),
            (60, "앞선 점검에서 고른 방식을 이어간 뒤 반응과 부담이 어떻게 달라졌는지 비교하세요."),
            (90, "선택한 경로를 유지하거나 바꿀 이유를 실제 경험에서 찾고 다음 점검을 정하세요."),
        )
    )
    sections["section_5_3"] = (
        f"## {titles['section_5_3']}\n\n이미 잘되고 있는 부분과 바꾸고 싶은 부분을 구분해 필요한 경로 하나만 고르세요. "
        "90일은 운이 바뀌는 확정 시점이 아니라 자신의 선택을 돌아보기 위한 실행 기간입니다. "
        f"오늘은 {plan['actions'][0]['action']} 이번 주에는 {plan['actions'][1]['action']}\n\n"
        "### 한눈에 보는 핵심\n\nA안은 유지할 이유가 확인됐을 때, B안은 아직 정보가 부족할 때, C안은 작은 시험의 결과와 실행 조건이 확인됐을 때 선택합니다. "
        "새 정보가 생기면 경로를 바꿀 수 있으며 전환이 유지보다 더 좋은 선택이라는 뜻은 아닙니다.\n\n"
        "### 90일 실행 계획\n\n"
        "- **A안 · 유지**: 효과가 확인된 방식 하나를 계속하고 불필요한 부담이 늘지 않는지 봅니다.\n"
        "- **B안 · 탐색**: 결론을 바꿀 질문 하나만 시험하고 얻은 사실을 기록합니다.\n"
        "- **C안 · 시도**: 실제 시간과 비용 안에서 되돌릴 수 있는 변화 하나를 실행합니다.\n\n"
        f"### 3개월 타임라인 체크리스트\n\n{milestones}\n\n"
        "### 멈추거나 바꿀 조건\n\n예상보다 부담이 커지거나 필요한 동의·자원이 없다면 규모를 줄이세요. "
        "반대로 지속 가능한 효과가 확인됐다면 다음 단계 하나만 추가합니다. 판단은 실제 기록을 기준으로 합니다."
    )
    sections["section_5_4"] = (
        f"## {titles['section_5_4']}\n\n{brief['one_line']} 이 책에서 자신의 경험과 맞았던 대목 하나만 먼저 활용해도 충분합니다.\n\n"
        f"### 한눈에 보는 핵심\n\n{brief['interaction']} 모호하게 맞는 느낌보다 실제로 설명할 수 있는 장면을 남겨보세요. "
        "설명되지 않는 경험을 억지로 끼워 맞출 필요는 없습니다.\n\n"
        "### 다음 선택을 위한 질문\n\n잘 맞았던 방식은 어떤 조건에서 작동했나요? 지금 바꿀 수 있는 것은 무엇인가요? "
        "자신의 답이 달라졌다면 계획도 바뀔 수 있습니다. 오늘 선택한 행동 하나의 결과를 보고 다음 걸음을 정하세요."
    )
    return sections
