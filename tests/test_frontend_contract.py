from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def test_input_page_includes_history_consent() -> None:
    html = read_text("frontend/pages/input.html")

    assert 'id="historyConsent"' in html
    assert "분석 기록을 저장" in html


def test_homepage_exposes_accessible_service_journey() -> None:
    html = read_text("frontend/pages/index.html")

    assert 'class="skip-link"' in html
    assert 'id="mainContent"' in html
    assert 'id="howItWorks"' in html
    assert "명식 계산과 맞춤 분석" in html
    assert 'id="safetySection"' in html


def test_input_page_separates_required_processing_and_optional_email_consent() -> None:
    html = read_text("frontend/pages/input.html")
    script = read_text("frontend/assets/js/input.js")

    assert 'id="emailNotificationConsent"' in html
    assert "개인정보 처리에 동의" in html
    assert 'id="processingConsent"' in html
    assert "email_notification_consent" in script


def test_input_page_accepts_an_optional_focus_concern() -> None:
    html = read_text("frontend/pages/input.html")
    script = read_text("frontend/assets/js/input.js")

    assert 'id="focus_concern"' in html
    assert 'maxlength="200"' in html
    assert "현 직장 5년차, 성장 정체로 이직 고민" in html
    assert "payload.focus_concern = focusConcern" in script


def test_partner_fields_use_an_accessible_animated_disclosure() -> None:
    html = read_text("frontend/pages/input.html")
    script = read_text("frontend/assets/js/input.js")
    styles = read_text("frontend/assets/css/input.css")

    assert 'aria-controls="partnerInfoSection"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="partnerInfoSection"' in html
    assert 'aria-hidden="true"' in html
    assert "classList.toggle('is-expanded', hasPartner)" in script
    assert "toggleAttribute('inert', !hasPartner)" in script
    assert "setAttribute('aria-expanded', String(hasPartner))" in script
    assert ".partner-details.is-disclosure-ready" in styles
    assert "max-height 440ms" in styles
    assert ".partner-details.is-expanded" in styles


def test_input_consent_links_to_dedicated_privacy_guide() -> None:
    input_html = read_text("frontend/pages/input.html")
    privacy_html = read_text("frontend/pages/privacy.html")

    assert 'href="privacy.html"' in input_html
    assert 'target="_blank"' in input_html
    assert "수집하는 정보" in privacy_html
    assert "Google Gemini API" in privacy_html
    assert "운영 알림 이메일" in privacy_html
    assert "Gmail" not in privacy_html
    assert "동의를 거절하거나 철회" in privacy_html
    assert "최대 24시간" in privacy_html


def test_legacy_form_fields_removed_from_index() -> None:
    html = read_text("frontend/pages/index.html")

    assert "writing_style" not in html
    assert 'name="tone"' not in html


def test_result_renderer_avoids_raw_innerhtml_injection() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "innerHTML = page.content" not in script
    assert "renderMarkdown(markdown)" in script


def test_result_hides_provider_models_and_exports_rendered_markdown() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "AI · ${modelLabel}" not in script
    assert "models_used.join" not in script
    assert "renderMarkdownToHtml(this.stripDuplicatePageHeading(page.markdown, page.title))" in script
    assert '<pre style="white-space: pre-wrap' not in script


def test_result_chart_labels_visible_counts_and_month_command() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")

    assert "오행의 보이는 분포와 월령" in html
    assert "metric.bar_percent" in script
    assert "metric.is_month_command" in script


def test_result_starts_with_a_progressive_sixty_second_summary() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")
    styles = read_text("frontend/assets/css/result.css")

    assert 'id="quickSummaryPanel"' in html
    assert 'id="quickDirectAnswer"' in html
    assert 'id="monthlyFlowList"' in html
    assert 'data-report-feedback="match"' in html
    assert html.index('id="reportTitle"') < html.index('id="quickSummaryPanel"') < html.index('id="sajuBasisPanel"')
    assert html.index('id="practicalReport"') < html.index('id="interpretationFeedbackTitle"')
    assert "renderQuickSummary(analysis?.quick_summary)" in script
    assert "saveInterpretationFeedback" in script
    assert "removeStandaloneBasisSection" in script
    assert ".monthly-flow-list" in styles


def test_result_locks_paid_steps_until_access_is_confirmed() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")

    assert 'class="step-tab-btn premium-step-tab"' in html
    assert 'class="premium-tab-state"' in html
    assert "resolvePremiumAccess(analysis)" in script
    assert "if (stepNum > 1 && !this.premiumUnlocked)" in script
    assert "book-saju:checkout-requested" in script


def test_free_summary_uses_analysis_data_instead_of_fixed_copy() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "this.sharpSummaryHeadline.textContent = summary.self_portrait?.headline || summary.one_line" in script
    assert "this.sharpSummaryBody.textContent = summary.self_portrait?.body" in script
    assert "this.sharpStrengthTitle.textContent = strengthHint" in script
    assert "this.sharpTaskTitle.textContent = taskHint" in script


def test_paid_practical_page_has_one_action_checklist() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")

    assert "오늘·이번 주·이번 달 실행 체크리스트" in html
    assert 'id="quickActionList"' not in html
    assert "action-check-button" in script


def test_form_submission_uses_task_id_redirect_without_private_query_params() -> None:
    script = read_text("frontend/assets/js/main.js")

    assert "createSajuBook(sajuData)" in script
    assert "new URLSearchParams({ task_id: taskId })" in script
    assert "Object.entries(sajuData).forEach" not in script


def test_birth_time_unknown_is_sent_as_explicit_flag() -> None:
    script = read_text("frontend/assets/js/main.js")

    assert "sajuData.birth_time_unknown = true" in script


def test_submission_revalidates_every_required_step() -> None:
    script = read_text("frontend/assets/js/main.js")

    assert "validateAllSteps()" in script
    assert "if (!this.validateAllSteps()) return;" in script
    assert "this.currentStep = firstInvalidStep" in script


def test_result_page_no_longer_creates_analysis_from_private_url_params() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "createSajuBook" not in script
    assert "urlParams.get('name')" not in script
    assert "url.search = ''" in script


def test_result_tabs_are_generated_from_analysis_data() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "renderChapterTabs()" in script
    assert "this.chapterTabs.replaceChildren()" in script
    assert "getFallbackChapters(analysis)" in script


def test_result_page_exposes_section_navigation_controls() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")

    assert 'id="previousPageButton"' in html
    assert 'id="nextPageButton"' in html
    assert "this.renderPage(this.currentPageIndex + 1)" in script


def test_private_cache_uses_session_storage_without_consent() -> None:
    script = read_text("frontend/assets/js/storage.js")

    assert "SESSION_ANALYSIS_CACHE_KEY" in script
    assert "const storage = persist ? localStorage : sessionStorage" in script


def test_inline_click_handlers_removed_from_result_page() -> None:
    html = read_text("frontend/pages/result.html")

    assert "onclick=" not in html


def test_root_redirect_is_relative_for_subpath_deployments() -> None:
    html = read_text("frontend/index.html")

    assert 'url=app/index.html' in html
    assert 'url=/app/index.html' not in html


def test_share_card_save_is_implemented() -> None:
    script = read_text("frontend/assets/js/result.js")

    assert "saveShareCard(" in script
    assert "canvas.toDataURL('image/png')" in script
    assert "'준비 중'" not in script


def test_result_page_exposes_practical_summary_cards() -> None:
    html = read_text("frontend/pages/result.html")
    script = read_text("frontend/assets/js/result.js")

    assert 'id="typeLabel"' in html
    assert 'id="profileChart"' in html
    assert 'id="actionCards"' in html
    assert 'id="socialProfileTitle"' in html
    assert 'id="copyProfileButton"' in html
    assert "renderPracticalSummary(userData, analysis)" in script


def test_file_pages_redirect_to_the_running_local_server() -> None:
    guard = read_text("frontend/assets/js/file-protocol-guard.js")

    assert "window.location.protocol !== 'file:'" in guard
    assert "http://127.0.0.1:3005/pages/" in guard
    assert "currentPage === 'result.html' && !hasTaskId" in guard
    for page in ("index.html", "input.html", "result.html", "privacy.html"):
        html = read_text(f"frontend/pages/{page}")
        assert 'src="../assets/js/file-protocol-guard.js"' in html


def test_start_script_supports_frontend_only_mode() -> None:
    script = read_text("start_servers.sh")

    assert "프론트엔드 정적 서버만 시작합니다" in script
    assert 'RUN_BACKEND=false' in script
