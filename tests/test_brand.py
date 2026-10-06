from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('page', ['index', 'input', 'result', 'privacy'])
def test_public_pages_use_current_brand(page):
    text = (ROOT / 'frontend' / 'pages' / f'{page}.html').read_text()
    assert '나의 결' in text
    assert '북 사주' not in text
    assert 'BOOK SAJU' not in text
    assert '冊' not in text


def test_download_names_change_without_breaking_saved_preferences():
    text = (ROOT / 'frontend/assets/js/result.js').read_text()
    assert '나의결-익명-리포트' in text
    assert '나의결-프로필' in text
    assert "localStorage.getItem('book-saju-view-mode')" in text
    assert "new CustomEvent('book-saju:checkout-requested'" in text
    assert '북 사주' not in text
    assert '나의 나의 결' not in text
