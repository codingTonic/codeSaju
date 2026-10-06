import { ApiError, fetchProgress, deleteAnalysis } from './api.js';
import { buildAnonymousProfile, buildAnonymousReportHtml } from './privacy.js';
import {
    clearLastInput,
    removeHistoryEntryById,
    getCachedAnalysis,
    isHistoryEnabled,
    removeCachedAnalysis,
    saveCachedAnalysis,
    saveHistoryEntry,
} from './storage.js';

const INITIAL_POLL_INTERVAL_MS = 2000;
const MAX_POLL_INTERVAL_MS = 10000;
const POLL_TIMEOUT_MS = 1000 * 60 * 30;
const MAX_POLL_ERRORS = 5;

class PersonalOSResultHandler {
    constructor() {
        this.analysisData = null;
        this.currentTaskId = null;
        this.pollingTimer = null;
        this.pollingStartedAt = 0;
        this.pollingErrorCount = 0;
        this.pollingAttempt = 0;
        this.pollingActive = false;

        this.loadingContainer = document.getElementById('loadingContainer');
        this.analysisContainer = document.getElementById('analysisContainer');
        this.errorContainer = document.getElementById('errorContainer');
        this.generationWarning = document.getElementById('generationWarning');

        this.heroUserGreeting = document.getElementById('heroUserGreeting');
        this.cardIdentity = document.getElementById('cardIdentity');
        this.cardRelationship = document.getElementById('cardRelationship');
        this.cardRelationshipTitle = document.getElementById('cardRelationshipTitle');
        this.cardWealth = document.getElementById('cardWealth');
        this.cardSpecialDate = document.getElementById('cardSpecialDate');
        this.heroDate = document.getElementById('heroDate');
        this.sajuBasisPanel = document.getElementById('sajuBasisPanel');
        this.dayMasterSummary = document.getElementById('dayMasterSummary');
        this.pillarGrid = document.getElementById('pillarGrid');
        this.elementBalance = document.getElementById('elementBalance');
        this.sajuStandardNote = document.getElementById('sajuStandardNote');
        this.quickSummaryPanel = document.getElementById('quickSummaryPanel');
        this.quickConfidence = document.getElementById('quickConfidence');
        this.quickDirectAnswer = document.getElementById('quickDirectAnswer');
        this.quickAnswerWindow = document.getElementById('quickAnswerWindow');
        this.quickGoodSignals = document.getElementById('quickGoodSignals');
        this.quickDecisionChangers = document.getElementById('quickDecisionChangers');
        this.quickOneLine = document.getElementById('quickOneLine');
        this.quickStrengths = document.getElementById('quickStrengths');
        this.quickWatchouts = document.getElementById('quickWatchouts');
        this.quickLuck = document.getElementById('quickLuck');
        this.quickSajuBasis = document.getElementById('quickSajuBasis');
        this.quickUserBasis = document.getElementById('quickUserBasis');
        this.monthlyFlowList = document.getElementById('monthlyFlowList');
        this.verificationQuestionList = document.getElementById('verificationQuestionList');
        this.feedbackStatus = document.getElementById('feedbackStatus');
        this.feedbackButtons = [...document.querySelectorAll('[data-report-feedback]')];

        // 날카로운 3단락 무료 요약 & 프리미엄 잠금 티저
        this.quickUserName = document.getElementById('quickUserName');
        this.sharpSummaryHeadline = document.getElementById('sharpSummaryHeadline');
        this.sharpSummaryBody = document.getElementById('sharpSummaryBody');
        this.sharpSummaryFocus = document.getElementById('sharpSummaryFocus');
        this.sharpStrengthTitle = document.getElementById('sharpStrengthTitle');
        this.sharpBottleneckTitle = document.getElementById('sharpBottleneckTitle');
        this.sharpTaskTitle = document.getElementById('sharpTaskTitle');
        this.freeActionText = document.getElementById('freeActionText');
        this.premiumTeaserSection = document.getElementById('premiumTeaserSection');
        this.teaserUserName = document.getElementById('teaserUserName');
        this.teaserUnlockCtaBtn = document.getElementById('teaserUnlockCtaBtn');
        this.lockedSectionCount = document.getElementById('lockedSectionCount');
        this.teaserPrice = document.getElementById('teaserPrice');
        this.teaserCtaNote = document.getElementById('teaserCtaNote');
        this.teaserStatus = document.getElementById('teaserStatus');

        this.chapterTabs = document.getElementById('chapterTabs');
        this.sectionJumpSelect = document.getElementById('sectionJumpSelect');
        this.allSectionsViewer = document.getElementById('allSectionsViewer');
        this.bookViewer = document.getElementById('bookViewer');
        this.viewModeButtons = [...document.querySelectorAll('.view-mode-btn')];
        this.headerViewModeToggle = document.querySelector('.header-view-mode');
        this.currentViewMode = this.loadViewMode();
        this.pageChapterEl = document.getElementById('pageChapter');
        this.pageTitleEl = document.getElementById('pageTitle');
        this.pageContentEl = document.getElementById('pageContent');
        this.previousPageButton = document.getElementById('previousPageButton');
        this.nextPageButton = document.getElementById('nextPageButton');
        this.pageNumberEl = document.getElementById('pageNumber');
        this.pageChapterMetaEl = document.getElementById('pageChapterMeta');

        // 오디오북 (Web Speech API)
        this.headerAudiobookBtn = document.getElementById('headerAudiobookBtn');
        this.audiobookPlayer = document.getElementById('audiobookPlayer');
        this.audioTrackTitle = document.getElementById('audioTrackTitle');
        this.audioPlayPauseBtn = document.getElementById('audioPlayPauseBtn');
        this.audioPlayIcon = document.getElementById('audioPlayIcon');
        this.audioPrevTrackBtn = document.getElementById('audioPrevTrackBtn');
        this.audioNextTrackBtn = document.getElementById('audioNextTrackBtn');
        this.audioSpeedBtn = document.getElementById('audioSpeedBtn');
        this.audioCloseBtn = document.getElementById('audioCloseBtn');
        this.audioWaveAnim = document.getElementById('audioWaveAnim');
        this.isAudioPlaying = false;
        this.audioSpeed = 1.0;
        this.audioPageIndex = 0;
        this.currentUtterance = null;

        this.loadingStatus = document.getElementById('loadingStatus');
        this.progressBar = document.getElementById('progressBar');
        this.readingProgressBar = document.getElementById('readingProgressBar');

        this.resultThemeToggle = document.getElementById('resultThemeToggle');
        this.resultThemeIcon = document.getElementById('resultThemeIcon');
        this.downloadButton = document.getElementById('downloadButton');

        this.shareModal = document.getElementById('shareModal');
        this.shareModalContent = this.shareModal?.querySelector('[role="dialog"]') || null;
        this.closeShareModalBtn = document.getElementById('closeShareModal');
        this.shareBtn = document.getElementById('shareBtn');
        this.copyAnonymousProfileBtn = document.getElementById('copyAnonymousProfileBtn');
        this.saveImageBtn = document.getElementById('saveImageBtn');
        this.downloadAnonymousReportBtn = document.getElementById('downloadAnonymousReportBtn');
        this.downloadBookReportBtn = document.getElementById('downloadBookReportBtn');
        this.readReportButton = document.getElementById('readReportButton');
        this.resultRetryButton = document.getElementById('resultRetryButton');
        this.typeOwner = document.getElementById('typeOwner');
        this.typeLabel = document.getElementById('typeLabel');
        this.typeTagline = document.getElementById('typeTagline');
        this.typeTraits = document.getElementById('typeTraits');
        this.profileChart = document.getElementById('profileChart');
        this.profileChartNote = document.getElementById('profileChartNote');
        this.actionCards = document.getElementById('actionCards');
        this.socialHeadline = document.getElementById('socialHeadline');
        this.socialProfileTitle = document.getElementById('socialProfileTitle');
        this.socialTags = document.getElementById('socialTags');
        this.practicalReport = document.getElementById('practicalReport');
        this.practicalReportTitle = document.getElementById('practicalReportTitle');
        this.copyProfileButton = document.getElementById('copyProfileButton');
        this.saveProfileImageButton = document.getElementById('saveProfileImageButton');
        this.profileCopyFeedback = document.getElementById('profileCopyFeedback');

        this.reportStepNav = document.getElementById('reportStepNav');
        this.stepTabButtons = Array.from(document.querySelectorAll('.step-tab-btn'));
        this.stepPages = Array.from(document.querySelectorAll('.step-page-section'));
        this.step1NextBtn = document.getElementById('step1NextBtn');
        this.step2PrevBtn = document.getElementById('step2PrevBtn');
        this.step2NextBtn = document.getElementById('step2NextBtn');
        this.step3PrevBtn = document.getElementById('step3PrevBtn');
        this.step3TopBtn = document.getElementById('step3TopBtn');
        this.currentStep = 1;
        this.premiumUnlocked = false;

        this.practicalSummaryData = null;
        this.socialShareText = '';
        this.lastFocusedElement = null;

        this.pages = [];
        this.currentPageIndex = 0;

        this.init();
    }

    async init() {
        this.applyStoredTheme();
        this.setupEventListeners();
        await this.loadAnalysisData();
    }

    setupEventListeners() {
        this.resultThemeToggle?.addEventListener('click', () => this.toggleTheme());

        let currentSize = 1.0625;
        const updateReadingSize = () => {
            document.documentElement.style.setProperty('--reading-font-size', `${currentSize}rem`);
            const decreaseButton = document.getElementById('fontSizeDown');
            const increaseButton = document.getElementById('fontSizeUp');
            if (decreaseButton) decreaseButton.disabled = currentSize <= 1;
            if (increaseButton) increaseButton.disabled = currentSize >= 2.125;
        };
        document.getElementById('fontSizeUp')?.addEventListener('click', () => {
            currentSize = Math.min(currentSize + 0.125, 2.125);
            updateReadingSize();
        });

        document.getElementById('fontSizeDown')?.addEventListener('click', () => {
            currentSize = Math.max(currentSize - 0.125, 1);
            updateReadingSize();
        });

        this.shareBtn?.addEventListener('click', () => this.openShareModal());

        this.closeShareModalBtn?.addEventListener('click', () => this.closeShareModal());

        this.shareModal?.addEventListener('click', (event) => {
            if (event.target === this.shareModal) {
                this.closeShareModal();
            }
        });

        document.addEventListener('keydown', (event) => this.handleGlobalKeydown(event));

        this.readReportButton?.addEventListener('click', () => {
            (this.quickSummaryPanel || this.sajuBasisPanel)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        document.getElementById('deleteReportBtn')?.addEventListener('click', () => this.deleteCurrentReport());
        this.resultRetryButton?.addEventListener('click', () => window.location.reload());

        this.copyAnonymousProfileBtn?.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(this.buildAnonymousShareText());
                this.flashButtonText(this.copyAnonymousProfileBtn, '복사되었습니다', '익명 요약 복사');
            } catch (error) {
                console.error('Anonymous summary copy failed:', error);
                this.flashButtonText(this.copyAnonymousProfileBtn, '복사 실패', '익명 요약 복사');
            }
        });

        this.saveImageBtn?.addEventListener('click', () => this.saveShareCard(this.saveImageBtn, { anonymous: true }));
        this.saveProfileImageButton?.addEventListener('click', () => this.saveShareCard(this.saveProfileImageButton));
        this.downloadAnonymousReportBtn?.addEventListener('click', () => this.downloadBookReport({ anonymous: true }));
        this.downloadBookReportBtn?.addEventListener('click', () => this.downloadBookReport({ anonymous: false }));

        this.copyProfileButton?.addEventListener('click', async () => {
            if (!this.socialShareText) return;
            try {
                await navigator.clipboard.writeText(this.socialShareText);
                if (this.profileCopyFeedback) {
                    this.profileCopyFeedback.textContent = '프로필 문구를 복사했습니다.';
                }
            } catch (error) {
                console.error('Profile copy failed:', error);
                if (this.profileCopyFeedback) {
                    this.profileCopyFeedback.textContent = '복사하지 못했습니다. 잠시 후 다시 시도해주세요.';
                }
            }
        });

        this.downloadButton?.addEventListener('click', () => this.downloadCurrentReport());

        this.feedbackButtons.forEach((button) => {
            button.addEventListener('click', () => this.saveInterpretationFeedback(button.dataset.reportFeedback));
        });

        this.headerAudiobookBtn?.addEventListener('click', () => {
            if (!this.premiumUnlocked) {
                this.requestPremiumAccess(2);
                return;
            }
            this.startAudiobook(this.currentPageIndex);
        });

        this.audioPlayPauseBtn?.addEventListener('click', () => this.toggleAudioPlayPause());
        this.audioPrevTrackBtn?.addEventListener('click', () => {
            if (this.audioPageIndex > 0) this.startAudiobook(this.audioPageIndex - 1);
        });
        this.audioNextTrackBtn?.addEventListener('click', () => {
            if (this.audioPageIndex + 1 < this.pages.length) this.startAudiobook(this.audioPageIndex + 1);
        });
        this.audioSpeedBtn?.addEventListener('click', () => this.cycleAudioSpeed());
        this.audioCloseBtn?.addEventListener('click', () => this.stopAudiobook());

        this.viewModeButtons.forEach((button) => {
            button.addEventListener('click', () => {
                const mode = button.dataset.viewMode;
                if (mode) this.switchViewMode(mode, true);
            });
        });

        this.chapterTabs?.addEventListener('click', (event) => {
            const button = event.target.closest('.tab-btn');
            if (!button) return;

            const chapter = Number.parseInt(button.dataset.chapter || '', 10);
            if (!Number.isNaN(chapter)) {
                this.scrollToChapter(chapter);
            }
        });

        this.sectionJumpSelect?.addEventListener('change', () => {
            const pageIndex = Number.parseInt(this.sectionJumpSelect.value, 10);
            if (Number.isNaN(pageIndex) || pageIndex < 0 || pageIndex >= this.pages.length) return;
            const targetPage = this.pages[pageIndex];

            if (this.currentViewMode === 'all') {
                const targetCard = document.getElementById(`section-card-${targetPage.id}`);
                if (targetCard) {
                    const offset = targetCard.getBoundingClientRect().top + window.scrollY - 130;
                    window.scrollTo({ top: offset, behavior: 'smooth' });
                    return;
                }
            }
            this.renderPage(pageIndex);
            this.scrollBookIntoView();
        });

        this.previousPageButton?.addEventListener('click', () => {
            this.renderPage(this.currentPageIndex - 1);
            this.scrollBookIntoView();
        });

        this.nextPageButton?.addEventListener('click', (event) => {
            this.goToNextDestination({ focusHeading: event.detail === 0 });
        });

        this.stepTabButtons.forEach((btn) => {
            btn.addEventListener('keydown', (event) => this.focusAdjacentStepTab(event));
            btn.addEventListener('click', () => {
                const step = Number.parseInt(btn.dataset.step, 10);
                if (step) this.switchStep(step);
            });
        });

        this.step1NextBtn?.addEventListener('click', () => this.switchStep(2));
        this.teaserUnlockCtaBtn?.addEventListener('click', () => {
            if (this.premiumUnlocked) {
                this.switchStep(2);
            } else {
                this.unlockPremiumAccess(2);
            }
        });
        this.step2PrevBtn?.addEventListener('click', () => this.switchStep(1));
        this.step2NextBtn?.addEventListener('click', () => this.switchStep(3));
        this.step3PrevBtn?.addEventListener('click', () => this.switchStep(2));
        this.step3TopBtn?.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        document.querySelectorAll('[data-step-jump]').forEach((el) => {
            el.addEventListener('click', () => {
                const targetStep = Number.parseInt(el.dataset.stepJump, 10);
                if (targetStep) this.switchStep(targetStep);
            });
        });

        // Curiosity-item 딥링크 — 각 항목 클릭 시 관련 챕터/섹션으로 바로 이동
        const curiosityLinks = [
            { id: 'curiosityBottleneck', chapter: 2, section: 'section_2_1' },
            { id: 'curiosityStrength',   chapter: 3, section: 'section_3_2' },
            { id: 'curiosityTask',       chapter: 5, section: 'section_5_2' },
        ];
        curiosityLinks.forEach(({ id, chapter, section }) => {
            const el = document.getElementById(id);
            if (!el) return;
            const handler = () => this.navigateToSection(chapter, section);
            el.addEventListener('click', handler);
            el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } });
        });
    }

    focusAdjacentStepTab(event) {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !this.stepTabButtons.length) return;
        event.preventDefault();
        const tabs = this.stepTabButtons;
        const current = tabs.indexOf(event.currentTarget);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
            : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        tabs.forEach((tab, index) => { tab.tabIndex = index === next ? 0 : -1; });
        tabs[next].focus();
    }

    switchStep(stepNum, shouldScrollTop = true) {
        if (![1, 2, 3].includes(stepNum)) return;
        if (stepNum > 1 && !this.premiumUnlocked) {
            this.requestPremiumAccess(stepNum);
            return;
        }
        this.currentStep = stepNum;

        this.stepTabButtons?.forEach((btn) => {
            const isActive = Number.parseInt(btn.dataset.step, 10) === stepNum;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', String(isActive));
            btn.tabIndex = isActive ? 0 : -1;
        });

        this.stepPages?.forEach((page) => {
            const isActive = Number.parseInt(page.dataset.step, 10) === stepNum;
            page.classList.toggle('hidden', !isActive);
            page.setAttribute('aria-hidden', String(!isActive));
        });

        if (this.headerViewModeToggle) {
            this.headerViewModeToggle.classList.toggle('hidden', stepNum !== 2);
        }

        if (stepNum === 2) {
            if (this.currentViewMode === 'page') {
                this.renderPage(this.currentPageIndex);
            } else {
                this.renderAllSections();
            }
        }

        if (shouldScrollTop) {
            const headerHeight = document.querySelector('.result-header')?.offsetHeight || 64;
            const targetTop = this.reportStepNav
                ? this.reportStepNav.getBoundingClientRect().top + window.scrollY - headerHeight - 8
                : 0;
            window.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
        }
    }

    resolvePremiumAccess(analysis) {
        if (this.premiumUnlocked) return true;
        const access = analysis?.access;
        return Boolean(
            access?.premium_unlocked === true
            || access?.level === 'premium'
            || analysis?.premium_unlocked === true
        );
    }

    unlockPremiumAccess(targetStep = 2) {
        this.premiumUnlocked = true;
        if (this.analysisData) {
            if (!this.analysisData.access) {
                this.analysisData.access = {};
            }
            this.analysisData.access.premium_unlocked = true;
            this.analysisData.premium_unlocked = true;
        }
        this.configurePremiumAccess(this.analysisData);
        if (this.teaserStatus) {
            this.teaserStatus.textContent = '';
        }
        this.switchStep(targetStep);
    }

    configurePremiumAccess(analysis) {
        this.premiumUnlocked = this.resolvePremiumAccess(analysis);
        const premiumTabs = this.stepTabButtons.filter((button) => Number(button.dataset.step) > 1);

        premiumTabs.forEach((button) => {
            const state = button.querySelector('.premium-tab-state');
            button.classList.toggle('is-locked', !this.premiumUnlocked);
            button.setAttribute('aria-label', this.premiumUnlocked
                ? button.querySelector('.step-title')?.textContent || '상세 리포트'
                : `${button.querySelector('.step-title')?.textContent || '상세 리포트'}, 전체 리포트 체험으로 열기`);
            if (state) {
                state.textContent = this.premiumUnlocked ? '열림' : '체험';
            }
        });

        const sectionCount = analysis?.table_of_contents?.chapters?.reduce(
            (total, chapter) => total + (Array.isArray(chapter.sections) ? chapter.sections.length : 0),
            0,
        ) || this.pages.length;
        if (this.lockedSectionCount) {
            this.lockedSectionCount.textContent = this.premiumUnlocked
                ? `전체 심층 해설 ${sectionCount}개가 열렸습니다`
                : `체험으로 읽을 수 있는 심층 해설 ${sectionCount}개`;
        }

        const purchase = analysis?.purchase || {};
        if (this.teaserPrice) {
            const priceLabel = String(purchase.price_label || '').trim();
            this.teaserPrice.textContent = priceLabel;
            this.teaserPrice.classList.toggle('hidden', !priceLabel || this.premiumUnlocked);
        }
        if (this.teaserCtaNote) {
            this.teaserCtaNote.textContent = this.premiumUnlocked
                ? '전체 리포트가 열렸습니다. 언제든 상세 해설을 읽을 수 있습니다.'
                : '현재 체험용으로 제공됩니다. 실제 결제는 진행되지 않습니다.';
        }
        if (this.teaserUnlockCtaBtn) {
            const label = this.teaserUnlockCtaBtn.querySelector('span:first-child');
            if (label) {
                label.textContent = this.premiumUnlocked
                    ? '상세 리포트 읽기'
                    : '전체 리포트 체험하기';
            }
        }
        this.premiumTeaserSection?.classList.toggle('is-unlocked', this.premiumUnlocked);

        [
            this.downloadBookReportBtn,
            this.downloadAnonymousReportBtn,
        ].forEach((button) => button?.classList.toggle('hidden', !this.premiumUnlocked));
    }

    requestPremiumAccess(targetStep = 2) {
        if (this.premiumUnlocked) {
            this.switchStep(targetStep);
            return;
        }

        const checkoutUrl = String(this.analysisData?.purchase?.checkout_url || '').trim();
        const checkoutEvent = new CustomEvent('book-saju:checkout-requested', {
            cancelable: true,
            detail: { taskId: this.currentTaskId, targetStep },
        });
        const shouldContinue = document.dispatchEvent(checkoutEvent);
        if (!shouldContinue) return;

        if (checkoutUrl && new URL(checkoutUrl, window.location.href).origin === window.location.origin
            && new URL(checkoutUrl, window.location.href).protocol === 'https:') {
            window.location.assign(checkoutUrl);
            return;
        }

        this.premiumTeaserSection?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (this.teaserStatus) {
            this.teaserStatus.textContent = '아래 버튼을 눌러 심층 해설과 90일 전략을 바로 확인할 수 있습니다.';
        }
        window.setTimeout(() => this.teaserUnlockCtaBtn?.focus({ preventScroll: true }), 350);
    }

    loadViewMode() {
        try {
            const saved = localStorage.getItem('book-saju-view-mode');
            return saved === 'page' ? 'page' : 'all';
        } catch {
            return 'all';
        }
    }

    saveViewMode(mode) {
        try {
            localStorage.setItem('book-saju-view-mode', mode);
        } catch {
            // storage error ignored
        }
    }

    switchViewMode(mode, shouldSwitchStep = false) {
        if (mode === 'card') mode = 'all'; // Migrate previously saved card-view preferences.
        if (!['all', 'page'].includes(mode)) return;
        this.currentViewMode = mode;
        this.saveViewMode(mode);

        if (shouldSwitchStep && this.currentStep !== 2) {
            this.switchStep(2);
        }

        this.viewModeButtons.forEach((btn) => {
            const isActive = btn.dataset.viewMode === mode;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', String(isActive));
        });

        if (this.allSectionsViewer) {
            this.allSectionsViewer.classList.toggle('hidden', mode !== 'all');
        }
        if (this.bookViewer) {
            this.bookViewer.classList.toggle('hidden', mode !== 'page');
        }

        if (mode === 'all') {
            this.renderAllSections();

        } else {
            this.renderPage(this.currentPageIndex);
        }
    }

    applyStoredTheme() {
        let theme = 'light';
        try {
            theme = localStorage.getItem('book-saju-reading-theme') || 'light';
        } catch {
            theme = 'light';
        }
        document.documentElement.setAttribute('data-theme', theme);
        document.body.setAttribute('data-theme', theme);
        if (this.resultThemeIcon) {
            this.resultThemeIcon.textContent = theme === 'light' ? '◐' : '○';
        }
        this.resultThemeToggle?.setAttribute(
            'aria-label',
            theme === 'light' ? '야간 읽기 모드로 전환' : '주간 읽기 모드로 전환',
        );
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', nextTheme);
        document.body.setAttribute('data-theme', nextTheme);
        if (this.resultThemeIcon) {
            this.resultThemeIcon.textContent = nextTheme === 'light' ? '◐' : '○';
        }
        this.resultThemeToggle?.setAttribute(
            'aria-label',
            nextTheme === 'light' ? '야간 읽기 모드로 전환' : '주간 읽기 모드로 전환',
        );

        try {
            localStorage.setItem('book-saju-reading-theme', nextTheme);
        } catch {
            console.warn('테마 설정을 저장할 수 없습니다.');
        }
    }

    flashButtonText(button, temporaryLabel, defaultLabel) {
        if (!button) return;
        button.textContent = temporaryLabel;
        window.setTimeout(() => {
            button.textContent = defaultLabel;
        }, 1800);
    }

    openShareModal() {
        if (!this.shareModal) return;
        this.lastFocusedElement = document.activeElement;
        this.shareModal.classList.add('show');
        this.shareModal.setAttribute('aria-hidden', 'false');
        this.closeShareModalBtn?.focus();
    }

    closeShareModal() {
        if (!this.shareModal) return;
        this.shareModal.classList.remove('show');
        this.shareModal.setAttribute('aria-hidden', 'true');
        this.lastFocusedElement?.focus?.();
        this.lastFocusedElement = null;
    }

    handleModalKeydown(event) {
        if (!this.shareModal?.classList.contains('show')) return;

        if (event.key === 'Escape') {
            event.preventDefault();
            this.closeShareModal();
            return;
        }

        if (event.key !== 'Tab' || !this.shareModalContent) return;
        const focusable = [...this.shareModalContent.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
            .filter((element) => !element.disabled && !element.hidden);
        if (!focusable.length) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    handleGlobalKeydown(event) {
        if (this.shareModal?.classList.contains('show')) {
            this.handleModalKeydown(event);
            return;
        }

        const target = event.target;
        const isTyping = target instanceof HTMLElement
            && (target.matches('input, textarea, select, button, a') || target.isContentEditable);
        if (isTyping || event.altKey || event.ctrlKey || event.metaKey) return;

        if (event.key === 'ArrowLeft') {
            this.renderPage(this.currentPageIndex - 1);
            this.scrollBookIntoView();
        } else if (event.key === 'ArrowRight') {
            this.goToNextDestination({ focusHeading: true });
        }
    }

    async loadAnalysisData() {
        const urlParams = new URLSearchParams(window.location.search);
        const taskId = urlParams.get('task_id');

        if (taskId) {
            const cachedResult = getCachedAnalysis(taskId);
            const cachedMode = cachedResult?.analysis?.generation_mode;
            if (cachedResult?.analysis && cachedMode !== 'local_fallback') {
                this.currentTaskId = taskId;
                this.onAnalysisReady(cachedResult.analysis, cachedResult.userData || {});
                return;
            }
            if (cachedMode === 'local_fallback') {
                removeCachedAnalysis(taskId);
            }
        }

        if (taskId) {
            this.currentTaskId = taskId;
            this.showLoadingState('분석 결과를 확인하는 중입니다.');
            this.startPollingStatus();
            return;
        }

        this.showError('분석 작업 식별자가 없습니다. 처음부터 다시 분석을 시작해주세요.');
    }

    startPollingStatus() {
        this.cleanupPolling();
        this.pollingStartedAt = Date.now();
        this.pollingErrorCount = 0;
        this.pollingAttempt = 0;
        this.pollingActive = true;

        void this.pollOnce();
    }

    async pollOnce() {
        if (!this.pollingActive) return;

        if (!this.currentTaskId) {
            this.showError('작업 식별자를 찾을 수 없습니다. 다시 시도해주세요.');
            return;
        }

        if (Date.now() - this.pollingStartedAt > POLL_TIMEOUT_MS) {
            this.showError('분석이 30분 이상 걸리고 있습니다. 작업은 서버에서 계속될 수 있으니 잠시 후 이 주소를 다시 열어주세요.');
            return;
        }

        try {
            const data = await fetchProgress(this.currentTaskId);
            this.pollingErrorCount = 0;
            this.pollingAttempt += 1;

            if (typeof data.percent_overall === 'number') {
                this.updateProgress(
                    data.percent_overall,
                    `분석 중... ${Math.round(data.percent_overall)}%`,
                );
            }

            if (data.status === 'failed' || data.status === 'error') {
                this.showError(data.error || '분석 중 오류가 발생했습니다.');
                return;
            }

            if (data.status === 'completed' || data.status === 'completed_with_errors') {
                const payload = this.extractAnalysisPayload(data, data.analysis_result?.user_data || {});
                if (payload.analysis) {
                    this.onAnalysisReady(payload.analysis, payload.userData, data.warnings);
                    return;
                }

                this.showError('분석은 완료되었지만 결과를 불러오지 못했습니다.');
            }
        } catch (error) {
            if (error instanceof ApiError && [403, 404].includes(error.status)) {
                this.showError(error.getUserMessage());
                return;
            }
            this.pollingErrorCount += 1;

            if (this.pollingErrorCount >= MAX_POLL_ERRORS) {
                const message = error instanceof ApiError
                    ? error.getUserMessage()
                    : '진행 상황을 확인하는 데 실패했습니다.';
                this.showError(message);
                return;
            }

            if (this.loadingStatus) {
                this.loadingStatus.textContent = '서버 응답을 다시 확인하는 중입니다.';
            }
        } finally {
            if (this.pollingActive) {
                const delay = Math.min(
                    INITIAL_POLL_INTERVAL_MS * (1.35 ** this.pollingAttempt),
                    MAX_POLL_INTERVAL_MS,
                );
                this.pollingTimer = window.setTimeout(() => void this.pollOnce(), delay);
            }
        }
    }

    cleanupPolling() {
        this.pollingActive = false;
        if (this.pollingTimer) {
            window.clearTimeout(this.pollingTimer);
            this.pollingTimer = null;
        }
    }

    extractAnalysisPayload(data, fallbackUserData = {}) {
        if (!data || typeof data !== 'object') {
            return { analysis: null, userData: fallbackUserData, taskId: null };
        }

        const directAnalysis = data.analysis || data.analysis_result || data;
        const looksLikeAnalysis = this.hasRenderableAnalysis(directAnalysis);

        if (!looksLikeAnalysis) {
            return { analysis: null, userData: fallbackUserData, taskId: data.task_id || null };
        }

        return {
            analysis: directAnalysis,
            userData: directAnalysis.user_data || fallbackUserData || {},
            taskId: directAnalysis.task_id || data.task_id || null,
        };
    }

    hasRenderableAnalysis(data) {
        if (!data || typeof data !== 'object') return false;
        if (data.table_of_contents?.chapters?.length) return true;
        return Object.keys(data).some((key) => key.startsWith('section_'));
    }

    updateProgress(percent, message) {
        if (this.progressBar) {
            this.progressBar.style.width = `${Math.max(0, Math.min(percent, 100))}%`;
        }

        if (this.loadingStatus) {
            this.loadingStatus.textContent = message;
        }
    }

    showLoadingState(message) {
        this.loadingContainer?.classList.remove('hidden');
        this.analysisContainer?.classList.add('hidden');
        this.errorContainer?.classList.add('hidden');
        this.updateProgress(0, message);
    }

    onAnalysisReady(analysis, userData, warnings = []) {
        this.cleanupPolling();

        this.analysisData = analysis;
        this.userData = userData;
        this.currentTaskId = analysis.task_id || this.currentTaskId;

        this.renderHeroSection(userData, analysis);
        this.renderQuickSummary(analysis?.quick_summary);
        this.renderSajuBasis(analysis?.saju_profile);
        this.renderPracticalSummary(userData, analysis);
        this.renderGenerationWarning(analysis, warnings);
        if (!this.buildBookPages(analysis)) {
            return;
        }
        this.configurePremiumAccess(analysis);

        if (this.currentTaskId && analysis.generation_mode !== 'local_fallback') {
            saveCachedAnalysis(this.currentTaskId, analysis, userData);
        }
        this.saveHistorySnapshot(userData, analysis);

        this.loadingContainer?.classList.add('hidden');
        this.errorContainer?.classList.add('hidden');
        this.analysisContainer?.classList.remove('hidden');

        if (this.currentTaskId) {
            const url = new URL(window.location.href);
            url.search = '';
            url.searchParams.set('task_id', this.currentTaskId);
            window.history.replaceState({}, '', url);
        }
    }

    renderGenerationWarning(analysis, warnings = []) {
        if (!this.generationWarning) return;

        const usedFallback = analysis?.generation_mode === 'local_fallback';
        if (!usedFallback && (!Array.isArray(warnings) || warnings.length === 0)) {
            this.generationWarning.classList.add('hidden');
            this.generationWarning.textContent = '';
            return;
        }

        const safeMessage = Array.isArray(warnings) && warnings.length
            ? warnings.slice(0, 2).join(' ')
            : 'AI 분석 대신 로컬 예시 결과가 표시되었습니다.';
        this.generationWarning.textContent = `⚠️ ${safeMessage}`;
        this.generationWarning.classList.remove('hidden');
    }

    saveHistorySnapshot(userData, analysis) {
        if (!this.currentTaskId || !isHistoryEnabled()) return;

        const name = userData?.name || '익명';
        const summaryTokens = [
            this.extractKeyword(analysis.section_1_1, ''),
            this.extractKeyword(analysis.section_2_1, ''),
            this.extractKeyword(analysis.section_3_1, ''),
        ].filter(Boolean);

        const summary = summaryTokens.length
            ? summaryTokens.join(' • ')
            : this.buildSummaryFallback(analysis.section_1_1);

        saveHistoryEntry({
            id: this.currentTaskId,
            task_id: this.currentTaskId,
            display_name: name,
            summary,
            analysis_date: new Date().toISOString(),
        });
    }

    buildSummaryFallback(text) {
        if (!text) return '요약 정보 없음';
        const firstLine = text
            .replace(/\s+/g, ' ')
            .replace(/[#*`>\-]/g, '')
            .trim()
            .slice(0, 48);
        return firstLine || '요약 정보 없음';
    }

    renderHeroSection(userData, analysis) {
        const displayName = userData?.name || '익명';
        const sajuProfile = analysis?.saju_profile;
        const dayMaster = sajuProfile?.day_master;
        const currentDecade = sajuProfile?.luck?.current_decade;
        const currentYear = sajuProfile?.luck?.current_year;
        const relationshipLabel = {
            single: '솔로',
            dating: '연애 중',
            married: '기혼',
        }[userData?.relationship_status] || '관계 상태';
        this.heroUserGreeting.textContent = `${displayName}님을 읽는 이야기`;
        this.heroDate.textContent = [
            relationshipLabel,
            `${new Date().toLocaleDateString('ko-KR')} 분석됨`,
        ].filter(Boolean).join(' · ');
        if (this.cardRelationshipTitle) this.cardRelationshipTitle.textContent = '현재 핵심 방향';
        if (this.cardSpecialDate) {
            const firstDate = Array.isArray(analysis?.special_dates)
                ? analysis.special_dates[0]
                : null;
            if (firstDate?.date) {
                const parsedDate = new Date(`${firstDate.date}T00:00:00`);
                const dateLabel = Number.isNaN(parsedDate.getTime())
                    ? firstDate.date
                    : parsedDate.toLocaleDateString('ko-KR', {
                        month: 'long',
                        day: 'numeric',
                    });
                this.cardSpecialDate.textContent = [
                    dateLabel,
                    firstDate.gan_zhi_ko ? `${firstDate.gan_zhi_ko}(${firstDate.gan_zhi})` : firstDate.gan_zhi,
                    firstDate.ten_god,
                    firstDate.label || '행동일',
                ].filter(Boolean).join(' · ');
            } else {
                this.cardSpecialDate.textContent = 'Chapter 4에서 확인하세요';
            }
        }

        const currentDecadeLabel = currentDecade
            ? (currentDecade.gan_zhi_ko ? `${currentDecade.gan_zhi_ko} 대운` : `${currentDecade.gan_zhi} 대운`)
            : '';
        const currentYearLabel = currentYear
            ? (currentYear.gan_zhi_ko ? `${currentYear.gan_zhi_ko} ${currentYear.stem_ten_god} 세운` : `${currentYear.gan_zhi} ${currentYear.stem_ten_god} 세운`)
            : '';

        const keywords = {
            identity: dayMaster
                ? `${dayMaster.label} · ${dayMaster.archetype}`
                : this.extractKeyword(analysis.section_1_1, '타고난 본질'),
            relationship: analysis?.quick_summary?.actions?.[0]?.action
                || analysis?.quick_summary?.direct_answer
                || this.extractKeyword(analysis.section_2_1, '지금의 핵심 방향'),
            wealth: currentDecade && currentYear
                ? `${currentDecadeLabel} · ${currentYearLabel}`
                : this.extractKeyword(analysis.section_3_1, '일과 재물의 흐름'),
        };

        this.cardIdentity.textContent = keywords.identity;
        this.cardRelationship.textContent = keywords.relationship;
        this.cardWealth.textContent = keywords.wealth;
    }

    renderQuickSummary(summary) {
        if (!summary || typeof summary !== 'object' || !this.quickSummaryPanel) return;

        this.quickSummaryPanel.classList.remove('hidden');

        const userData = this.userData || {};
        const userName = String(userData?.name || '사용자').trim();

        // 1. 사용자 이름 바인딩
        if (this.quickUserName) {
            this.quickUserName.textContent = userName;
        }
        if (this.teaserUserName) {
            this.teaserUserName.textContent = userName;
        }

        // 2. 날카롭고 개인화된 3단락 무료 핵심 요약 구성 (자연스러운 한국어 정제)
        const strengthsList = Array.isArray(summary.strengths) ? summary.strengths : [];
        const watchoutsList = Array.isArray(summary.watchouts) ? summary.watchouts : [];
        const actionsList = Array.isArray(summary.actions) ? summary.actions : [];

        const parsedStrength = this.normalizeTraitText(strengthsList[0] || '');
        const parsedWatchout = this.normalizeTraitText(watchoutsList[0] || '');

        const strengthLabel = parsedStrength.label || '타고난 추진력과 기회 포착';
        const strengthDesc = parsedStrength.desc || '새로운 기회와 아이디어를 빠르게 포착하는 추진력';

        const watchoutLabel = parsedWatchout.label || '에너지 분산과 실행 지연';
        const watchoutDesc = parsedWatchout.desc || '일이 반복·조율 단계로 접어들 때 생각이 많아져 실행이 늦어지는 패턴';

        const rawTask = actionsList[0]?.action || '새 기회를 늘리기보다, 이미 시작한 일 하나의 완료 기준을 세우는 것';
        const asSentence = (value) => {
            const text = String(value || '').trim();
            if (!text) return '';
            return /[.!?。！？]$/.test(text) ? text : `${text}.`;
        };

        if (this.sharpSummaryHeadline) {
            this.sharpSummaryHeadline.textContent = summary.self_portrait?.headline || summary.one_line
                || `${strengthLabel}이 두드러지는 기질입니다.`;
        }

        if (this.sharpSummaryBody) {
            this.sharpSummaryBody.textContent = summary.self_portrait?.body
                || `${userName} 님에게 두드러진 강점은 ${strengthLabel}입니다. ${asSentence(strengthDesc)} 반면 ${watchoutLabel}이 강해질 때는 ${asSentence(watchoutDesc)}`;
        }

        if (this.sharpSummaryFocus) {
            this.sharpSummaryFocus.textContent = summary.self_portrait?.closing || summary.direct_answer || asSentence(rawTask);
        }

        // 3. 현실에서 보이는 신호 3대 카드 공개 문구 — 공감 레이어 추가
        if (this.sharpStrengthTitle) {
            // 강점 공개 문구: 언제 살아나는지 + 공감 힌트
            const strengthHint = summary.self_portrait?.scene || `${asSentence(strengthDesc)} 자신의 경험에서 이런 모습이 나타나는 상황을 떠올려보세요.`;
            this.sharpStrengthTitle.textContent = strengthHint;
        }
        if (this.sharpBottleneckTitle) {
            // 병목 공개 문구: 언제 나타나는지 + 공감 힌트
            const bottleneckHint = `${asSentence(watchoutDesc)} 실제로 이런 상황이 반복될 때 참고할 주의점이며, 이미 겪고 있다는 뜻은 아닙니다.`;
            this.sharpBottleneckTitle.textContent = bottleneckHint;
        }
        if (this.sharpTaskTitle) {
            // 90일 키워드 공개 문구: 방향 + 공감 힌트
            const taskHint = `${asSentence(rawTask)} 일상에서 적용할 수 있는 작은 행동부터 시작해 보세요.`;
            this.sharpTaskTitle.textContent = taskHint;
        }
        if (this.freeActionText) this.freeActionText.textContent = asSentence(rawTask);

        // insight 영역을 클릭하면 관련 상세 챕터/섹션으로 딥링크 이동
        // 강점 카드 → Chapter 3 · section_3_2 (강점이 성과로 바뀌는 순간)
        const strengthInsightEl = document.getElementById('strengthInsight');
        if (strengthInsightEl) {
            strengthInsightEl.addEventListener('click', () => this.navigateToSection(3, 'section_3_2'));
        }

        // 병목 카드 → Chapter 2 · section_2_1 (지금 가장 막혀있는 영역)
        const bottleneckInsightEl = document.querySelector('.bottleneck-insight');
        if (bottleneckInsightEl) {
            bottleneckInsightEl.addEventListener('click', () => this.navigateToSection(2, 'section_2_1'));
        }

        // 90일 키워드 카드 → Chapter 5 · section_5_2 (월별 타이밍)
        const taskInsightEl = document.querySelector('.task-insight');
        if (taskInsightEl) {
            taskInsightEl.addEventListener('click', () => this.navigateToSection(5, 'section_5_2'));
        }

        // 하위 호환 데이터 바인딩
        if (this.quickConfidence) {
            this.quickConfidence.textContent = summary.confidence === 'low'
                ? '입력 기준 · 출생 시각 미입력'
                : '입력 기준 · 출생 시각 포함';
        }
        if (this.quickDirectAnswer) {
            this.quickDirectAnswer.textContent = summary.direct_answer || summary.one_line || '직접 결론을 확인하지 못했습니다.';
        }
        if (this.quickAnswerWindow) {
            this.quickAnswerWindow.textContent = summary.answer_window?.label || '앞으로 30일';
        }
        this.renderTextList(this.quickGoodSignals, summary.good_signals);
        this.renderTextList(this.quickDecisionChangers, summary.decision_changers);
        if (this.quickOneLine) {
            this.quickOneLine.textContent = summary.one_line || '';
        }
        if (this.quickLuck) {
            this.quickLuck.textContent = summary.current_luck || '';
        }
        this.renderTextList(this.quickStrengths, summary.strengths);
        this.renderTextList(this.quickWatchouts, summary.watchouts);
        this.renderTextList(this.quickSajuBasis, summary.saju_basis);
        this.renderTextList(this.quickUserBasis, summary.user_context_basis);

        // 4. 결제 후 한눈에 정리에서 사용하는 12개월 흐름
        if (this.monthlyFlowList) {
            this.monthlyFlowList.replaceChildren();
            const moreMonths = document.getElementById('monthlyFlowMore');
            const remainingMonths = document.getElementById('remainingMonths');
            moreMonths?.replaceChildren();
            const months = Array.isArray(summary.timing_windows)
                ? summary.timing_windows.slice(0, 12)
                : [];
            if (remainingMonths) {
                remainingMonths.hidden = months.length <= 3;
                const label = remainingMonths.querySelector('summary');
                if (label) label.textContent = `이후 ${Math.max(0, months.length - 3)}개월 흐름 더 보기`;
            }

            months.forEach((month, index) => {
                const card = document.createElement('article');
                card.className = 'monthly-flow-card';
                card.classList.toggle('is-key-month', index < 3);
                card.setAttribute('role', 'listitem');

                const meta = document.createElement('span');
                const monthGanZhi = month.gan_zhi_ko ? `${month.gan_zhi_ko}(${month.gan_zhi})` : month.gan_zhi;
                meta.textContent = [month.label, monthGanZhi].filter(Boolean).join(' · ');

                const title = document.createElement('h4');
                title.textContent = month.focus || '관찰과 조정';

                const use = document.createElement('p');
                use.textContent = month.use || '';

                const watch = document.createElement('small');
                watch.textContent = month.watch ? `주의 신호 · ${month.watch}` : '';

                const boundary = document.createElement('small');
                boundary.className = 'monthly-boundary';
                boundary.textContent = month.boundary_label ? `입절 경계 · ${month.boundary_label}` : '';

                card.append(meta, title, use, watch, boundary);
                (index >= 3 && moreMonths ? moreMonths : this.monthlyFlowList).appendChild(card);
            });
        }

        this.renderTextList(this.verificationQuestionList, summary.verification_questions);
        this.restoreInterpretationFeedback();
    }

    normalizeTraitText(text) {
        if (!text) return { label: '', desc: '' };
        const str = String(text).trim();
        const translations = {
            '비견': '자기 주도성',
            '겁재': '승부욕과 순발력',
            '식신': '실무 실행력',
            '상관': '창의적 표현력',
            '편재': '기회 포착과 사업 감각',
            '정재': '현실적 관리와 안정감',
            '편관': '위기 돌파와 책임감',
            '정관': '원칙과 신뢰 구축',
            '편인': '독창적 직관과 통찰력',
            '정인': '지식 습득과 포용력',
        };

        const parenMatch = str.match(/^([가-힣]+)\s*\(([^)]+)\)$/);
        if (parenMatch) {
            const rawLabel = parenMatch[1];
            const label = translations[rawLabel] || rawLabel;
            return { label, desc: parenMatch[2].trim() };
        }

        const colonIdx = str.indexOf(':');
        if (colonIdx > 0 && colonIdx < 30) {
            const rawLabel = str.slice(0, colonIdx).trim();
            const label = translations[rawLabel] || rawLabel;
            return { label, desc: str.slice(colonIdx + 1).trim() };
        }

        return { label: '', desc: str };
    }

    renderTextList(target, items) {
        if (!target) return;
        target.replaceChildren();
        const values = Array.isArray(items) ? items.filter(Boolean) : [];
        values.forEach((value) => {
            const item = document.createElement('li');
            const { label, desc } = this.normalizeTraitText(value);
            if (label) {
                const strong = document.createElement('strong');
                strong.textContent = label;
                item.append(strong, document.createTextNode(`: ${desc}`));
            } else {
                item.textContent = desc;
            }
            target.appendChild(item);
        });
    }

    feedbackStorageKey() {
        return `book-saju-feedback:${this.currentTaskId || 'current'}`;
    }

    saveInterpretationFeedback(value) {
        if (!['match', 'different', 'unsure'].includes(value)) return;
        try {
            localStorage.setItem(this.feedbackStorageKey(), value);
        } catch {
            // The feedback remains selected for this view even when storage is unavailable.
        }
        this.applyInterpretationFeedback(value);
        if (this.feedbackStatus) {
            this.feedbackStatus.textContent = '현재 브라우저에 확인 결과를 저장했습니다.';
        }
    }

    restoreInterpretationFeedback() {
        let value = '';
        try {
            value = localStorage.getItem(this.feedbackStorageKey()) || '';
        } catch {
            value = '';
        }
        this.applyInterpretationFeedback(value);
    }

    applyInterpretationFeedback(value) {
        this.feedbackButtons.forEach((button) => {
            button.setAttribute('aria-pressed', String(button.dataset.reportFeedback === value));
        });
    }

    renderSajuBasis(profile) {
        if (!profile || !this.sajuBasisPanel) return;

        const dayMaster = profile.day_master || {};
        if (this.dayMasterSummary) {
            this.dayMasterSummary.textContent = [dayMaster.label, dayMaster.archetype]
                .filter(Boolean)
                .join(' · ');
        }

        if (this.pillarGrid) {
            this.pillarGrid.replaceChildren();
            const pillars = Array.isArray(profile.pillars) ? profile.pillars : [];
            pillars.forEach((pillar) => {
                const item = document.createElement('article');
                item.className = 'pillar-card';

                const label = document.createElement('span');
                label.textContent = pillar.label || '기둥';
                const ganZhi = document.createElement('strong');
                ganZhi.textContent = pillar.gan_zhi_ko ? `${pillar.gan_zhi_ko} (${pillar.gan_zhi})` : (pillar.gan_zhi || '—');
                const detail = document.createElement('small');
                detail.textContent = [
                    `천간 ${pillar.stem_ten_god || '미상'}`,
                    `지지 본기 ${pillar.branch_main_ten_god || '미상'}`,
                ].join(' · ');

                item.append(label, ganZhi, detail);
                this.pillarGrid.appendChild(item);
            });

            if (Array.isArray(profile.missing_pillars) && profile.missing_pillars.includes('시주')) {
                const item = document.createElement('article');
                item.className = 'pillar-card missing-pillar';
                const label = document.createElement('span');
                label.textContent = '시주';
                const value = document.createElement('strong');
                value.textContent = '미상';
                const detail = document.createElement('small');
                detail.textContent = '출생시간 미입력 · 해석에서 제외';
                item.append(label, value, detail);
                this.pillarGrid.appendChild(item);
            }
        }

        if (this.elementBalance) {
            this.elementBalance.replaceChildren();
            const hanja = { 목: '木', 화: '火', 토: '土', 금: '金', 수: '水' };
            Object.entries(profile.element_counts || {}).forEach(([element, count]) => {
                const item = document.createElement('span');
                const isMonthCommand = profile.month_command?.element === element;
                item.textContent = `${hanja[element] || element} ${element} ${count}자${isMonthCommand ? ' · 월령' : ''}`;
                this.elementBalance.appendChild(item);
            });
        }

        if (this.sajuStandardNote) {
            this.sajuStandardNote.textContent = [
                profile.calculation_standard,
                profile.analysis_scope,
                ...(Array.isArray(profile.calculation_basis) ? profile.calculation_basis : []),
                profile.element_note,
                profile.interpretation_limits,
            ].filter(Boolean).join(' · ');
        }
        this.sajuBasisPanel.classList.remove('hidden');
    }

    renderPracticalSummary(userData, analysis) {
        const summary = this.normalizePracticalSummary(
            analysis?.practical_summary,
            userData,
            analysis,
        );
        this.practicalSummaryData = summary;

        if (this.typeOwner) {
            this.typeOwner.textContent = userData?.name ? `${userData.name}님의 기질` : '나의 기질';
        }
        if (this.typeLabel) this.typeLabel.textContent = summary.type.label;
        if (this.typeTagline) this.typeTagline.textContent = summary.type.tagline;

        if (this.typeTraits) {
            this.typeTraits.replaceChildren();
            summary.type.traits.forEach((trait) => {
                const item = document.createElement('span');
                item.textContent = `#${String(trait).replace(/^#/, '')}`;
                this.typeTraits.appendChild(item);
            });
        }

        if (this.profileChart) {
            this.profileChart.replaceChildren();
            const accessibleValues = [];
            summary.chart.forEach((metric) => {
                const row = document.createElement('div');
                row.className = 'chart-row';

                const label = document.createElement('span');
                label.className = 'chart-label';
                label.textContent = metric.label;

                const track = document.createElement('span');
                track.className = 'chart-track';
                const bar = document.createElement('span');
                bar.style.width = `${metric.bar_percent}%`;
                track.appendChild(bar);

                const value = document.createElement('span');
                value.className = 'chart-value';
                value.textContent = `${metric.value}${metric.unit}${metric.is_month_command ? ' · 월령' : ''}`;

                row.append(label, track, value);
                this.profileChart.appendChild(row);
                accessibleValues.push(`${metric.label} ${value.textContent}`);
            });
            this.profileChart.setAttribute('aria-label', accessibleValues.join(', '));
        }
        if (this.profileChartNote) {
            this.profileChartNote.textContent = summary.chart_note;
        }

        if (this.actionCards) {
            this.actionCards.replaceChildren();
            summary.actions.forEach((action) => {
                const card = document.createElement('article');
                card.className = 'action-card';

                const period = document.createElement('span');
                period.textContent = action.period;
                const timing = document.createElement('small');
                timing.textContent = action.timing;
                const title = document.createElement('h4');
                title.textContent = action.title;
                const copy = document.createElement('p');
                copy.textContent = action.action;

                const checkButton = document.createElement('button');
                checkButton.type = 'button';
                checkButton.className = 'action-check-button';
                checkButton.setAttribute('aria-pressed', 'false');
                checkButton.textContent = '완료 표시';
                checkButton.addEventListener('click', () => {
                    const completed = checkButton.getAttribute('aria-pressed') !== 'true';
                    checkButton.setAttribute('aria-pressed', String(completed));
                    checkButton.textContent = completed ? '완료됨' : '완료 표시';
                    card.classList.toggle('is-complete', completed);
                });

                card.append(period, timing, title, copy, checkButton);
                this.actionCards.appendChild(card);
            });
        }

        if (this.socialHeadline) {
            this.socialHeadline.textContent = summary.social_profile.headline;
        }
        if (this.socialProfileTitle) {
            this.socialProfileTitle.textContent = summary.social_profile.summary;
        }
        if (this.socialTags) {
            this.socialTags.textContent = summary.social_profile.hashtags.join(' ');
        }
        this.socialShareText = summary.social_profile.share_text;
    }

    normalizePracticalSummary(rawSummary, userData, analysis) {
        const fallback = this.buildPracticalSummaryFallback(userData, analysis);
        if (!rawSummary || typeof rawSummary !== 'object') return fallback;

        const rawType = rawSummary.type && typeof rawSummary.type === 'object'
            ? rawSummary.type
            : {};
        const chart = Array.isArray(rawSummary.chart)
            ? rawSummary.chart
                .filter((metric) => metric && typeof metric.label === 'string')
                .slice(0, 5)
                .map((metric) => {
                    const hasCount = Number.isFinite(Number(metric.count));
                    const value = hasCount
                        ? Math.max(0, Number(metric.count))
                        : Math.max(0, Math.min(Number(metric.value) || 0, 100));
                    return {
                        label: metric.label,
                        value,
                        unit: hasCount ? '자' : '',
                        bar_percent: Math.max(
                            0,
                            Math.min(Number(metric.bar_percent ?? metric.value) || 0, 100),
                        ),
                        is_month_command: Boolean(metric.is_month_command),
                    };
                })
            : [];
        const actions = Array.isArray(rawSummary.actions)
            ? rawSummary.actions
                .filter((action) => action && typeof action.title === 'string')
                .slice(0, 3)
                .map((action, index) => ({
                    period: String(action.period || fallback.actions[index]?.period || 'ACTION'),
                    timing: String(action.timing || fallback.actions[index]?.timing || ''),
                    title: action.title,
                    action: String(action.action || ''),
                }))
            : [];
        const social = rawSummary.social_profile && typeof rawSummary.social_profile === 'object'
            ? rawSummary.social_profile
            : {};

        const normalized = {
            type: {
                label: String(rawType.label || fallback.type.label),
                tagline: String(rawType.tagline || fallback.type.tagline),
                traits: Array.isArray(rawType.traits) && rawType.traits.length
                    ? rawType.traits.slice(0, 4).map(String)
                    : fallback.type.traits,
            },
            chart: chart.length ? chart : fallback.chart,
            chart_note: String(rawSummary.chart_note || fallback.chart_note),
            actions: actions.length ? actions : fallback.actions,
            social_profile: {
                headline: String(social.headline || fallback.social_profile.headline),
                summary: String(social.summary || fallback.social_profile.summary),
                hashtags: Array.isArray(social.hashtags) && social.hashtags.length
                    ? social.hashtags.slice(0, 5).map(String)
                    : fallback.social_profile.hashtags,
                share_text: String(social.share_text || ''),
            },
        };
        if (!normalized.social_profile.share_text) {
            normalized.social_profile.share_text = [
                normalized.social_profile.headline,
                normalized.social_profile.summary,
                normalized.social_profile.hashtags.join(' '),
            ].join('\n');
        }
        return normalized;
    }

    buildPracticalSummaryFallback(userData, analysis) {
        const name = userData?.name || '나';
        const keyword = this.extractKeyword(analysis?.section_1_1, '나만의 리듬 탐색가');
        const label = keyword.replace(/형(?=[가-힣])/u, '형 ') || '나만의 리듬 탐색가';
        const relationship = {
            single: '나만의 속도를 지키며 관계를 여는',
            dating: '서로의 표현을 대화로 번역하는',
            married: '일상의 합의를 신뢰로 쌓는',
        }[userData?.relationship_status] || '자기 기준을 차분히 세우는';
        const elementCounts = analysis?.saju_profile?.element_counts || {};
        const labels = [
            ['목', '木'],
            ['화', '火'],
            ['토', '土'],
            ['금', '金'],
            ['수', '水'],
        ];
        const maxCount = Math.max(1, ...labels.map(([element]) => Number(elementCounts[element]) || 0));
        const summary = `나는 ${relationship} ${label}입니다. 생각을 짧게 적고 작게 실행할 때 나다운 흐름이 살아납니다.`;
        const hashtags = ['#나의결', `#${label.replace(/\s/g, '')}`, '#나를읽는시간'];
        return {
            type: {
                label,
                tagline: '충분히 살핀 뒤 내 기준이 선명해지면, 작은 실행을 오래 이어가는 사람입니다.',
                traits: ['관찰', '기준', '꾸준함'],
            },
            chart: labels.map(([element, hanja]) => ({
                label: `${element.toUpperCase()} · ${hanja}`,
                value: Number(elementCounts[element]) || 0,
                unit: '자',
                bar_percent: Math.round(((Number(elementCounts[element]) || 0) / maxCount) * 100),
                is_month_command: false,
            })),
            chart_note: analysis?.saju_profile?.element_note
                || '오행의 보이는 글자 수를 표시하며 강약·성격 점수로 해석하지 않습니다.',
            actions: [
                { period: 'TODAY', timing: '오늘 · 10분', title: '가장 작은 첫 행동', action: '미뤄둔 선택 하나를 적고, 되돌릴 수 있다면 10분 안에 시작하세요.' },
                { period: 'THIS WEEK', timing: '이번 주 · 한 번', title: '관계의 문 열기', action: '고마움이나 원하는 행동 하나를 추측 없이 구체적인 문장으로 전해보세요.' },
                { period: 'THIS MONTH', timing: '이번 달 · 30분', title: '내 기준 적기', action: '돈·시간·에너지를 어디에 쓸지 세 가지 기준으로 적고 다시 볼 날짜를 정하세요.' },
            ],
            social_profile: {
                headline: `${name} | ${label}`,
                summary,
                hashtags,
                share_text: [`${name} | ${label}`, summary, hashtags.join(' ')].join('\n'),
            },
        };
    }

    extractKeyword(text, defaultText) {
        if (!text) return defaultText;

        const hashtagMatch = text.match(/#([\w가-힣]+)/);
        if (hashtagMatch) {
            return hashtagMatch[1];
        }

        const firstSentence = text
            .split(/\n|\./)
            .map((segment) => segment.replace(/[#*`>\-]/g, '').trim())
            .find(Boolean);

        if (firstSentence && firstSentence.length <= 22) {
            return firstSentence;
        }

        return defaultText;
    }

    buildBookPages(analysis) {
        this.pages = [];
        const structure = analysis.table_of_contents?.chapters || [];
        const chapters = structure.length > 0 ? structure : this.getFallbackChapters(analysis);

        chapters.forEach((chapter, chapterIndex) => {
            const chapterNumber = this.getChapterNumber(chapter, chapterIndex);
            const chapterTitle = this.getChapterTitle(chapter, chapterNumber);
            const sections = Array.isArray(chapter?.sections) ? [...chapter.sections] : [];

            if (sections.length === 0) {
                Object.keys(analysis)
                    .filter((key) => key.startsWith(`section_${chapterNumber}_`))
                    .sort((left, right) => this.compareSectionIds(left, right))
                    .forEach((key) => sections.push(key));
            }

            sections.forEach((section) => {
                let sectionId = '';
                let title = '';

                if (typeof section === 'string') {
                    sectionId = section;
                    title = this.getSectionTitleFallback(sectionId);
                } else {
                    sectionId = section?.id || '';
                    title = section?.title || section?.topic || this.getSectionTitleFallback(sectionId);
                }

                const markdown = this.removeStandaloneBasisSection(analysis[sectionId]);
                if (!markdown) return;

                this.pages.push({
                    chapter: chapterNumber,
                    chapterTitle,
                    id: sectionId,
                    title,
                    markdown,
                });
            });
        });

        if (!this.pages.length) {
            this.showError('표시할 분석 섹션을 찾지 못했습니다.');
            return false;
        }

        this.renderChapterTabs();
        this.renderPage(0);
        this.switchViewMode(this.currentViewMode, false);
        this.switchStep(1, false);
        return true;
    }

    removeStandaloneBasisSection(markdown) {
        return String(markdown || '')
            .replace(
                /(?:^|\n)###\s+(?:사주 근거와 운의 해석|사주 근거|명리 근거)\s*\n[\s\S]*?(?=\n#{2,3}\s+|$)/g,
                '\n',
            )
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    getFallbackChapters(analysis) {
        const chapterNumbers = new Set();

        Object.keys(analysis || {}).forEach((key) => {
            const match = key.match(/^section_(\d+)_/);
            if (match) {
                chapterNumbers.add(Number.parseInt(match[1], 10));
            }
        });

        const sortedNumbers = [...chapterNumbers]
            .filter((value) => Number.isInteger(value))
            .sort((left, right) => left - right);

        return sortedNumbers.length ? sortedNumbers : [1, 2, 3, 4, 5];
    }

    getChapterNumber(chapter, chapterIndex) {
        if (typeof chapter === 'number' && Number.isInteger(chapter)) {
            return chapter;
        }

        const candidates = [
            chapter?.chapter,
            chapter?.number,
            chapter?.id,
            chapterIndex + 1,
        ];

        for (const candidate of candidates) {
            const match = String(candidate || '').match(/\d+/);
            if (match) {
                return Number.parseInt(match[0], 10);
            }
        }

        return chapterIndex + 1;
    }

    getChapterTitle(chapter, chapterNumber) {
        if (chapter && typeof chapter === 'object') {
            const title = chapter.title || chapter.name || chapter.topic;
            if (typeof title === 'string' && title.trim()) {
                return title.trim();
            }
        }

        return this.getChapterTitleFallback(chapterNumber);
    }

    getChapterTitleFallback(chapterNumber) {
        const titleMap = {
            1: '타고난 기질과 세상이 보는 나',
            2: '지금의 흐름과 선택을 점검하기',
            3: '일과 재물이 풀리는 전략적 방향',
            4: '내 삶의 인연과 공간의 조화',
            5: '신체 리듬 회복과 나아갈 방향',
        };

        return titleMap[chapterNumber] || `챕터 ${chapterNumber}`;
    }

    compareSectionIds(left, right) {
        const leftParts = String(left).match(/^section_(\d+)_(\d+)/);
        const rightParts = String(right).match(/^section_(\d+)_(\d+)/);

        if (!leftParts || !rightParts) {
            return String(left).localeCompare(String(right));
        }

        const leftChapter = Number.parseInt(leftParts[1], 10);
        const rightChapter = Number.parseInt(rightParts[1], 10);
        if (leftChapter !== rightChapter) {
            return leftChapter - rightChapter;
        }

        return Number.parseInt(leftParts[2], 10) - Number.parseInt(rightParts[2], 10);
    }

    renderChapterTabs() {
        if (!this.chapterTabs) return;

        const chapters = [];
        const seen = new Set();

        this.pages.forEach((page) => {
            if (seen.has(page.chapter)) return;
            seen.add(page.chapter);
            chapters.push({
                number: page.chapter,
                title: page.chapterTitle || this.getChapterTitleFallback(page.chapter),
            });
        });

        this.chapterTabs.replaceChildren();

        chapters.forEach((chapter, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'tab-btn';
            button.dataset.chapter = String(chapter.number);
            const shortTitles = { 1: '성향', 2: '현재 흐름', 3: '일과 재물', 4: '관계·환경', 5: '실천 계획' };
            button.textContent = shortTitles[chapter.number] || chapter.title;
            button.title = `${chapter.number}. ${chapter.title}`;
            button.setAttribute('aria-label', `${button.textContent} — ${chapter.title}`);
            button.classList.toggle('active', index === 0);
            this.chapterTabs.appendChild(button);
        });

        if (this.sectionJumpSelect) {
            this.sectionJumpSelect.replaceChildren();
            this.pages.forEach((page, index) => {
                const option = document.createElement('option');
                option.value = String(index);
                option.textContent = `${index + 1}. ${page.title}`;
                this.sectionJumpSelect.appendChild(option);
            });
            this.sectionJumpSelect.value = String(this.currentPageIndex);
        }
    }

    getSectionTitleFallback(id) {
        const titleMap = {
            section_1_1: '태어날 때부터 지닌 본연의 기운',
            section_1_2: '세상과 사람들이 바라보는 나',
            section_1_3: '겉으로 보이는 행동과 혼자 있을 때의 생각',
            section_2_1: '지금 확인할 흐름과 진행 조건',
            section_2_2: '반복되는 상황과 조정할 수 있는 조건',
            section_2_3: '나의 강점을 활용하는 작은 전환',
            section_3_1: '나는 어떤 환경에서 일해야 가장 빛날까?',
            section_3_2: '내 고유한 재능이 성과와 돈으로 바뀌는 순간',
            section_3_3: '버텨야 할 타이밍과 과감히 움직여야 할 타이밍',
            section_3_4: '들어온 돈을 지키는 흐름과 관리 습관',
            section_4_1: '마음이 열리는 순간과 나의 표현 방식',
            section_4_2: '앞으로 내 삶에 들어올 좋은 인연의 신호',
            section_4_3: '내 기운을 살려주는 공간 에너지와 일상 정돈법',
            section_5_1: '내 생활 리듬과 회복을 돕는 쉼 루틴',
            section_5_2: '앞으로 3개월, 내가 주목해야 할 월별 타이밍',
            section_5_3: '선택한 변화를 이어가는 90일 실행 계획',
            section_5_4: '나만의 속도로 나아가기 위한 마지막 제언',
            section_5_5: '지금 가장 궁금한 이야기',
        };

        return titleMap[id] || '삶의 한 장면';
    }

    renderPage(index) {
        if (index < 0 || index >= this.pages.length) return;

        this.currentPageIndex = index;
        const page = this.pages[index];
        if (this.sectionJumpSelect) {
            this.sectionJumpSelect.value = String(index);
        }

        this.pageChapterEl.textContent = `${page.chapter}장`;
        this.pageTitleEl.textContent = page.title;
        this.renderMarkdown(this.stripDuplicatePageHeading(page.markdown, page.title));

        if (this.pageNumberEl) {
            this.pageNumberEl.textContent = `${index + 1} / ${this.pages.length}`;
        }
        if (this.pageChapterMetaEl) {
            this.pageChapterMetaEl.textContent = `${page.chapter}장 · ${page.chapterTitle}`;
        }
        if (this.readingProgressBar) {
            this.readingProgressBar.style.width = `${((index + 1) / this.pages.length) * 100}%`;
        }
        if (this.previousPageButton) {
            this.previousPageButton.disabled = index === 0;
        }
        if (this.nextPageButton) {
            const isLastPage = index === this.pages.length - 1;
            this.nextPageButton.disabled = false;
            this.nextPageButton.textContent = isLastPage
                ? '한눈에 요약 보기 →'
                : '다음 이야기 →';
            this.nextPageButton.classList?.toggle('summary-nav', isLastPage);
            this.nextPageButton.setAttribute?.(
                'aria-label',
                isLastPage ? '책을 덮기 전 한눈에 보는 요약으로 이동' : '다음 이야기로 이동',
            );
        }

        document.querySelectorAll('.tab-btn').forEach((button) => {
            const chapter = Number.parseInt(button.dataset.chapter || '', 10);
            button.classList.toggle('active', chapter === page.chapter);
            if (chapter === page.chapter) {
                button.setAttribute('aria-current', 'page');
            } else {
                button.removeAttribute('aria-current');
            }
            if (chapter === page.chapter) {
                button.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }
        });
    }

    scrollBookIntoView() {
        const contentArea = document.getElementById('analysisContent');
        if (!contentArea) return;

        const offsetPosition = contentArea.getBoundingClientRect().top
            + window.scrollY
            - 132;
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
    }

    stripDuplicatePageHeading(markdown, title) {
        if (typeof markdown !== 'string') return '';
        let cleaned = markdown.trimStart();
        const hashMatch = cleaned.match(/^(#[^\n#]+(?:\s+#[^\n#]+)*)\s*\n+/);
        let prefix = '';
        if (hashMatch) {
            prefix = hashMatch[1] + '\n\n';
            cleaned = cleaned.slice(hashMatch[0].length).trimStart();
        }
        const headingMatch = cleaned.match(/^##\s+(.+?)(?:\n{2,}|\n|$)/);
        if (headingMatch) {
            const normalize = (value) => String(value || '')
                .replace(/[*`#]/g, '')
                .replace(/\s+/g, ' ')
                .trim();
            const normMatch = normalize(headingMatch[1]);
            const normTitle = normalize(title);
            const isSimilar = !normTitle
                || normMatch === normTitle
                || normMatch.includes('공간 에너지')
                || normMatch.includes('본연의 기운')
                || normMatch.includes('바라보는 나')
                || normMatch.includes('진짜 속마음')
                || normMatch.includes('정체')
                || normMatch.includes('원인')
                || normMatch.includes('돌파')
                || normMatch.includes('환경')
                || normMatch.includes('재능')
                || normMatch.includes('타이밍')
                || normMatch.includes('재물')
                || normMatch.includes('심리 패턴')
                || normMatch.includes('인연의 신호')
                || normMatch.includes('쉼 루틴')
                || normMatch.includes('월별 타이밍')
                || normMatch.includes('방어 계획')
                || normMatch.includes('마지막 제언');
            if (isSimilar) {
                cleaned = cleaned.slice(headingMatch[0].length).trimStart();
            }
        }
        return prefix + cleaned;
    }

    goToNextDestination({ focusHeading = false } = {}) {
        const isLastPage = this.currentPageIndex === this.pages.length - 1;
        if (isLastPage) {
            this.scrollToPracticalReport({ focusHeading });
            return;
        }

        this.renderPage(this.currentPageIndex + 1);
        this.scrollBookIntoView();
    }

    scrollToPracticalReport({ focusHeading = false } = {}) {
        const target = this.practicalReport || document.getElementById('practicalReport');
        if (!target) return;

        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (!focusHeading) return;

        window.setTimeout(() => {
            const heading = this.practicalReportTitle || document.getElementById('practicalReportTitle');
            heading?.focus?.({ preventScroll: true });
        }, 450);
    }

    renderMarkdown(markdown) {
        if (!this.pageContentEl) return;
        this.renderMarkdownIntoContainer(this.pageContentEl, markdown);
    }

    renderMarkdownIntoContainer(target, markdown) {
        if (!target) return;
        target.replaceChildren();

        const blocks = markdown
            .split(/\n{2,}/)
            .map((block) => block.trim())
            .filter(Boolean);

        if (!blocks.length) {
            const paragraph = document.createElement('p');
            paragraph.textContent = '표시할 내용이 없습니다.';
            target.appendChild(paragraph);
            return;
        }

        for (let index = 0; index < blocks.length; index += 1) {
            const block = blocks[index];
            const basisHeading = block.match(/^###\s+(?:사주 근거|명리 근거)\s*(?:\n([\s\S]*))?$/);
            if (basisHeading) {
                const details = document.createElement('details');
                details.className = 'technical-basis-details';
                const summary = document.createElement('summary');
                summary.textContent = '계산에 사용한 사주 용어 보기';
                const content = document.createElement('div');
                content.className = 'technical-basis-content';

                if (basisHeading[1]?.trim()) {
                    this.appendMarkdownBlock(content, basisHeading[1].trim());
                }
                while (index + 1 < blocks.length && !/^#{2,3}\s+/.test(blocks[index + 1])) {
                    index += 1;
                    this.appendMarkdownBlock(content, blocks[index]);
                }

                details.append(summary, content);
                target.appendChild(details);
                continue;
            }

            this.appendMarkdownBlock(target, block);
        }
    }

    renderAllSections() {
        if (!this.allSectionsViewer) return;
        this.allSectionsViewer.replaceChildren();

        const chaptersMap = new Map();
        this.pages.forEach((page, pageIndex) => {
            if (!chaptersMap.has(page.chapter)) {
                chaptersMap.set(page.chapter, {
                    chapterNumber: page.chapter,
                    chapterTitle: page.chapterTitle,
                    pages: [],
                });
            }
            chaptersMap.get(page.chapter).pages.push({ ...page, pageIndex });
        });

        chaptersMap.forEach((chapterGroup) => {
            const chapterSection = document.createElement('section');
            chapterSection.className = 'chapter-scroll-section';
            chapterSection.id = `chapter-section-${chapterGroup.chapterNumber}`;

            const cardsList = document.createElement('div');
            cardsList.className = 'chapter-sections-list';

            chapterGroup.pages.forEach((page) => {
                const card = document.createElement('article');
                card.className = 'book-page section-scroll-card';
                card.id = `section-card-${page.id}`;

                const cardHeader = document.createElement('header');
                cardHeader.className = 'page-header';

                const chapterLabel = document.createElement('span');
                chapterLabel.className = 'chapter-label';
                chapterLabel.textContent = `${page.chapter}장`;

                const title = document.createElement('h2');
                title.className = 'section-title';
                title.textContent = page.title;

                cardHeader.append(chapterLabel, title);

                const ornament = document.createElement('div');
                ornament.className = 'page-ornament';
                ornament.setAttribute('aria-hidden', 'true');
                ornament.innerHTML = '<span>木</span><span>火</span><span>土</span><span>金</span><span>水</span>';

                const body = document.createElement('div');
                body.className = 'page-body';
                this.renderMarkdownIntoContainer(body, this.stripDuplicatePageHeading(page.markdown, page.title));

                card.append(cardHeader, ornament, body);
                cardsList.appendChild(card);
            });

            chapterSection.appendChild(cardsList);
            this.allSectionsViewer.appendChild(chapterSection);
        });
    }

    splitIntoSentences(text) {
        if (typeof text !== 'string') return [];
        const trimmed = text.trim();
        if (!trimmed) return [];
        const parts = trimmed.split(/(?<!\b\d+\.)(?<!\b[A-Za-z]\.)(?<!(?:^|\s|[(\[])[가나다라마바사아자차카타파하ㄱ-ㅎ]\.)(?<![\(\[]\d+[\)\]]\.)(?<!\b(?:No|Dr|Mr|Ms|Prof|vs|etc|vol|ver|p|ref)\.)(?<=[.!?][)"'”’]?)\s+(?=[가-힣A-Za-z0-9"“'‘(（\[<*`])/);
        return parts.map((p) => p.trim()).filter(Boolean);
    }

    appendMarkdownBlock(target, block) {
        const lines = block
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean);

        if (!lines.length) return;

        if (lines.every((line) => line.startsWith('- '))) {
            const list = document.createElement('ul');
            lines.forEach((line) => {
                const item = document.createElement('li');
                const rawContent = line.replace(/^- /, '');
                const sentences = this.splitIntoSentences(rawContent);
                sentences.forEach((sentence, sIdx) => {
                    this.appendInlineContent(item, sentence);
                    if (sIdx < sentences.length - 1) item.appendChild(document.createElement('br'));
                });
                list.appendChild(item);
            });
            target.appendChild(list);
            return;
        }

        if (lines.every((line) => /^\d+\.\s/.test(line))) {
            const list = document.createElement('ol');
            lines.forEach((line) => {
                const item = document.createElement('li');
                const rawContent = line.replace(/^\d+\.\s/, '');
                const sentences = this.splitIntoSentences(rawContent);
                sentences.forEach((sentence, sIdx) => {
                    this.appendInlineContent(item, sentence);
                    if (sIdx < sentences.length - 1) item.appendChild(document.createElement('br'));
                });
                list.appendChild(item);
            });
            target.appendChild(list);
            return;
        }

        if (lines.some((line) => /^>\s*/.test(line))) {
            let group = [];
            let quoteGroup = /^>\s*/.test(lines[0]);
            const flush = () => {
                const visibleLines = group.filter((line) => !this.isEmptyReasonLine(line));
                group = [];
                if (!visibleLines.length) return;
                const container = document.createElement(quoteGroup ? 'blockquote' : 'p');
                const allSentences = [];
                visibleLines.forEach((line) => {
                    const cleanLine = line.replace(/^>\s*/, '');
                    allSentences.push(...this.splitIntoSentences(cleanLine));
                });
                allSentences.forEach((sentence, sIdx) => {
                    this.appendInlineContent(container, sentence);
                    if (sIdx < allSentences.length - 1) container.appendChild(document.createElement('br'));
                });
                target.appendChild(container);
            };
            lines.forEach((line) => {
                const isQuote = /^>\s*/.test(line);
                if (group.length && isQuote !== quoteGroup) flush();
                quoteGroup = isQuote;
                group.push(line);
            });
            flush();
            return;
        }

        const headingMatch = lines[0].match(/^(#{2,3})\s+(.+)$/);
        if (headingMatch) {
            const heading = document.createElement(headingMatch[1].length === 2 ? 'h2' : 'h3');
            this.appendInlineContent(heading, headingMatch[2]);
            target.appendChild(heading);

            if (lines.length > 1) {
                const remainingLines = lines.slice(1);
                if (remainingLines.every((line) => line.startsWith('- '))) {
                    const list = document.createElement('ul');
                    remainingLines.forEach((line) => {
                        const item = document.createElement('li');
                        const rawContent = line.replace(/^- /, '');
                        const sentences = this.splitIntoSentences(rawContent);
                        sentences.forEach((sentence, sIdx) => {
                            this.appendInlineContent(item, sentence);
                            if (sIdx < sentences.length - 1) item.appendChild(document.createElement('br'));
                        });
                        list.appendChild(item);
                    });
                    target.appendChild(list);
                } else if (remainingLines.every((line) => /^\d+\.\s/.test(line))) {
                    const list = document.createElement('ol');
                    remainingLines.forEach((line) => {
                        const item = document.createElement('li');
                        const rawContent = line.replace(/^\d+\.\s/, '');
                        const sentences = this.splitIntoSentences(rawContent);
                        sentences.forEach((sentence, sIdx) => {
                            this.appendInlineContent(item, sentence);
                            if (sIdx < sentences.length - 1) item.appendChild(document.createElement('br'));
                        });
                        list.appendChild(item);
                    });
                    target.appendChild(list);
                } else {
                    const paragraph = document.createElement('p');
                    const allSentences = [];
                    remainingLines.forEach((line) => {
                        allSentences.push(...this.splitIntoSentences(line));
                    });
                    allSentences.forEach((sentence, sIdx) => {
                        this.appendInlineContent(paragraph, sentence);
                        if (sIdx < allSentences.length - 1) paragraph.appendChild(document.createElement('br'));
                    });
                    target.appendChild(paragraph);
                }
            }
            return;
        }

        const paragraph = document.createElement('p');
        const allSentences = [];
        lines.forEach((line) => {
            allSentences.push(...this.splitIntoSentences(line));
        });
        allSentences.forEach((sentence, sIdx) => {
            this.appendInlineContent(paragraph, sentence);
            if (sIdx < allSentences.length - 1) {
                paragraph.appendChild(document.createElement('br'));
            }
        });
        target.appendChild(paragraph);
    }

    isEmptyReasonLine(line) {
        return /^>\s*\*\*(?:사주에서 본 이유|입력 정보에서 본 이유|명리 근거|사용자 맥락)\*\*:\s*$/.test(
            String(line || '').trim(),
        );
    }

    appendInlineContent(element, text) {
        const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
        tokens.forEach((token) => {
            const strongMatch = token.match(/^\*\*(.+)\*\*$/);
            if (strongMatch) {
                const strong = document.createElement('strong');
                strong.textContent = strongMatch[1];
                element.appendChild(strong);
                return;
            }

            const codeMatch = token.match(/^`(.+)`$/);
            if (codeMatch) {
                const inlineTag = document.createElement('code');
                inlineTag.className = 'inline-tag';
                inlineTag.textContent = codeMatch[1];
                element.appendChild(inlineTag);
                return;
            }

            element.appendChild(document.createTextNode(token));
        });
    }

    renderMarkdownToHtml(markdown) {
        const output = document.createElement('div');
        const previousTarget = this.pageContentEl;
        this.pageContentEl = output;
        try {
            this.renderMarkdown(markdown);
            return output.innerHTML;
        } finally {
            this.pageContentEl = previousTarget;
        }
    }

    scrollToChapter(chapterNum) {
        if (this.currentViewMode === 'all') {
            const chapterEl = document.getElementById(`chapter-section-${chapterNum}`);
            if (chapterEl) {
                const offset = chapterEl.getBoundingClientRect().top + window.scrollY - 130;
                window.scrollTo({ top: offset, behavior: 'smooth' });
            }
        } else {
            const pageIndex = this.pages.findIndex((page) => page.chapter === chapterNum);
            if (pageIndex !== -1) {
                this.renderPage(pageIndex);
                this.scrollBookIntoView();
            }
        }

        document.querySelectorAll('.tab-btn').forEach((button) => {
            const chapter = Number.parseInt(button.dataset.chapter || '', 10);
            button.classList.toggle('active', chapter === chapterNum);
            if (chapter === chapterNum) {
                button.setAttribute('aria-current', 'page');
            } else {
                button.removeAttribute('aria-current');
            }
        });
    }

    /**
     * 프리미엄 해제 후 특정 섹션으로 딥링크 이동
     * @param {number} chapterNum - 이동할 챕터 번호 (1~5)
     * @param {string|null} sectionId - 이동할 섹션 ID (예: 'section_2_1'), null이면 챕터 상단으로
     */
    navigateToSection(chapterNum, sectionId = null) {
        // 1. 프리미엄 해제
        this.premiumUnlocked = true;
        if (this.analysisData) {
            if (!this.analysisData.access) this.analysisData.access = {};
            this.analysisData.access.premium_unlocked = true;
            this.analysisData.premium_unlocked = true;
        }
        this.configurePremiumAccess(this.analysisData);

        // 2. STEP 2로 이동 (스크롤 없이)
        this.switchStep(2, false);

        // 3. 렌더링 후 해당 섹션/챕터로 스크롤
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (sectionId) {
                    // 섹션 카드로 바로 이동 (all/card 뷰)
                    const sectionCard = document.getElementById(`section-card-${sectionId}`);
                    if (sectionCard) {
                        const offset = sectionCard.getBoundingClientRect().top + window.scrollY - 130;
                        window.scrollTo({ top: Math.max(0, offset), behavior: 'smooth' });
                        // 챕터 탭 활성화
                        document.querySelectorAll('.tab-btn').forEach((btn) => {
                            const ch = Number.parseInt(btn.dataset.chapter || '', 10);
                            btn.classList.toggle('active', ch === chapterNum);
                            if (ch === chapterNum) btn.setAttribute('aria-current', 'page');
                            else btn.removeAttribute('aria-current');
                        });
                        return;
                    }
                }
                // 섹션을 못 찾으면 챕터 상단으로
                this.scrollToChapter(chapterNum);
            });
        });
    }


    /* ==========================================================================
       Audiobook (TTS) Implementation
       ========================================================================== */
    startAudiobook(pageIndex = this.currentPageIndex) {
        if (!this.premiumUnlocked) {
            this.requestPremiumAccess(2);
            return;
        }
        if (!('speechSynthesis' in window) || !this.pages.length) {
            alert('이 브라우저에서는 음성 낭독 기능을 지원하지 않습니다.');
            return;
        }

        window.speechSynthesis.cancel();
        this.audioPageIndex = Math.max(0, Math.min(pageIndex, this.pages.length - 1));
        const page = this.pages[this.audioPageIndex];

        if (this.audioTrackTitle) {
            this.audioTrackTitle.textContent = `${this.audioPageIndex + 1}. ${page.title}`;
        }
        this.audiobookPlayer?.classList.remove('hidden');

        const textToSpeak = this.prepareTextForTTS(page);
        const utterance = new SpeechSynthesisUtterance(textToSpeak);
        utterance.lang = 'ko-KR';
        utterance.rate = this.audioSpeed;

        utterance.onstart = () => {
            this.isAudioPlaying = true;
            this.updateAudioUI();
        };

        utterance.onend = () => {
            if (this.audioPageIndex + 1 < this.pages.length) {
                this.startAudiobook(this.audioPageIndex + 1);
            } else {
                this.stopAudiobook();
            }
        };

        utterance.onerror = () => {
            this.stopAudiobook();
        };

        this.currentUtterance = utterance;
        window.speechSynthesis.speak(utterance);
    }

    toggleAudioPlayPause() {
        if (!('speechSynthesis' in window)) return;

        if (window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
            this.isAudioPlaying = true;
        } else if (window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
            this.isAudioPlaying = false;
        } else {
            this.startAudiobook(this.currentPageIndex);
            return;
        }
        this.updateAudioUI();
    }

    cycleAudioSpeed() {
        const speeds = [1.0, 1.2, 1.5];
        const nextIdx = (speeds.indexOf(this.audioSpeed) + 1) % speeds.length;
        this.audioSpeed = speeds[nextIdx];
        if (this.audioSpeedBtn) {
            this.audioSpeedBtn.textContent = `${this.audioSpeed.toFixed(1)}x`;
        }
        if (this.isAudioPlaying) {
            this.startAudiobook(this.audioPageIndex);
        }
    }

    stopAudiobook() {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        this.isAudioPlaying = false;
        this.audiobookPlayer?.classList.add('hidden');
        this.updateAudioUI();
    }

    updateAudioUI() {
        if (this.audioPlayIcon) {
            this.audioPlayIcon.textContent = this.isAudioPlaying ? '❚❚' : '▶';
        }
        if (this.audioWaveAnim) {
            this.audioWaveAnim.classList.toggle('is-playing', this.isAudioPlaying);
        }
    }

    prepareTextForTTS(page) {
        if (!page) return '';
        const titleIntro = `제 ${page.chapter}장, ${page.chapterTitle}. ${page.title}. `;
        const cleanBody = String(page.markdown || '')
            .replace(/^##\s+.+$/gm, '')
            .replace(/^###\s+(.+)$/gm, '$1.')
            .replace(/^>\s*\*\*[^:]+\*\*:\s*/gm, '')
            .replace(/^>\s*/gm, '')
            .replace(/^-\s+/gm, '')
            .replace(/^\d+\.\s+/gm, '')
            .replace(/[*`#_]/g, '')
            .replace(/\[\s*木\s*火\s*土\s*金\s*水\s*\]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        return `${titleIntro} ${cleanBody}`;
    }

    /* ==========================================================================
       Card News View (Short-form Slide) Implementation
       ========================================================================== */
    buildAnonymousShareText() {
        return buildAnonymousProfile(this.analysisData).shareText;
    }

    anonymizeReportHtml(_html) {
        return buildAnonymousReportHtml(this.analysisData);
    }

    async deleteCurrentReport() {
        if (!this.currentTaskId || !window.confirm('이 리포트와 저장된 입력 정보를 삭제하시겠습니까?')) return;
        this.cleanupPolling();
        try {
            await deleteAnalysis(this.currentTaskId);
        } catch {
            window.alert('서버에 연결하지 못해 서버 사본은 삭제하지 못했습니다. 서버 사본은 생성 후 24시간에 만료됩니다. 이 기기의 사본은 삭제합니다.');
        }
        removeCachedAnalysis(this.currentTaskId);
        removeHistoryEntryById(this.currentTaskId);
        clearLastInput();
        window.location.replace('index.html');
    }

    saveShareCard(triggerButton = this.saveImageBtn, { anonymous = false } = {}) {
        if (!this.analysisData) {
            this.flashButtonText(triggerButton, '결과 없음', '프로필 카드 저장');
            return;
        }

        const canvas = document.createElement('canvas');
        canvas.width = 1080;
        canvas.height = 1350;

        const context = canvas.getContext('2d');
        if (!context) {
            this.flashButtonText(triggerButton, '저장 실패', '프로필 카드 저장');
            return;
        }

        this.drawShareCard(context, canvas.width, canvas.height, { anonymous });

        const link = document.createElement('a');
        link.download = `${anonymous ? '나의결-익명-프로필' : '나의결-프로필'}-${Date.now()}.png`;
        link.href = canvas.toDataURL('image/png');
        document.body.appendChild(link);
        link.click();
        link.remove();

        const defaultLabel = triggerButton === this.saveProfileImageButton
            ? '프로필 카드 저장'
            : (anonymous ? '익명 카드 저장' : '카드 저장');
        this.flashButtonText(triggerButton, '저장되었습니다', defaultLabel);
    }

    drawShareCard(context, width, height, { anonymous = false } = {}) {
        context.fillStyle = '#FBF9F3';
        context.fillRect(0, 0, width, height);

        context.fillStyle = '#173F35';
        context.fillRect(0, 0, 300, height);

        context.save();
        context.globalAlpha = 0.28;
        context.strokeStyle = '#AA9257';
        context.lineWidth = 2;
        context.beginPath();
        context.arc(150, 430, 210, 0, Math.PI * 2);
        context.stroke();
        context.beginPath();
        context.moveTo(-20, 240);
        context.lineTo(300, 650);
        context.moveTo(60, 760);
        context.lineTo(330, 370);
        context.stroke();
        context.restore();

        context.fillStyle = '#B64634';
        context.fillRect(64, 64, 74, 74);
        context.strokeStyle = '#FBF9F3';
        context.lineWidth = 2;
        context.strokeRect(70, 70, 62, 62);
        context.fillStyle = '#FFFFFF';
        context.font = '500 40px "Noto Serif KR", serif';
        context.fillText('결', 81, 116);

        context.fillStyle = '#F6F0E3';
        context.font = '500 38px "Noto Serif KR", serif';
        context.fillText('나의 결', 64, 196);

        context.fillStyle = '#C8B36D';
        context.font = '600 25px Pretendard, "Noto Sans KR", sans-serif';
        context.fillText('나의 결', 64, 1120);
        context.fillStyle = '#D7DED9';
        context.font = '400 24px Pretendard, "Noto Sans KR", sans-serif';
        this.wrapCanvasText(context, '당신의 시간을 한 권의 언어로 기록합니다.', 64, 1178, 185, 36, 4);

        context.fillStyle = '#B64634';
        context.font = '700 24px Pretendard, "Noto Sans KR", sans-serif';
        context.fillText('나의 결 · PERSONAL PROFILE', 380, 94);

        context.fillStyle = '#1F2724';
        context.font = '600 62px "Noto Serif KR", serif';
        const title = anonymous
            ? '나의 결 프로필'
            : (this.socialHeadline?.textContent || this.heroUserGreeting?.textContent || '나의 결');
        let y = this.wrapCanvasText(context, title, 380, 184, 620, 82, 2);

        context.fillStyle = '#68716C';
        context.font = '400 24px Pretendard, "Noto Sans KR", sans-serif';
        context.fillText(
            anonymous ? '이름·생년월일을 제외한 익명 공유본' : (this.heroDate?.textContent || '나만의 사주 리포트'),
            380,
            y + 20,
        );

        const safe = buildAnonymousProfile(this.analysisData);
        const practical = anonymous ? {
            type: { label: safe.label }, chart: safe.chart,
            actions: [{ title: '나에게 맞는 생활 리듬 살피기' }],
        } : this.practicalSummaryData;
        const strongestRhythm = practical?.chart?.length
            ? practical.chart.reduce((best, item) => item.value > best.value ? item : best)
            : null;
        const cards = [
            ['MY TYPE', practical?.type?.label || this.cardIdentity?.textContent || '나만의 유형'],
            ['STRONG RHYTHM', strongestRhythm?.label || '나만의 리듬'],
            ['TAKE ACTION', practical?.actions?.[0]?.title || '가장 작은 첫 행동'],
        ];

        y += 86;
        cards.forEach(([label, value]) => {
            this.drawRoundedRect(context, 380, y, 620, 190, 6, '#FFFDF8', '#D8D2C6');
            context.fillStyle = '#B64634';
            context.font = '700 23px Pretendard, "Noto Sans KR", sans-serif';
            context.fillText(label, 420, y + 52);
            context.fillStyle = '#1F2724';
            context.font = '600 38px "Noto Serif KR", serif';
            this.wrapCanvasText(context, value, 420, y + 118, 535, 50, 2);
            y += 218;
        });

        context.fillStyle = '#F1EDE3';
        context.fillRect(380, height - 160, 620, 82);
        context.fillStyle = '#B64634';
        context.font = '700 21px Pretendard, "Noto Sans KR", sans-serif';
        context.fillText(anonymous ? '익명 요약' : '가까운 특별한 날', 410, height - 110);
        context.fillStyle = '#1F2724';
        context.font = '600 23px "Noto Serif KR", serif';
        this.wrapCanvasText(context, anonymous ? '개인별 날짜는 공유하지 않습니다' : (this.cardSpecialDate?.textContent || '리포트에서 확인하세요'), 640, height - 110, 325, 34, 1);
    }

    drawRoundedRect(context, x, y, width, height, radius, fillStyle, strokeStyle) {
        context.beginPath();
        context.moveTo(x + radius, y);
        context.lineTo(x + width - radius, y);
        context.quadraticCurveTo(x + width, y, x + width, y + radius);
        context.lineTo(x + width, y + height - radius);
        context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        context.lineTo(x + radius, y + height);
        context.quadraticCurveTo(x, y + height, x, y + height - radius);
        context.lineTo(x, y + radius);
        context.quadraticCurveTo(x, y, x + radius, y);
        context.closePath();

        context.fillStyle = fillStyle;
        context.fill();
        context.strokeStyle = strokeStyle;
        context.lineWidth = 2;
        context.stroke();
    }

    wrapCanvasText(context, text, x, y, maxWidth, lineHeight, maxLines = 3) {
        const chars = [...String(text || '').trim()];
        let line = '';
        let linesDrawn = 0;

        for (let index = 0; index < chars.length; index += 1) {
            const testLine = `${line}${chars[index]}`;
            const metrics = context.measureText(testLine);

            if (metrics.width > maxWidth && line) {
                if (linesDrawn === maxLines - 1) {
                    context.fillText(this.truncateCanvasLine(context, line, maxWidth), x, y);
                    return y + lineHeight;
                }

                context.fillText(line, x, y);
                line = chars[index];
                y += lineHeight;
                linesDrawn += 1;
            } else {
                line = testLine;
            }
        }

        if (line) {
            context.fillText(line, x, y);
            y += lineHeight;
        }

        return y;
    }

    truncateCanvasLine(context, line, maxWidth) {
        let output = `${line.trim()}...`;
        while (output.length > 3 && context.measureText(output).width > maxWidth) {
            output = `${output.slice(0, -4).trim()}...`;
        }
        return output;
    }

    downloadCurrentReport({ anonymous = false } = {}) {
        if (!this.premiumUnlocked) {
            this.requestPremiumAccess(2);
            return;
        }
        this.downloadBookReport({ anonymous });
    }

    downloadBookReport({ anonymous = false } = {}) {
        if (!this.premiumUnlocked) {
            this.requestPremiumAccess(2);
            return;
        }
        if (!this.analysisData || !this.pages.length) return;

        if (anonymous) {
            const blob = new Blob([buildAnonymousReportHtml(this.analysisData)], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `나의결-익명-요약-${Date.now()}.html`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
            return;
        }
        const practical = this.practicalSummaryData;
        const practicalHtml = practical ? `
    <article class="book-page practical-summary-page">
      <header class="page-header">
        <span class="chapter-label">CHAPTER 5 · FINAL SUMMARY</span>
        <h2 class="section-title">지금 나를 읽는 핵심 요약</h2>
      </header>
      <div class="page-ornament" aria-hidden="true"><span>木</span><span>火</span><span>土</span><span>金</span><span>水</span></div>
      <div class="page-body">
        <div class="type-summary-box">
          <span class="type-badge">${this.escapeHtml(practical.type.label)}</span>
          <p class="type-tagline">${this.escapeHtml(practical.type.tagline)}</p>
          <div class="type-traits">${practical.type.traits.map((trait) => `<span>#${this.escapeHtml(String(trait).replace(/^#/, ''))}</span>`).join(' ')}</div>
        </div>

        <div class="summary-section-block">
          <h3>오행의 보이는 분포와 월령</h3>
          <div class="profile-chart">
            ${practical.chart.map((metric) => `
              <div class="chart-row">
                <span class="chart-label">${this.escapeHtml(metric.label)}</span>
                <span class="chart-track"><span style="width: ${metric.bar_percent}%;"></span></span>
                <span class="chart-value">${this.escapeHtml(metric.value)}${this.escapeHtml(metric.unit)}${metric.is_month_command ? ' · 월령' : ''}</span>
              </div>
            `).join('')}
          </div>
          ${practical.chart_note ? `<p class="chart-note">${this.escapeHtml(practical.chart_note)}</p>` : ''}
        </div>

        <div class="summary-section-block">
          <h3>지금부터 꺼내 쓰는 행동 카드</h3>
          <div class="action-cards-grid">
            ${practical.actions.map((action) => `
              <div class="action-card">
                <div class="action-card-header">
                  <span class="action-period">${this.escapeHtml(action.period)}</span>
                  <small class="action-timing">${this.escapeHtml(action.timing)}</small>
                </div>
                <h4>${this.escapeHtml(action.title)}</h4>
                <p>${this.escapeHtml(action.action)}</p>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="summary-section-block">
          <h3>SNS 프로필 요약</h3>
          <div class="social-profile-box">
            <blockquote>${this.escapeHtml(practical.social_profile.summary)}</blockquote>
            <p class="hashtags">${this.escapeHtml(practical.social_profile.hashtags.join(' '))}</p>
          </div>
        </div>
      </div>
    </article>` : '';

        const html = `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.escapeHtml(anonymous ? '나의 결 · 익명 리포트' : (this.heroUserGreeting?.textContent || '나의 결 리포트'))}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@1.3.9/dist/web/variable/pretendardvariable.css">
  <style>
    :root {
      --paper: #f8f5ed;
      --paper-card: #ffffff;
      --paper-deep: #eee9dc;
      --ink: #19231f;
      --green: #123b31;
      --green-soft: #1c4c40;
      --red: #bb4b36;
      --gold: #aa8b46;
      --muted: #59645f;
      --soft: #7a847f;
      --border: #d5d0c4;
      --font-serif: "Noto Serif KR", Batang, Georgia, serif;
      --font-body: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, "Noto Sans KR", sans-serif;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background: var(--paper);
      color: var(--ink);
      font-family: var(--font-body);
      font-size: 1rem;
      line-height: 1.85;
      word-break: keep-all;
      padding: clamp(2rem, 5vw, 4.5rem) 1rem;
    }

    .report-container {
      width: min(880px, 100%);
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 3rem;
    }

    .report-cover-header {
      text-align: center;
      padding: 3rem 2rem;
      border: 1px solid #365f54;
      border-radius: 8px;
      background: var(--green);
      color: #fff;
      position: relative;
      overflow: hidden;
      box-shadow: 0 1rem 3.5rem rgba(18, 59, 49, 0.15);
    }

    .brand-emblem {
      display: inline-grid;
      width: 48px;
      height: 48px;
      place-items: center;
      margin-bottom: 1.2rem;
      border: 1px solid var(--gold);
      color: var(--gold);
      font-family: var(--font-serif);
      font-size: 1.3rem;
      border-radius: 50%;
    }

    .report-cover-header h1 {
      font-family: var(--font-serif);
      font-size: clamp(2rem, 3.8vw, 2.75rem);
      font-weight: 500;
      color: #fffaf0;
      letter-spacing: -0.04em;
      margin-bottom: 0.6rem;
    }

    .report-cover-header p {
      color: #d2ddd8;
      font-size: 0.95rem;
    }

    .book-page {
      position: relative;
      padding: clamp(2.25rem, 6vw, 4.5rem) clamp(1.5rem, 7vw, 5rem);
      border: 1px solid var(--border);
      background: var(--paper-card);
      border-radius: 8px;
      box-shadow: 0 0.75rem 2.5rem rgba(18, 59, 49, 0.07);
    }

    .book-page::before {
      content: '';
      position: absolute;
      top: 14px;
      right: 14px;
      bottom: 14px;
      left: 14px;
      border: 1px solid rgba(170, 139, 70, 0.24);
      border-radius: 4px;
      pointer-events: none;
    }

    .page-header {
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
    }

    .chapter-label {
      display: block;
      color: var(--red);
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 0.4rem;
    }

    .section-title {
      font-family: var(--font-serif);
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      font-weight: 600;
      line-height: 1.35;
    }

    .page-ornament {
      display: flex;
      justify-content: center;
      gap: 1.5rem;
      margin: 1.5rem 0 2.5rem;
      color: var(--muted);
      font-family: var(--font-serif);
      font-size: 0.85rem;
      letter-spacing: 0.3em;
    }

    .page-body h2 {
      font-family: var(--font-serif);
      font-size: 1.4rem;
      margin: 2.5rem 0 1rem;
      color: var(--green);
    }

    .page-body h3 {
      font-size: 1.15rem;
      margin: 2rem 0 0.8rem;
      padding-left: 0.8rem;
      border-left: 3px solid var(--red);
      color: var(--ink);
    }

    .page-body p {
      margin-bottom: 1.25rem;
      color: #2b3632;
    }

    .page-body ul, .page-body ol {
      margin: 1.2rem 0 1.5rem;
      padding: 1.2rem 1.4rem 1.2rem 2.8rem;
      background: var(--paper-deep);
      border-radius: 6px;
      border: 1px solid var(--border);
    }

    .page-body ol {
      list-style-type: decimal;
    }

    .page-body ol li::marker {
      color: var(--red);
      font-weight: 700;
    }

    .page-body ul {
      list-style-type: disc;
    }

    .page-body ul li::marker {
      color: var(--gold);
    }

    .page-body li {
      margin-bottom: 0.5rem;
      line-height: 1.8;
    }

    .page-body blockquote {
      margin: 1.5rem 0;
      padding: 1.2rem 1.5rem;
      background: var(--paper-deep);
      border-left: 4px solid var(--gold);
      font-style: italic;
      color: #33403a;
    }

    .page-body strong {
      color: var(--red);
      font-weight: 600;
    }

    .type-summary-box {
      text-align: center;
      padding: 2.5rem 1.5rem;
      background: var(--paper-deep);
      border-radius: 8px;
      margin-bottom: 2.5rem;
    }

    .type-badge {
      display: inline-block;
      padding: 0.4rem 1.2rem;
      background: var(--gold);
      color: #fff;
      font-size: 0.85rem;
      font-weight: 700;
      border-radius: 999px;
      margin-bottom: 0.8rem;
    }

    .type-tagline {
      font-family: var(--font-serif);
      font-size: 1.35rem;
      font-weight: 600;
      color: var(--green);
      margin-bottom: 1rem;
    }

    .type-traits {
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .type-traits span {
      background: #fff;
      padding: 0.3rem 0.8rem;
      border-radius: 4px;
      font-size: 0.85rem;
      color: var(--muted);
      border: 1px solid var(--border);
    }

    .summary-section-block {
      margin-top: 2.5rem;
    }

    .summary-section-block h3 {
      font-size: 1.2rem;
      border-left: 3px solid var(--gold);
      padding-left: 0.8rem;
      margin-bottom: 1.2rem;
    }

    .profile-chart {
      display: flex;
      flex-direction: column;
      gap: 0.8rem;
      background: #fff;
      padding: 1.5rem;
      border: 1px solid var(--border);
      border-radius: 8px;
    }

    .chart-row {
      display: grid;
      grid-template-columns: 4.5rem 1fr 4.5rem;
      align-items: center;
      gap: 1rem;
      font-size: 0.9rem;
    }

    .chart-track {
      height: 10px;
      background: var(--paper-deep);
      border-radius: 999px;
      overflow: hidden;
    }

    .chart-track > span {
      display: block;
      height: 100%;
      background: var(--green);
      border-radius: 999px;
    }

    .chart-note {
      font-size: 0.82rem;
      color: var(--soft);
      margin-top: 0.5rem;
      font-family: var(--font-body);
    }

    .action-cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }

    .action-card {
      padding: 1.25rem;
      background: var(--paper-deep);
      border: 1px solid var(--border);
      border-radius: 4px;
      font-family: var(--font-body);
    }

    .action-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.6rem;
    }

    .action-period {
      font-weight: 700;
      font-size: 0.78rem;
      color: var(--red);
    }

    .action-timing {
      font-size: 0.72rem;
      color: var(--soft);
    }

    .action-card h4 {
      font-size: 1.05rem;
      color: var(--ink);
      margin-bottom: 0.5rem;
      font-family: var(--font-serif);
    }

    .action-card p {
      margin: 0;
      font-size: 0.88rem;
      line-height: 1.65;
      color: var(--muted);
    }

    .social-profile-box {
      margin-top: 1rem;
    }

    .hashtags {
      margin-top: 0.75rem;
      font-weight: 600;
      color: var(--red);
      font-size: 0.9rem;
      font-family: var(--font-body);
    }

    .report-footer {
      text-align: center;
      padding: 2rem 0;
      color: var(--soft);
      font-size: 0.82rem;
      font-family: var(--font-body);
    }

    @page {
      margin: 15mm;
      size: A4 portrait;
    }

    @media print {
      body {
        padding: 0;
        background: #fff;
      }
      .report-container {
        width: 100%;
        gap: 0;
      }
      .report-cover-header {
        box-shadow: none;
        break-after: page;
        page-break-after: always;
        border-radius: 0;
      }
      .book-page {
        box-shadow: none;
        break-after: page;
        page-break-after: always;
        border-radius: 0;
        border-color: #d8d2c6;
        padding: 2.5rem 2rem;
        margin-bottom: 0;
      }
      .book-page:last-child {
        break-after: auto;
        page-break-after: auto;
      }
      .report-footer {
        display: none;
      }
      details > * {
        display: block !important;
      }
      details summary {
        display: none !important;
      }
    }
  </style>
</head>
<body>
  <div class="report-container">
    <header class="report-cover-header">
      <span class="brand-emblem">결</span>
      <h1>${this.escapeHtml(anonymous ? '나의 결 · 익명 공유본' : (this.heroUserGreeting?.textContent || '나의 결'))}</h1>
      <p>${this.escapeHtml(anonymous ? '개인 식별 정보를 제외한 분석 리포트입니다.' : (this.heroDate?.textContent || ''))}</p>
    </header>
    ${this.pages.map((page) => `
      <article class="book-page">
        <header class="page-header">
          <span class="chapter-label">Chapter ${page.chapter}</span>
          <h2 class="section-title">${this.escapeHtml(page.title)}</h2>
        </header>
        <div class="page-ornament" aria-hidden="true"><span>木</span><span>火</span><span>土</span><span>金</span><span>水</span></div>
        <div class="page-body">
          ${this.renderMarkdownToHtml(this.stripDuplicatePageHeading(page.markdown, page.title))}
        </div>
      </article>
    `).join('')}
    ${practicalHtml}
    <footer class="report-footer">
      <p>&copy; 나의 결 · 나를 읽는 한 권의 이야기</p>
    </footer>
  </div>
</body>
</html>`;

        const outputHtml = anonymous ? this.anonymizeReportHtml(html) : html;
        const blob = new Blob([outputHtml], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${anonymous ? '나의결-익명-리포트' : '나의결-리포트'}-${Date.now()}.html`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    showError(message) {
        this.cleanupPolling();
        this.loadingContainer?.classList.add('hidden');
        this.analysisContainer?.classList.add('hidden');
        this.errorContainer?.classList.remove('hidden');

        const errorMessage = document.getElementById('errorMessage');
        if (errorMessage) {
            errorMessage.textContent = message;
        }
    }
}

export { PersonalOSResultHandler };

if (typeof document !== 'undefined') {
    new PersonalOSResultHandler();
}
