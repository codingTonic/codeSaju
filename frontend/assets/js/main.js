import { ApiError, checkHealth, createSajuBook, deleteAnalysis, deleteStoredTasks } from './api.js';
import {
    clearLastInput,
    clearCachedAnalyses,
    clearHistory,
    getAnalysisHistory,
    getCachedAnalysis,
    getHistoryDateLabel,
    getLastInput,
    isHistoryEnabled,
    removeCachedAnalysis,
    removeHistoryEntryById,
    saveCachedAnalysis,
    saveLastInput,
    setHistoryEnabled,
} from './storage.js';

const HISTORY_UPDATED_EVENT = 'history:updated';

class ThemeManager {
    constructor() {
        this.themeToggle = document.getElementById('themeToggle');
        this.themeIcon = document.getElementById('themeIcon');
        this.currentTheme = this.getStoredTheme() || this.getPreferredTheme();
        this.liveRegionTimeout = null;

        this.init();
    }

    init() {
        this.ensureLiveRegion();
        this.applyTheme(this.currentTheme);

        this.themeToggle?.addEventListener('click', () => this.toggleTheme());

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
            if (!this.getStoredTheme()) {
                this.applyTheme(event.matches ? 'dark' : 'light');
            }
        });

    }

    getPreferredTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    getStoredTheme() {
        try {
            return localStorage.getItem('saju-theme');
        } catch {
            return null;
        }
    }

    storeTheme(theme) {
        try {
            localStorage.setItem('saju-theme', theme);
        } catch {
            console.warn('테마 설정을 저장할 수 없습니다.');
        }
    }

    applyTheme(theme) {
        if (!this.themeToggle || !this.themeIcon) return;

        const root = document.documentElement;
        if (theme === 'dark') {
            root.setAttribute('data-theme', 'dark');
            this.themeIcon.textContent = '☀️';
            this.themeToggle.setAttribute('aria-label', '라이트 모드로 전환');
        } else {
            root.setAttribute('data-theme', 'light');
            this.themeIcon.textContent = '🌙';
            this.themeToggle.setAttribute('aria-label', '다크 모드로 전환');
        }

        this.currentTheme = theme;
        this.storeTheme(theme);
        this.showThemeChangeToast(theme);
    }

    toggleTheme() {
        const nextTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.applyTheme(nextTheme);
    }

    showThemeChangeToast(theme) {
        const region = this.ensureLiveRegion();
        if (!region) return;

        region.textContent = theme === 'dark'
            ? '다크 모드가 활성화되었습니다.'
            : '라이트 모드가 활성화되었습니다.';

        if (this.liveRegionTimeout) {
            clearTimeout(this.liveRegionTimeout);
        }

        this.liveRegionTimeout = window.setTimeout(() => {
            region.textContent = '';
        }, 1200);
    }

    ensureLiveRegion() {
        let region = document.getElementById('theme-live-region');
        if (!region) {
            region = document.createElement('div');
            region.id = 'theme-live-region';
            region.className = 'sr-only';
            region.setAttribute('aria-live', 'polite');
            region.setAttribute('aria-atomic', 'true');
            document.body.appendChild(region);
        }
        return region;
    }
}

class HistoryPreviewManager {
    constructor() {
        this.section = document.getElementById('historySection');
        this.listEl = document.getElementById('historyPreviewList');
        this.emptyEl = document.getElementById('historyPreviewEmpty');
        this.clearBtn = document.getElementById('historyClearBtn');

        if (!this.section || !this.listEl || !this.emptyEl) return;
        this.init();
    }

    init() {
        this.render();
        this.clearBtn?.addEventListener('click', () => this.clearAll());
        this.listEl.addEventListener('click', (event) => this.handleListClick(event));
        window.addEventListener('storage', () => this.render());
        window.addEventListener('pageshow', () => this.render());
        window.addEventListener(HISTORY_UPDATED_EVENT, () => this.render());
    }

    render() {
        this.listEl.replaceChildren();

        if (!isHistoryEnabled()) {
            this.clearBtn?.setAttribute('disabled', '');
            if (this.clearBtn) this.clearBtn.hidden = true;
            this.setEmptyMessage('아직 저장한 리포트가 없어요. 입력할 때 기록 저장을 선택하면 이곳에서 다시 읽을 수 있습니다.');
            return;
        }

        const history = getAnalysisHistory();
        this.clearBtn?.toggleAttribute('disabled', history.length === 0);
        if (this.clearBtn) this.clearBtn.hidden = history.length === 0;

        if (!history.length) {
            this.setEmptyMessage('아직 분석된 기록이 없습니다. 당신의 첫 번째 이야기를 시작해보세요.');
            return;
        }

        this.emptyEl.style.display = 'none';
        history.forEach((item) => {
            this.listEl.appendChild(this.createHistoryCard(item));
        });
    }

    setEmptyMessage(message) {
        this.emptyEl.replaceChildren();
        const paragraph = document.createElement('p');
        paragraph.textContent = message;
        this.emptyEl.appendChild(paragraph);
        this.emptyEl.style.display = 'block';
    }

    createHistoryCard(item) {
        const article = document.createElement('article');
        article.className = 'history-card';
        article.dataset.id = item.id;

        const header = document.createElement('div');
        const title = document.createElement('h3');
        title.textContent = `${item.display_name || '익명'}님`;
        const meta = document.createElement('div');
        meta.className = 'history-meta';
        meta.textContent = getHistoryDateLabel(item);
        header.append(title, meta);

        const summary = document.createElement('div');
        summary.className = 'history-summary';
        summary.textContent = item.summary || '요약 정보 없음';

        const actions = document.createElement('div');
        actions.className = 'history-actions';

        const openBtn = document.createElement('button');
        openBtn.type = 'button';
        openBtn.className = 'button primary history-open-btn';
        openBtn.dataset.id = item.id;

        const hasCachedResult = Boolean(getCachedAnalysis(item.task_id));
        openBtn.textContent = hasCachedResult ? '바로 보기' : '결과 없음';
        openBtn.disabled = !hasCachedResult;

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'button ghost history-delete-btn';
        deleteBtn.dataset.id = item.id;
        deleteBtn.textContent = '삭제';

        actions.append(openBtn, deleteBtn);
        article.append(header, summary, actions);
        return article;
    }

    async handleListClick(event) {
        const button = event.target.closest('button');
        if (!button) return;

        const entryId = button.dataset.id;
        const history = getAnalysisHistory();
        const item = history.find((entry) => `${entry.id}` === `${entryId}`);
        if (!item) return;

        if (button.classList.contains('history-open-btn')) {
            if (getCachedAnalysis(item.task_id)) {
                window.location.href = `result.html?task_id=${encodeURIComponent(item.task_id)}`;
            }
            return;
        }

        if (!button.classList.contains('history-delete-btn')) return;

        if (!window.confirm('이 결과를 삭제하시겠습니까?')) return;

        try {
            await deleteAnalysis(item.task_id);
        } catch {
            window.alert('서버에 연결하지 못했습니다. 서버 사본은 생성 후 24시간에 만료되며, 이 기기의 기록은 삭제합니다.');
        }
        clearLastInput();
        removeCachedAnalysis(item.task_id);
        removeHistoryEntryById(entryId);
        window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT));
    }

    async clearAll() {
        if (!window.confirm('이 기기에 저장한 모든 분석 기록을 삭제하시겠습니까?')) return;
        if (!await deleteStoredTasks()) {
            window.alert('일부 서버 사본을 삭제하지 못했습니다. 해당 사본은 생성 후 24시간에 만료되며, 이 기기의 정보는 모두 삭제합니다.');
        }
        clearHistory();
        clearCachedAnalyses();
        window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT));
    }
}

class PersonalOSStepperHandler {
    constructor() {
        this.form = document.getElementById('sajuForm');
        this.formShell = this.form?.closest('.form-shell') || null;
        this.apiStatusNotice = document.getElementById('apiStatusNotice');
        this.loadingContainer = document.getElementById('loadingContainer');
        this.loadingStatusText = document.getElementById('loadingStatusText');
        this.errorContainer = document.getElementById('errorContainer');
        this.retryButton = document.getElementById('retryButton');
        this.historyConsentInput = document.getElementById('historyConsent');

        this.currentStep = 1;
        this.totalSteps = 6;
        this.progressBar = document.getElementById('stepperProgressBar');

        this.birthTimeInput = document.getElementById('birth_time');
        this.birthTimeUnknown = document.getElementById('birth_time_unknown');
        this.birthDateInput = document.getElementById('birth_date');
        this.calendarTypeInput = document.getElementById('calendar_type');
        this.leapMonthRow = document.getElementById('leapMonthRow');
        this.leapMonthInput = document.getElementById('is_leap_month');
        this.partnerBirthTimeInput = document.getElementById('partner_birth_time');
        this.partnerBirthTimeUnknown = document.getElementById('partner_birth_time_unknown');
        this.partnerBirthDateInput = document.getElementById('partner_birth_date');
        this.partnerCalendarTypeInput = document.getElementById('partner_calendar_type');
        this.partnerLeapMonthRow = document.getElementById('partnerLeapMonthRow');
        this.partnerLeapMonthInput = document.getElementById('partner_is_leap_month');

        this.isSubmitting = false;
        this.apiAvailable = true;

        this.init();
    }

    init() {
        if (!this.form) return;

        this.setupEventListeners();
        this.setDateInputLimits();
        this.checkApiStatus();
        this.restoreLastInput();
        this.syncCalendarState(this.calendarTypeInput, this.leapMonthRow, this.leapMonthInput);
        this.syncCalendarState(
            this.partnerCalendarTypeInput,
            this.partnerLeapMonthRow,
            this.partnerLeapMonthInput,
        );
        this.updateStepUI(false);
    }

    setupEventListeners() {
        this.form.querySelectorAll('.next-btn').forEach((button) => {
            button.addEventListener('click', () => {
                const nextStep = Number.parseInt(button.dataset.next || '', 10);
                this.goToStep(nextStep);
            });
        });

        this.form.querySelectorAll('.btn-prev').forEach((button) => {
            button.addEventListener('click', () => {
                const prevStep = this.resolvePreviousStep(button.dataset.prev || '');
                this.goToStep(prevStep);
            });
        });

        this.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.handleSubmit();
        });

        this.birthTimeUnknown?.addEventListener('change', () => {
            this.syncBirthTimeState(this.birthTimeInput, this.birthTimeUnknown);
        });

        this.partnerBirthTimeUnknown?.addEventListener('change', () => {
            this.syncBirthTimeState(this.partnerBirthTimeInput, this.partnerBirthTimeUnknown);
        });

        this.calendarTypeInput?.addEventListener('change', () => {
            this.syncCalendarState(this.calendarTypeInput, this.leapMonthRow, this.leapMonthInput);
        });

        this.partnerCalendarTypeInput?.addEventListener('change', () => {
            this.syncCalendarState(
                this.partnerCalendarTypeInput,
                this.partnerLeapMonthRow,
                this.partnerLeapMonthInput,
            );
        });

        this.historyConsentInput?.addEventListener('change', () => {
            setHistoryEnabled(this.historyConsentInput.checked);
            window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT));
        });

        this.retryButton?.addEventListener('click', () => {
            if (this.isSubmitting) return;
            this.handleSubmit();
        });

        this.form.querySelectorAll('input, select').forEach((input) => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearFieldError(input));
        });
    }

    setDateInputLimits() {
        const now = new Date();
        const today = [
            now.getFullYear(),
            String(now.getMonth() + 1).padStart(2, '0'),
            String(now.getDate()).padStart(2, '0'),
        ].join('-');

        this.birthDateInput?.setAttribute('max', today);
        this.partnerBirthDateInput?.setAttribute('max', today);
    }

    resolvePreviousStep(rawValue) {
        if (rawValue === 'partner_logic') {
            return this.isPartnerFlowEnabled() ? 5 : 4;
        }

        const parsed = Number.parseInt(rawValue, 10);
        return Number.isNaN(parsed) ? this.currentStep : parsed;
    }

    syncBirthTimeState(inputEl, checkboxEl) {
        if (!inputEl || !checkboxEl) return;

        if (checkboxEl.checked) {
            inputEl.value = '12:00';
            inputEl.readOnly = true;
            inputEl.removeAttribute('required');
        } else {
            inputEl.readOnly = false;
            inputEl.setAttribute('required', '');
            if (inputEl.value === '12:00') {
                inputEl.value = '';
            }
        }
    }

    syncCalendarState(selectEl, rowEl, checkboxEl) {
        const isLunar = selectEl?.value === 'lunar';
        rowEl?.classList.toggle('hidden', !isLunar);
        if (!isLunar && checkboxEl) checkboxEl.checked = false;
    }

    getRelationshipStatus() {
        return this.form.querySelector('input[name="relationship_status"]:checked')?.value || null;
    }

    isPartnerFlowEnabled() {
        const relationshipStatus = this.getRelationshipStatus();
        return relationshipStatus === 'dating' || relationshipStatus === 'married';
    }

    getStepElement(step) {
        return this.form.querySelector(`.step-section[data-step="${step}"]`);
    }

    goToStep(targetStep) {
        if (!Number.isInteger(targetStep)) return;
        if (targetStep < 1 || targetStep > this.totalSteps) return;

        if (targetStep > this.currentStep && !this.validateCurrentStep()) {
            return;
        }

        if (targetStep === 5 && !this.isPartnerFlowEnabled()) {
            targetStep = 6;
        }

        if (targetStep === 5 && this.currentStep === 6 && !this.isPartnerFlowEnabled()) {
            targetStep = 4;
        }

        this.currentStep = targetStep;
        this.updateStepUI();
    }

    updateStepUI(focusField = true) {
        this.form.querySelectorAll('.step-section').forEach((section) => section.classList.remove('active'));

        const currentEl = this.getStepElement(this.currentStep);
        if (currentEl) {
            currentEl.classList.add('active');
            if (focusField) {
                const firstInput = currentEl.querySelector('input:not([type="hidden"]), select');
                firstInput?.focus();
            }
        }

        const progress = ((this.currentStep - 1) / (this.totalSteps - 1)) * 100;
        if (this.progressBar) {
            this.progressBar.style.width = `${progress}%`;
        }

        const partnerMbtiGroup = document.getElementById('partnerMbtiGroup');
        if (partnerMbtiGroup) {
            if (this.isPartnerFlowEnabled()) {
                partnerMbtiGroup.style.display = 'block';
            } else {
                partnerMbtiGroup.style.display = 'none';
                const partnerMbtiInput = document.getElementById('partner_mbti');
                if (partnerMbtiInput) {
                    partnerMbtiInput.value = '';
                }
            }
        }
    }

    validateCurrentStep() {
        return this.validateStep(this.currentStep, false);
    }

    validateStep(step, includeHiddenFields = false) {
        const stepElement = this.getStepElement(step);
        if (!stepElement) return true;

        let isValid = true;

        stepElement.querySelectorAll('input, select').forEach((input) => {
            if (!this.validateField(input, includeHiddenFields)) {
                isValid = false;
            }
        });

        const radioGroups = new Set();
        stepElement.querySelectorAll('input[type="radio"][required]').forEach((radio) => {
            radioGroups.add(radio.name);
        });

        radioGroups.forEach((name) => {
            const checked = stepElement.querySelector(`input[name="${name}"]:checked`);
            if (checked) return;

            isValid = false;
            const groupContainer = stepElement.querySelector(`input[name="${name}"]`)?.closest('.option-card-group');
            if (groupContainer && !groupContainer.classList.contains('shake-error')) {
                groupContainer.classList.add('shake-error');
                window.setTimeout(() => groupContainer.classList.remove('shake-error'), 500);
            }
        });

        return isValid;
    }

    validateAllSteps() {
        const steps = [1, 2, 3, 4, 6];
        if (this.isPartnerFlowEnabled()) {
            steps.splice(4, 0, 5);
        }

        const firstInvalidStep = steps.find((step) => !this.validateStep(step, true));
        if (firstInvalidStep === undefined) return true;

        this.currentStep = firstInvalidStep;
        this.updateStepUI();
        window.setTimeout(() => {
            const stepElement = this.getStepElement(firstInvalidStep);
            const invalidField = stepElement?.querySelector('[aria-invalid="true"]');
            invalidField?.focus();
        }, 0);
        return false;
    }

    validateField(field, includeHiddenField = false) {
        if (!field || field.type === 'hidden') return true;
        if (!includeHiddenField && field.offsetParent === null) return true;
        if (!field.required && field.value.trim() === '') return true;

        let isValid = true;
        let errorMessage = '';
        const value = field.value.trim();

        if (field.required && !value) {
            isValid = false;
            errorMessage = '필수 항목입니다.';
        } else if (field.name === 'name' && (value.length < 1 || value.length > 50)) {
            isValid = false;
            errorMessage = '1~50자로 입력해주세요.';
        } else if (field.type === 'date' && value) {
            const date = new Date(value);
            const currentYear = new Date().getFullYear();
            if (Number.isNaN(date.getTime()) || date.getFullYear() < 1900 || date.getFullYear() > currentYear) {
                isValid = false;
                errorMessage = '올바른 날짜를 입력해주세요.';
            }
        } else if ((field.name === 'mbti' || field.name === 'partner_mbti') && value) {
            const normalized = value.toUpperCase();
            if (!/^[EI][NS][TF][JP]$/.test(normalized)) {
                isValid = false;
                errorMessage = '올바른 MBTI 형식(예: INFP)이 아닙니다.';
            } else {
                field.value = normalized;
            }
        }

        this.setFieldValidation(field, isValid, errorMessage);
        return isValid;
    }

    setFieldValidation(field, isValid, message) {
        const group = field.closest('.form-group');
        if (!group) return;

        const existingError = group.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }

        if (!isValid) {
            const errorId = `${field.id || field.name}-error`;
            field.style.borderColor = 'var(--neon-orange)';
            field.setAttribute('aria-invalid', 'true');
            field.setAttribute('aria-describedby', errorId);
            const errorEl = document.createElement('div');
            errorEl.id = errorId;
            errorEl.className = 'field-error';
            errorEl.style.cssText = 'color: var(--neon-orange); font-size: 0.8rem; margin-top: 4px;';
            errorEl.textContent = message;
            group.appendChild(errorEl);
            return;
        }

        field.style.borderColor = '';
        field.removeAttribute('aria-invalid');
        field.removeAttribute('aria-describedby');
    }

    clearFieldError(field) {
        field.style.borderColor = '';
        field.removeAttribute('aria-invalid');
        field.removeAttribute('aria-describedby');
        const group = field.closest('.form-group');
        group?.querySelector('.field-error')?.remove();
    }

    buildFormState(formData) {
        const state = Object.fromEntries(formData.entries());
        state.birth_time_unknown = Boolean(this.birthTimeUnknown?.checked);
        state.partner_birth_time_unknown = Boolean(this.partnerBirthTimeUnknown?.checked);
        state.history_consent = Boolean(this.historyConsentInput?.checked);
        return state;
    }

    async handleSubmit() {
        if (this.isSubmitting) return;
        if (!this.apiAvailable) {
            const recovered = await this.checkApiStatus();
            if (!recovered) {
                this.showError('분석 API 서버에 연결할 수 없습니다. 현재는 프런트 UI만 실행 중이거나 backend가 8000 포트에서 실행되지 않았습니다.');
                return;
            }
        }
        if (!this.validateAllSteps()) return;

        const formData = new FormData(this.form);
        const sajuData = {
            name: formData.get('name'),
            birth_date: formData.get('birth_date'),
            birth_time: this.birthTimeUnknown?.checked ? '12:00' : formData.get('birth_time'),
            gender: formData.get('gender'),
            relationship_status: formData.get('relationship_status'),
            mbti: formData.get('mbti') ? formData.get('mbti').toUpperCase() : null,
            calendar_type: formData.get('calendar_type') || 'solar',
            is_leap_month: Boolean(this.leapMonthInput?.checked),
            processing_consent: Boolean(this.form.querySelector('[name="processing_consent"]')?.checked),
            privacy_policy_version: '2026-09-07',
        };

        const focusConcern = formData.get('focus_concern')?.trim();
        if (focusConcern) {
            sajuData.focus_concern = focusConcern;
        }

        if (this.birthTimeUnknown?.checked) {
            sajuData.birth_time_unknown = true;
        }

        const partnerData = this.getPartnerData(formData);
        if (partnerData) {
            Object.assign(sajuData, partnerData);
        }

        setHistoryEnabled(Boolean(this.historyConsentInput?.checked));
        saveLastInput(this.buildFormState(formData));
        window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT));

        await this.sendUserInfo(sajuData);
    }

    getPartnerData(formData) {
        if (!this.isPartnerFlowEnabled()) return null;

        const partnerName = formData.get('partner_name') || null;
        const partnerBirthDate = formData.get('partner_birth_date') || null;
        const partnerBirthTime = this.partnerBirthTimeUnknown?.checked
            ? null
            : (formData.get('partner_birth_time') || null);
        const partnerGender = formData.get('partner_gender') || null;
        const partnerMbti = formData.get('partner_mbti')
            ? formData.get('partner_mbti').toUpperCase()
            : null;

        const hasMeaningfulValue = Boolean(
            partnerName ||
            partnerBirthDate ||
            partnerBirthTime ||
            partnerGender ||
            partnerMbti
        );

        if (!hasMeaningfulValue) {
            return null;
        }

        const payload = {
            partner_name: partnerName,
            partner_birth_date: partnerBirthDate,
            partner_birth_time: partnerBirthTime,
            partner_gender: partnerGender,
            partner_mbti: partnerMbti,
            partner_calendar_type: formData.get('partner_calendar_type') || 'solar',
            partner_is_leap_month: Boolean(this.partnerLeapMonthInput?.checked),
        };

        if (this.partnerBirthTimeUnknown?.checked) {
            payload.partner_birth_time_unknown = true;
        }

        return payload;
    }

    async sendUserInfo(sajuData) {
        try {
            this.isSubmitting = true;
            this.showLoading();

            const data = await createSajuBook(sajuData);
            const payload = this.extractAnalysisPayload(data, sajuData);

            if (payload.analysis) {
                const taskId = payload.taskId || this.createLocalTaskId();
                const analysis = {
                    ...payload.analysis,
                    task_id: payload.analysis.task_id || taskId,
                };
                saveCachedAnalysis(taskId, analysis, payload.userData || sajuData);
                this.redirectToResult(taskId);
                return;
            }

            if (data?.task_id) {
                this.redirectToResult(data.task_id);
                return;
            }

            this.showError('분석 요청은 전송되었지만 작업 식별자를 받지 못했습니다. 잠시 후 다시 시도해주세요.');
        } catch (error) {
            console.error(error);
            const message = error instanceof ApiError
                ? error.getUserMessage()
                : '오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
            this.showError(message);
        } finally {
            this.isSubmitting = false;
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

    createLocalTaskId() {
        if (window.crypto?.randomUUID) {
            return `local-${window.crypto.randomUUID()}`;
        }

        return `local-${Date.now()}`;
    }

    redirectToResult(taskId) {
        const params = new URLSearchParams({ task_id: taskId });
        window.location.href = `result.html?${params.toString()}`;
    }

    async checkApiStatus() {
        try {
            await checkHealth();
            this.apiAvailable = true;
            this.setApiStatusMessage('');
            return true;
        } catch (error) {
            this.apiAvailable = false;
            console.warn('API health check failed:', error);
            this.setApiStatusMessage('분석 API 서버에 연결할 수 없습니다. 현재 저장소에는 backend가 없거나 8000 포트에서 실행 중이지 않습니다.');
            return false;
        }
    }

    setApiStatusMessage(message) {
        if (!this.apiStatusNotice) return;

        if (!message) {
            this.apiStatusNotice.classList.add('hidden');
            this.apiStatusNotice.textContent = '';
            return;
        }

        this.apiStatusNotice.classList.remove('hidden');
        this.apiStatusNotice.textContent = message;
    }

    showLoading() {
        if (this.formShell) {
            this.formShell.style.display = 'none';
        }
        if (this.loadingStatusText) {
            this.loadingStatusText.textContent = '당신의 기질과 삶의 흐름을 읽는 중입니다.';
        }
        this.errorContainer?.classList.add('hidden');
        this.loadingContainer?.classList.remove('hidden');
        this.loadingContainer?.focus();
    }

    showError(message) {
        this.loadingContainer?.classList.add('hidden');
        if (this.formShell) {
            this.formShell.style.display = 'block';
        }
        this.errorContainer?.classList.remove('hidden');
        const errorMessage = document.getElementById('errorMessage');
        if (errorMessage) {
            errorMessage.textContent = message;
        }
        this.errorContainer?.focus();
    }

    restoreLastInput() {
        const state = getLastInput();
        if (this.historyConsentInput) {
            this.historyConsentInput.checked = isHistoryEnabled();
        }

        if (!state || !this.form) return;

        this.form.querySelectorAll('input, select').forEach((input) => {
            const stateKey = input.name || input.id;
            if (!(stateKey in state)) return;

            if (input.type === 'radio') {
                input.checked = input.value === state[stateKey];
                return;
            }

            if (input.type === 'checkbox') {
                input.checked = Boolean(state[stateKey]);
                return;
            }

            input.value = state[stateKey];
        });

        if (this.birthTimeUnknown) {
            this.birthTimeUnknown.checked = Boolean(state.birth_time_unknown);
            this.syncBirthTimeState(this.birthTimeInput, this.birthTimeUnknown);
        }

        if (this.partnerBirthTimeUnknown) {
            this.partnerBirthTimeUnknown.checked = Boolean(state.partner_birth_time_unknown);
            this.syncBirthTimeState(this.partnerBirthTimeInput, this.partnerBirthTimeUnknown);
        }

        if (this.historyConsentInput) {
            this.historyConsentInput.checked = state.history_consent ?? isHistoryEnabled();
            setHistoryEnabled(this.historyConsentInput.checked);
        }
    }
}

export { HistoryPreviewManager, PersonalOSStepperHandler, ThemeManager };

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('themeToggle')) {
            new ThemeManager();
        }
        new HistoryPreviewManager();
        const form = document.getElementById('sajuForm');
        if (form && !form.closest('[hidden]')) {
            new PersonalOSStepperHandler();
        }
    });
}
