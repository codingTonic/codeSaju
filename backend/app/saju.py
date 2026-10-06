from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from lunar_python import Lunar, Solar
from lunar_python.util import LunarUtil

from .models import SajuRequest


REPORT_DATE: ContextVar[date | None] = ContextVar("saju_report_date", default=None)


def analysis_today() -> date:
    """Use one Korean calendar day throughout a report, including async chapters."""
    return REPORT_DATE.get() or datetime.now(ZoneInfo("Asia/Seoul")).date()


GAN_ELEMENT = {
    "甲": "목",
    "乙": "목",
    "丙": "화",
    "丁": "화",
    "戊": "토",
    "己": "토",
    "庚": "금",
    "辛": "금",
    "壬": "수",
    "癸": "수",
}

ZHI_ELEMENT = {
    "子": "수",
    "丑": "토",
    "寅": "목",
    "卯": "목",
    "辰": "토",
    "巳": "화",
    "午": "화",
    "未": "토",
    "申": "금",
    "酉": "금",
    "戌": "토",
    "亥": "수",
}

# LunarUtil.ZHI_HIDE_GAN과 같은 순서입니다. 첫 글자만 지지의 본기로 쓰고,
# 나머지는 지장간으로 따로 보존해 지지 전체의 십신과 섞지 않습니다.
ZHI_HIDDEN_STEMS = {
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "庚", "戊"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
}

GAN_READING = {
    "甲": "갑",
    "乙": "을",
    "丙": "병",
    "丁": "정",
    "戊": "무",
    "己": "기",
    "庚": "경",
    "辛": "신",
    "壬": "임",
    "癸": "계",
}

ZHI_READING = {
    "子": "자",
    "丑": "축",
    "寅": "인",
    "卯": "묘",
    "辰": "진",
    "巳": "사",
    "午": "오",
    "未": "미",
    "申": "신",
    "酉": "유",
    "戌": "술",
    "亥": "해",
}


def gan_zhi_reading(gan_zhi: str) -> str:
    if not gan_zhi or len(gan_zhi) < 2:
        return gan_zhi
    gan = GAN_READING.get(gan_zhi[0], gan_zhi[0])
    zhi = ZHI_READING.get(gan_zhi[1], gan_zhi[1])
    return f"{gan}{zhi}"


DAY_MASTER_ARCHETYPES = {
    "甲": "개척하는 큰나무형",
    "乙": "연결하는 풀과 덩굴형",
    "丙": "밝히고 확산하는 태양형",
    "丁": "한곳을 비추는 등불형",
    "戊": "중심을 잡는 산형",
    "己": "기르고 다듬는 밭형",
    "庚": "결단하고 단련하는 쇠형",
    "辛": "정교하게 가려내는 보석형",
    "壬": "경계를 넘어 흐르는 큰물형",
    "癸": "세밀하게 스며드는 빗물형",
}

DAY_MASTER_HASHTAGS = {
    "甲": ("#단단한_개척자", "#도전과_성장"),
    "乙": ("#유연한_생존자", "#적응과_연결"),
    "丙": ("#열정의_태양", "#밝은_영향력"),
    "丁": ("#섬세한_등불", "#따뜻한_몰입"),
    "戊": ("#흔들리지_않는_산", "#든든한_신뢰"),
    "己": ("#포용하는_대지", "#실용적_가꿈"),
    "庚": ("#단단한_강철", "#결단과_원칙"),
    "辛": ("#정교한_보석", "#예리한_디테일"),
    "壬": ("#거침없는_바다", "#넓은_통찰"),
    "癸": ("#스며드는_샘물", "#지혜로운_관찰"),
}

TEN_GOD_KO = {
    "比肩": "비견",
    "劫财": "겁재",
    "劫財": "겁재",
    "食神": "식신",
    "伤官": "상관",
    "傷官": "상관",
    "偏财": "편재",
    "偏財": "편재",
    "正财": "정재",
    "正財": "정재",
    "七杀": "편관",
    "七殺": "편관",
    "偏官": "편관",
    "正官": "정관",
    "偏印": "편인",
    "正印": "정인",
    "日主": "일간",
}

TEN_GOD_TERMS = (
    "비견",
    "겁재",
    "식신",
    "상관",
    "편재",
    "정재",
    "편관",
    "정관",
    "편인",
    "정인",
)

ELEMENT_ORDER = ("목", "화", "토", "금", "수")

ORGAN_ELEMENT_MAP: dict[str, str] = {
    "목": "간·담 (간장 기능, 눈의 피로, 근육 긴장, 신경계)",
    "화": "심장·소장 (혈관, 혈액순환, 안면 열감, 가슴 답답함)",
    "토": "비장·위장 (소화기계, 복부 팽만, 식습관 리듬, 피부 대사)",
    "금": "폐·대장 (호흡기계, 기관지, 알레르기, 피부 장벽)",
    "수": "신장·방광 (비뇨기, 생식기, 뼈·관절, 수분 대사 및 만성 피로)",
}

SPACE_DIRECTION_MAP: dict[str, dict[str, str]] = {
    "목": {"direction": "동쪽 (생기와 새로운 시작)", "color": "초록·청록 계열 및 원목 식물", "theme": "성장과 창의적 발상"},
    "화": {"direction": "남쪽 (열정과 확장)", "color": "따뜻한 웜톤(오렌지, 은은한 무드등)", "theme": "표현과 활력, 대외적 활동"},
    "토": {"direction": "중앙 및 완만한 평지", "color": "베이지·아이보리·황토·따뜻한 패브릭", "theme": "안정과 정착, 심리적 신뢰"},
    "금": {"direction": "서쪽 (정돈과 결실)", "color": "화이트·메탈·모노톤·미니멀 가구", "theme": "집중과 정리, 결단력"},
    "수": {"direction": "북쪽 (휴식과 재충전)", "color": "네이비·블루·차분한 딥톤 조명", "theme": "깊은 사색과 에너지 회복"},
}


SPECIAL_DATE_GROUPS = (
    (
        ("비견", "겁재"),
        "주도권을 점검하는 날",
        "혼자 밀어붙이기 전 역할, 경쟁 조건, 도움을 청할 사람을 적어보세요.",
    ),
    (
        ("식신", "상관"),
        "표현을 밖으로 꺼내는 날",
        "메모·대화 초안·정리 문서처럼 생각을 보여주는 결과물 하나를 내보세요.",
    ),
    (
        ("편재", "정재"),
        "돈과 조건을 확인하는 날",
        "예산, 보상, 시간 비용을 숫자로 적고 감당 가능한 범위를 확인하세요.",
    ),
    (
        ("편관", "정관"),
        "결정 기준을 세우는 날",
        "약속·계약·공식 결정처럼 책임이 따르는 일의 수락 조건과 보류 조건을 나누세요.",
    ),
    (
        ("편인", "정인"),
        "배움과 회복을 채우는 날",
        "새 자료를 배우거나 조용히 복기하세요. 피로가 쌓였다면 일정을 덜어내는 것도 행동입니다.",
    ),
)

MONTHLY_FLOW_GUIDES = {
    "비견": (
        "주도권과 협업",
        "혼자 결정하기 전 역할과 책임 범위를 확인하세요.",
        "경쟁심 때문에 도움을 거절하거나 일을 겹쳐 맡는 패턴",
    ),
    "겁재": (
        "경쟁과 경계",
        "시간·돈·역할을 나누는 조건을 먼저 합의하세요.",
        "비교에 끌려 계획에 없던 약속이나 지출을 늘리는 패턴",
    ),
    "식신": (
        "표현과 결과물",
        "생각을 말·글·작은 결과물로 밖에 꺼내 확인하세요.",
        "준비만 오래 하고 실제 반응을 확인하지 않는 패턴",
    ),
    "상관": (
        "개선과 문제 제기",
        "불편함을 비판으로 끝내지 말고 바꿀 제안과 함께 말하세요.",
        "말이 앞서 관계나 공식 절차와 충돌하는 패턴",
    ),
    "편재": (
        "기회와 변동 비용",
        "새 제안은 기대 이익과 함께 시간·현금 비용을 적어 비교하세요.",
        "선택지를 넓히다가 유지 비용을 놓치는 패턴",
    ),
    "정재": (
        "현금 흐름과 유지",
        "수입보다 실제로 남는 돈과 반복 지출을 먼저 확인하세요.",
        "안정감을 위해 변화를 지나치게 미루거나 작은 누수를 방치하는 패턴",
    ),
    "편관": (
        "압박과 결단",
        "책임이 큰 결정은 수락 조건과 중단 조건을 함께 적으세요.",
        "긴장을 추진력으로 착각해 회복 없이 밀어붙이는 패턴",
    ),
    "정관": (
        "책임과 공식화",
        "약속·계약·역할을 말이 아닌 확인 가능한 기준으로 정리하세요.",
        "기대에 맞추느라 자신의 한계를 늦게 알리는 패턴",
    ),
    "편인": (
        "탐색과 관점 전환",
        "정보를 더 모으기 전에 지금 검증할 질문 하나를 고르세요.",
        "새로운 해석을 계속 찾느라 결정을 미루는 패턴",
    ),
    "정인": (
        "배움과 회복",
        "배운 내용을 쉬운 말로 정리하고 수면·휴식 시간을 먼저 확보하세요.",
        "이해와 준비가 충분해질 때까지 시작을 미루는 패턴",
    ),
}

DAY_MASTER_SHADOWS: dict[str, str] = {
    "甲": "목표를 지키는 일과 방법을 바꾸는 일을 구분하고 있나요?",
    "乙": "상황에 맞추는 동안 자신의 의사를 말할 기회를 놓치지는 않나요?",
    "丙": "새 일을 시작할 때 마무리에 필요한 시간도 남겨두나요?",
    "丁": "상대가 알아주길 기다리는 마음을 구체적인 부탁으로 표현하나요?",
    "戊": "유지할 기준과 바꿔도 되는 관행을 따로 정하고 있나요?",
    "己": "챙기는 일의 범위가 실제 사용할 수 있는 시간을 넘지는 않나요?",
    "庚": "결론을 전달할 때 상대가 맥락을 이해할 설명도 덧붙이나요?",
    "辛": "완성도를 높이는 수정과 완료를 늦추는 수정을 구분하나요?",
    "壬": "선택지를 넓힌 뒤 하나를 시험할 종료 조건도 정하나요?",
    "癸": "충분히 관찰한 사실과 아직 확인하지 않은 추측을 구분하나요?",
}

TEN_GOD_SHADOWS: dict[str, str] = {
    "비견": "스스로 할 일과 도움받을 일을 나눌 수 있나요?",
    "겁재": "비교가 아니라 자신의 조건으로 약속과 비용을 정하나요?",
    "식신": "익숙한 방식을 유지하면서도 실제 반응을 확인하나요?",
    "상관": "개선점을 말할 때 상대가 실행할 대안도 함께 제시하나요?",
    "편재": "새 기회를 늘리기 전에 이미 맡은 일의 유지 비용을 확인하나요?",
    "정재": "절약할 비용과 목적을 위해 필요한 비용을 구분하나요?",
    "편관": "책임을 받아들이기 전에 권한과 지원을 확인하나요?",
    "정관": "약속을 지키는 만큼 자신의 수용 한계도 알리나요?",
    "편인": "새로운 해석을 찾기 전에 검증할 질문을 하나 정하나요?",
    "정인": "배운 것을 작은 결과물로 사용해볼 기회를 만들고 있나요?",
}

ELEMENT_SHADOWS: dict[str, dict[str, str]] = {
    "목": {
        "lacking": "시작하는 결단력과 추진력 부족, 새로운 환경에 대한 유연성 저하와 무기력",
        "excessive": "시작만 벌여놓고 수습하지 못하는 무책임, 타협 없는 직진으로 인한 충돌",
    },
    "화": {
        "lacking": "열정 표출의 어려움, 감정의 단절과 의욕 저하, 자신을 드러내는 것에 대한 두려움",
        "excessive": "감정 기복과 충동성, 조급증으로 인한 폭발적 분노 및 빠른 에너지 고갈",
    },
    "토": {
        "lacking": "정서적 불안정, 끈기와 뒷심 부족, 매듭을 짓지 못하고 중심을 잃는 유약함",
        "excessive": "생각의 정체, 고집불통, 외부 변화에 대한 완강한 거부와 둔감함",
    },
    "금": {
        "lacking": "결단력과 절제력 결여, 맺고 끊음이 흐릿하여 불필요한 관계와 일에 얽매임",
        "excessive": "지나치게 냉혹한 비판과 자기검열, 융통성 없는 잣대로 타인을 밀어내는 결벽",
    },
    "수": {
        "lacking": "상황 대처의 유연성 부족, 긴장 완화와 휴식 장애, 메마른 감정 반응",
        "excessive": "불안과 잡생각의 범람, 우유부단함, 현실 도피와 감정적 침잠",
    },
}


class SajuCalculationError(ValueError):
    """Raised when the submitted calendar date cannot form a valid chart."""


def _birth_components(request: SajuRequest) -> tuple[int, int, int, int, int]:
    birth_time = request.birth_time if not request.birth_time_unknown else None
    birth_time = birth_time or time(12, 0)
    return (
        request.birth_date.year,
        request.birth_date.month,
        request.birth_date.day,
        birth_time.hour,
        birth_time.minute,
    )


def _birth_lunar_and_solar(request: SajuRequest) -> tuple[Any, Any]:
    year, month, day, hour, minute = _birth_components(request)
    try:
        if request.calendar_type == "lunar":
            lunar_month = -month if request.is_leap_month else month
            lunar = Lunar.fromYmdHms(year, lunar_month, day, hour, minute, 0)
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
            lunar = solar.getLunar()
    except Exception as exc:  # lunar_python raises a generic Exception for bad lunar dates.
        raise SajuCalculationError(
            "입력한 음력 날짜를 만세력으로 변환할 수 없습니다. 날짜와 윤달 여부를 확인해주세요."
        ) from exc
    return lunar, solar


def _translate_ten_god(value: str | None) -> str:
    if not value:
        return "미상"
    return TEN_GOD_KO.get(value, value)


def _ten_god(day_gan: str, other_gan: str) -> str:
    return _translate_ten_god(LunarUtil.SHI_SHEN.get(day_gan + other_gan))


def _branch_ten_god_details(day_gan: str, zhi: str) -> list[dict[str, Any]]:
    return [
        {
            "stem": stem,
            "stem_ko": GAN_READING.get(stem, stem),
            "element": GAN_ELEMENT[stem],
            "ten_god": _ten_god(day_gan, stem),
            "is_main": index == 0,
            "role": "본기" if index == 0 else "지장간",
        }
        for index, stem in enumerate(ZHI_HIDDEN_STEMS[zhi])
    ]


def _pillar(
    eight_char: Any,
    *,
    key: str,
    label: str,
    include: bool = True,
) -> dict[str, Any] | None:
    if not include:
        return None
    method = key.capitalize()
    gan_zhi = getattr(eight_char, f"get{method}")()
    gan = getattr(eight_char, f"get{method}Gan")()
    zhi = getattr(eight_char, f"get{method}Zhi")()
    gan_ko = GAN_READING.get(gan, gan)
    zhi_ko = ZHI_READING.get(zhi, zhi)
    gan_zhi_ko = f"{gan_ko}{zhi_ko}"
    hidden_stems = _branch_ten_god_details(eight_char.getDayGan(), zhi)
    branch_main = hidden_stems[0]
    return {
        "key": key,
        "label": label,
        "gan_zhi": gan_zhi,
        "gan_zhi_ko": gan_zhi_ko,
        "gan": gan,
        "gan_ko": gan_ko,
        "zhi": zhi,
        "zhi_ko": zhi_ko,
        "gan_element": GAN_ELEMENT[gan],
        "zhi_element": ZHI_ELEMENT[zhi],
        "stem_ten_god": _translate_ten_god(
            getattr(eight_char, f"get{method}ShiShenGan")()
        ),
        "branch_main_stem": branch_main["stem"],
        "branch_main_stem_ko": branch_main.get("stem_ko", branch_main["stem"]),
        "branch_main_ten_god": branch_main["ten_god"],
        "hidden_stems": hidden_stems,
        "hidden_ten_gods": [item["ten_god"] for item in hidden_stems],
    }


def _luck_item(day_gan: str, gan_zhi: str, **values: Any) -> dict[str, Any]:
    gan = gan_zhi[:1]
    zhi = gan_zhi[1:2]
    gan_ko = GAN_READING.get(gan, gan)
    zhi_ko = ZHI_READING.get(zhi, zhi)
    gan_zhi_ko = f"{gan_ko}{zhi_ko}"
    branch_main_stem = ZHI_HIDDEN_STEMS.get(zhi, ("",))[0]
    return {
        **values,
        "gan_zhi": gan_zhi,
        "gan_zhi_ko": gan_zhi_ko,
        "gan": gan,
        "gan_ko": gan_ko,
        "stem_element": GAN_ELEMENT.get(gan, "미상"),
        "stem_ten_god": _ten_god(day_gan, gan) if gan else "미상",
        "branch": zhi,
        "branch_ko": zhi_ko,
        "branch_element": ZHI_ELEMENT.get(zhi, "미상"),
        "branch_main_stem": branch_main_stem or "미상",
        "branch_main_stem_ko": GAN_READING.get(branch_main_stem, branch_main_stem) if branch_main_stem else "미상",
        "branch_main_ten_god": (
            _ten_god(day_gan, branch_main_stem) if branch_main_stem else "미상"
        ),
    }


def _annual_pillar(reference_date: date) -> str:
    return (
        Solar.fromYmd(reference_date.year, reference_date.month, reference_date.day)
        .getLunar()
        .getYearInGanZhiExact()
    )


def _shift_years(source: date, years: int) -> date:
    try:
        return source.replace(year=source.year + years)
    except ValueError:
        return source.replace(year=source.year + years, day=28)


JIE_KO = {
    "立春": "입춘",
    "惊蛰": "경칩",
    "驚蟄": "경칩",
    "清明": "청명",
    "立夏": "입하",
    "芒种": "망종",
    "芒種": "망종",
    "小暑": "소서",
    "立秋": "입추",
    "白露": "백로",
    "寒露": "한로",
    "立冬": "입동",
    "大雪": "대설",
    "小寒": "소한",
}


def _month_sample(source: date, offset: int) -> date:
    """Return an interior sample date; the exposed boundary comes from Jie times."""

    month_index = source.year * 12 + source.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 15)


def _jie_boundary(value: Any) -> dict[str, str]:
    name = value.getName()
    solar = value.getSolar()
    timestamp = solar.toYmdHms()
    return {
        "name": JIE_KO.get(name, name),
        "timestamp": timestamp,
        "date": timestamp[:10],
    }


def _build_monthly_flow(day_gan: str, today: date) -> list[dict[str, Any]]:
    months: list[dict[str, Any]] = []
    reference = datetime.combine(today, time.min)
    for offset in range(12):
        lunar = Solar.fromYmdHms(
            reference.year, reference.month, reference.day,
            reference.hour, reference.minute, reference.second,
        ).getLunar()
        gan_zhi = lunar.getMonthInGanZhiExact()
        boundary_start = _jie_boundary(lunar.getPrevJie())
        boundary_end = _jie_boundary(lunar.getNextJie())
        item = _luck_item(
            day_gan,
            gan_zhi,
            year=reference.year,
            month=reference.month,
            label=f"{boundary_start['date']} ~ {boundary_end['date']}",
            reference_date=reference.date().isoformat(),
            boundary_start=boundary_start,
            boundary_end=boundary_end,
            boundary_label=(
                f"{boundary_start['name']} {boundary_start['date']}부터 "
                f"{boundary_end['name']} {boundary_end['date']} 전까지"
            ),
            timezone_assumption="출생지 미입력 · 대한민국(Asia/Seoul) 표준시 가정",
        )
        focus, use, watch = MONTHLY_FLOW_GUIDES.get(
            item["stem_ten_god"],
            (
                "관찰과 조정",
                "한 달의 실제 사건과 감정 변화를 기록해 다음 선택에 반영하세요.",
                "운세 문구만으로 중요한 결정을 확정하는 패턴",
            ),
        )
        item.update(
            focus=focus,
            use=use,
            watch=watch,
            basis=(
                f"월운은 {boundary_start['name']} 입절부터 {boundary_end['name']} 입절 전까지의 "
                f"{gan_zhi}월 천간을 {item['stem_ten_god']} 흐름으로 참고"
            ),
        )
        months.append(item)
        reference = datetime.fromisoformat(boundary_end["timestamp"]) + timedelta(seconds=1)
    return months


def build_saju_profile(
    request: SajuRequest,
    *,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Calculate a transparent Four Pillars basis for prompts and the report UI."""

    today = reference_date or analysis_today()
    lunar, solar = _birth_lunar_and_solar(request)
    eight_char = lunar.getEightChar()
    day_gan = eight_char.getDayGan()
    time_known = not request.birth_time_unknown and request.birth_time is not None

    pillars = [
        _pillar(eight_char, key="year", label="연주"),
        _pillar(eight_char, key="month", label="월주"),
        _pillar(eight_char, key="day", label="일주"),
        _pillar(eight_char, key="time", label="시주", include=time_known),
    ]
    visible_pillars = [pillar for pillar in pillars if pillar is not None]

    counts = Counter({element: 0 for element in ELEMENT_ORDER})
    for pillar in visible_pillars:
        counts[pillar["gan_element"]] += 1
        counts[pillar["zhi_element"]] += 1

    gender = 1 if request.gender == "male" else 0
    yun = eight_char.getYun(gender)
    first_transition = date.fromisoformat(yun.getStartSolar().toYmd())
    decades = []
    for transition_index, item in enumerate(
        (item for item in yun.getDaYun(12) if item.getGanZhi())
    ):
        transition_date = _shift_years(first_transition, transition_index * 10)
        next_transition_date = _shift_years(transition_date, 10)
        decades.append(
            _luck_item(
                day_gan,
                item.getGanZhi(),
                start_year=item.getStartYear(),
                end_year=item.getEndYear(),
                start_age=item.getStartAge(),
                end_age=item.getEndAge(),
                transition_date=transition_date.isoformat(),
                end_date=(next_transition_date - timedelta(days=1)).isoformat(),
            )
        )
    current_decade = next(
        (
            item
            for item in decades
            if date.fromisoformat(item["transition_date"])
            <= today
            <= date.fromisoformat(item["end_date"])
        ),
        None,
    )
    next_decade = next(
        (
            item
            for item in decades
            if date.fromisoformat(item["transition_date"]) > today
        ),
        None,
    )

    current_annual_gan_zhi = _annual_pillar(today)
    annual_year = today.year if current_annual_gan_zhi == _annual_pillar(date(today.year, 7, 1)) else today.year - 1
    next_year_date = date(annual_year + 1, 7, 1)
    current_month_gan_zhi = (
        Solar.fromYmd(today.year, today.month, today.day)
        .getLunar()
        .getMonthInGanZhiExact()
    )

    day_element = GAN_ELEMENT[day_gan]
    day_master = {
        "gan": day_gan,
        "reading": GAN_READING[day_gan],
        "element": day_element,
        "polarity": "양" if list(GAN_ELEMENT).index(day_gan) % 2 == 0 else "음",
        "label": f"{GAN_READING[day_gan]}{day_element} 일간",
        "archetype": DAY_MASTER_ARCHETYPES[day_gan],
        "hashtags": list(DAY_MASTER_HASHTAGS.get(day_gan, ("#단단한_중심", "#신뢰의_원칙"))),
    }
    month_pillar = next(pillar for pillar in visible_pillars if pillar["key"] == "month")
    ten_god_reference = {
        "stems": {
            gan: {
                "gan_ko": GAN_READING.get(gan, gan),
                "element": GAN_ELEMENT[gan],
                "ten_god": _ten_god(day_gan, gan),
            }
            for gan in GAN_ELEMENT
        },
        "branches": {
            zhi: {
                "zhi_ko": ZHI_READING.get(zhi, zhi),
                "element": ZHI_ELEMENT[zhi],
                "main_stem": ZHI_HIDDEN_STEMS[zhi][0],
                "main_stem_ko": GAN_READING.get(ZHI_HIDDEN_STEMS[zhi][0], ZHI_HIDDEN_STEMS[zhi][0]),
                "main_ten_god": _ten_god(day_gan, ZHI_HIDDEN_STEMS[zhi][0]),
                "hidden_stems": _branch_ten_god_details(day_gan, zhi),
            }
            for zhi in ZHI_ELEMENT
        },
    }

    year_gan = str(visible_pillars[0]["gan"])
    year_polarity = "양" if list(GAN_ELEMENT).index(year_gan) % 2 == 0 else "음"
    gender_label = "남성" if request.gender == "male" else "여성"
    direction = "순행" if yun.isForward() else "역행"

    return {
        "reference_date": today.isoformat(),
        "calculation_standard": (
            "출생지 미입력 · 대한민국(Asia/Seoul) 표준시를 가정한 절기 기준 간편 계산"
        ),
        "analysis_scope": (
            "간편형 · 일간, 천간 십신, 지지 본기, 보이는 오행, 월령, 대운·세운·월운 중심"
        ),
        "calculation_basis": [
            f"입력 달력: {'음력' if request.calendar_type == 'lunar' else '양력'}"
            f"{' 윤달' if request.is_leap_month else ''}",
            f"양력 환산 출생: {solar.toYmdHms()}",
            (
                "출생 시간: 입력값 사용"
                if time_known
                else "출생 시간: 미상 · 시주 제외, 정오를 계산용 임시값으로 사용"
            ),
            f"대운 방향: {gender_label}·출생 연간 {year_gan}({year_polarity}) 기준 {direction}",
            f"첫 대운 시작일: {yun.getStartSolar().toYmd()}",
            "시간대 가정: 출생지 입력이 없어 대한민국(Asia/Seoul) 표준시를 사용",
        ],
        "calendar_input": "음력" if request.calendar_type == "lunar" else "양력",
        "is_leap_month": bool(request.is_leap_month),
        "solar_birth": solar.toYmdHms(),
        "lunar_birth": lunar.toString(),
        "time_known": time_known,
        "pillars": visible_pillars,
        "missing_pillars": [] if time_known else ["시주"],
        "day_master": day_master,
        "month_command": {
            "zhi": month_pillar["zhi"],
            "element": month_pillar["zhi_element"],
            "main_stem": month_pillar["branch_main_stem"],
            "main_ten_god": month_pillar["branch_main_ten_god"],
            "label": (
                f"월지 {month_pillar['zhi']}({month_pillar['zhi_element']}) · "
                f"본기 {month_pillar['branch_main_stem']}({month_pillar['branch_main_ten_god']})"
            ),
        },
        "ten_god_reference": ten_god_reference,
        "organ_profile": {
            "weak_organs": [],
            "note": "오행 글자 수나 일간으로 취약 장기·체질·질병을 판정하지 않습니다. 실제 생활 기록을 바탕으로 휴식과 업무량만 점검합니다.",
        },
        "space_profile": {
            "favorable_space": SPACE_DIRECTION_MAP.get(day_element, SPACE_DIRECTION_MAP["토"]),
            "all_spaces": SPACE_DIRECTION_MAP,
            "note": "색상과 소재는 전통 상징을 활용한 취향 제안이며 길한 방위나 운의 개선을 판정한 결과가 아닙니다. 채광·소음·동선과 실제 선호를 우선합니다.",
        },
        "element_counts": {element: counts[element] for element in ELEMENT_ORDER},
        "element_count_total": sum(counts.values()),
        "shadow_profile": {
            "note": "아래 항목은 확인할 질문이며 성격 진단이 아닙니다. 일치하지 않는 경험을 함께 확인하고, 환경적 원인을 개인의 성격 탓으로 돌리지 않습니다.",
            "day_master_shadow": DAY_MASTER_SHADOWS.get(
                day_gan,
                "자신의 방식을 고수하다 맹점에 빠지기 쉬운 성향",
            ),
            "element_imbalances": [
                (
                    f"{element} 보이는 글자 0자: 지장간까지 없다는 뜻도, 관련 능력이 부족하다는 뜻도 아닙니다."
                    if counts[element] == 0
                    else f"{element} 보이는 글자 {counts[element]}자: 반복된 배치이며 세력 과다나 성격 문제로 판정하지 않습니다."
                )
                for element in ELEMENT_ORDER
                if counts[element] == 0 or counts[element] >= 3
            ]
            or ["보이는 글자 수만으로 균형·강약·성격을 판정하지 않습니다."],
            "ten_god_shadows": [
                f"{tg}: {TEN_GOD_SHADOWS[tg]}"
                for tg in TEN_GOD_TERMS
                if tg in (
                    {p["stem_ten_god"] for p in visible_pillars if p["key"] != "day"}
                    | {p["branch_main_ten_god"] for p in visible_pillars}
                )
                and tg in TEN_GOD_SHADOWS
            ],
        },
        "element_note": (
            f"오행 수치는 보이는 천간·지지 글자 수이고, 월령은 {month_pillar['zhi']}"
            f"({month_pillar['zhi_element']})입니다. 월령은 별도로 표시하지만 계절 세력·통근·"
            "합충형파·용신을 종합한 강약 백분율로 환산하지 않습니다."
        ),
        "luck": {
            "direction": direction,
            "direction_basis": (
                f"입력 성별 {gender_label}과 출생 연간 {year_gan}({year_polarity})을 기준으로 {direction}"
            ),
            "start": {
                "years_after_birth": yun.getStartYear(),
                "months_after_birth": yun.getStartMonth(),
                "days_after_birth": yun.getStartDay(),
                "solar_date": yun.getStartSolar().toYmd(),
                "estimated": not time_known,
            },
            "current_decade": current_decade,
            "next_decade": next_decade,
            "current_year": _luck_item(
                day_gan,
                current_annual_gan_zhi,
                year=annual_year,
                reference_calendar_year=today.year,
            ),
            "next_year": _luck_item(
                day_gan,
                _annual_pillar(next_year_date),
                year=annual_year + 1,
            ),
            "current_month": _luck_item(
                day_gan,
                current_month_gan_zhi,
                year=today.year,
                month=today.month,
            ),
            "next_transition_date": (
                next_decade["transition_date"] if next_decade else None
            ),
            "monthly_flow": _build_monthly_flow(day_gan, today),
        },
        "interpretation_limits": (
            "이 결과는 간편형 해석입니다. 지장간은 계산 원장에 표시하지만 합·충·형·파·해, "
            "통근, 조후, 격국을 종합한 전문 판정은 하지 않습니다. 용신·희신과 신강·신약은 "
            "학파와 세부 판단에 따라 달라 자동 확정하지 않습니다. "
            "운세는 가능성과 대비 시점을 읽는 참고이며 사건·합격·수익을 보장하지 않습니다."
        ),
    }


def build_saju_special_dates(
    request: SajuRequest,
    *,
    reference_date: date | None = None,
    profile: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Pick five action dates from daily stems, without labelling them lucky or unlucky."""

    today = reference_date or (date.fromisoformat(profile["reference_date"]) if profile else analysis_today())
    profile = profile or build_saju_profile(request, reference_date=today)
    day_gan = str(profile["day_master"]["gan"])
    cursor = today + timedelta(days=4)
    selected: list[dict[str, str]] = []

    gaps_after_match = (13, 8, 13, 8, 8)
    for group_index, (ten_gods, label, action) in enumerate(SPECIAL_DATE_GROUPS):
        match: dict[str, str] | None = None
        for offset in range(0, 24):
            candidate = cursor + timedelta(days=offset)
            lunar = Solar.fromYmd(candidate.year, candidate.month, candidate.day).getLunar()
            gan_zhi = lunar.getDayInGanZhiExact2()
            ten_god = _ten_god(day_gan, gan_zhi[:1])
            if ten_god in ten_gods:
                match = {
                    "date": candidate.isoformat(),
                    "label": label,
                    "action": action,
                    "kind": "saju_action",
                    "recommendation_type": "행동을 점검할 추천일",
                    "gan_zhi": gan_zhi,
                    "ten_god": ten_god,
                    "basis": f"{gan_zhi}일의 천간을 {profile['day_master']['label']} 기준 {ten_god} 흐름으로 참고",
                    "selection_reason": (
                        f"기준일 이후 {ten_gods[0]}·{ten_gods[1]} 일진을 순서대로 탐색하고 "
                        "다른 추천일과 최소 8일 간격을 둔 첫 날짜"
                    ),
                }
                cursor = candidate + timedelta(days=gaps_after_match[group_index])
                break
        if match:
            selected.append(match)

    return selected
