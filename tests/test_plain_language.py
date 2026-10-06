from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.narrative import jargon_density_issues
from app.portraits import ROLE_PORTRAITS, role_interplay
from app.gemini import _chapter_scope_issues, _build_chapter_prompt
from app.models import SajuRequest


def test_user_reported_jargon_chain_is_sent_for_rewriting():
    text = "지지에 놓인 인목의 본기 갑목인 편인은 당연해 보이는 통념을 새로운 시각으로 다시 묻는 역할이며, 오화의 본기 정화인 겁재는 뚜렷한 주관으로 경쟁과 협업을 헤쳐 나가는 동력이 됩니다."
    request = SajuRequest.model_validate(dict(name="문체 검사", birth_date="1990-05-15", birth_time_unknown=True, gender="male", relationship_status="single"))
    assert jargon_density_issues(text)
    assert any("전문용어 과밀" in issue for issue in _chapter_scope_issues("section_1_3", text, request))
    assert "계산 자료는 작가가 해석을 고르는 내부 참고" in _build_chapter_prompt(request, 1)


def test_plain_words_and_a_single_explained_term_are_allowed():
    assert not jargon_density_issues("일간은 나의 중심 기질을 읽는 기준입니다.")
    assert not jargon_density_issues("다른 사람과 상관없이 정관을 고치는 일은 직업과 무관합니다.")
    assert not jargon_density_issues("함께할 때는 활발하게 의견을 나누어도, 혼자 있을 때는 다른 가능성을 깊이 생각할 수 있습니다.")


def test_portraits_and_combined_roles_do_not_require_ten_god_vocabulary():
    for role, paragraphs in ROLE_PORTRAITS.items():
        assert role not in paragraphs[0]
        for other in ROLE_PORTRAITS:
            text = role_interplay(role, other)
            assert role not in text
            assert other not in text
            assert not jargon_density_issues(text)
