import { ApiError, checkHealth, createSajuBook } from './api.js';
import {
    getLastInput,
    isHistoryEnabled,
    saveCachedAnalysis,
    saveLastInput,
    setHistoryEnabled,
} from './storage.js';

function optionalValue(value) {
    const normalized = String(value || '').trim();
    return normalized || null;
}

export function buildSajuPayload(values, flags = {}) {
    const relationshipStatus = values.relationship_status || 'single';
    const payload = {
        name: String(values.name || '').trim(),
        birth_date: values.birth_date || '',
        birth_time: flags.birthTimeUnknown ? '12:00' : (values.birth_time || ''),
        gender: values.gender || '',
        relationship_status: relationshipStatus,
        mbti: optionalValue(values.mbti)?.toUpperCase() || null,
        calendar_type: values.calendar_type || 'solar',
        is_leap_month: Boolean(flags.isLeapMonth),
        processing_consent: Boolean(flags.processingConsent),
        privacy_policy_version: '2026-09-07',
        email_notification_consent: Boolean(flags.emailNotificationConsent),
    };

    const focusConcern = optionalValue(values.focus_concern);
    if (focusConcern) {
        payload.focus_concern = focusConcern;
    }

    if (flags.birthTimeUnknown) {
        payload.birth_time_unknown = true;
    }

    if (relationshipStatus === 'single') {
        return payload;
    }

    const partnerData = {
        partner_name: optionalValue(values.partner_name),
        partner_birth_date: optionalValue(values.partner_birth_date),
        partner_birth_time: flags.partnerBirthTimeUnknown
            ? null
            : optionalValue(values.partner_birth_time),
        partner_gender: optionalValue(values.partner_gender),
        partner_mbti: optionalValue(values.partner_mbti)?.toUpperCase() || null,
        partner_calendar_type: values.partner_calendar_type || 'solar',
        partner_is_leap_month: Boolean(flags.partnerIsLeapMonth),
    };
    const hasPartnerData = Object.entries(partnerData).some(([key, value]) => (
        !['partner_calendar_type', 'partner_is_leap_month'].includes(key) && value
    ));

    if (!hasPartnerData && !flags.partnerBirthTimeUnknown) {
        return payload;
    }

    Object.assign(payload, partnerData);
    if (flags.partnerBirthTimeUnknown) {
        payload.partner_birth_time_unknown = true;
    }
    return payload;
}

export class UserInfoFormHandler {
    constructor() {
        this.form = document.getElementById('userInfoForm');
        this.apiStatusNotice = document.getElementById('apiStatusNotice');
        this.partnerSection = document.getElementById('partnerInfoSection');
        this.relationshipInput = document.getElementById('relationship_status');
        this.birthDateInput = document.getElementById('birth_date');
        this.leapMonthRow = document.getElementById('leapMonthRow');
        this.leapMonthInput = document.getElementById('is_leap_month');
        this.birthTimeInput = document.getElementById('birth_time');
        this.birthTimeUnknown = document.getElementById('birth_time_unknown');
        this.partnerBirthDateInput = document.getElementById('partner_birth_date');
        this.partnerLeapMonthRow = document.getElementById('partnerLeapMonthRow');
        this.partnerLeapMonthInput = document.getElementById('partner_is_leap_month');
        this.partnerBirthTimeInput = document.getElementById('partner_birth_time');
        this.partnerBirthTimeUnknown = document.getElementById('partner_birth_time_unknown');
        this.historyConsentInput = document.getElementById('historyConsent');
        this.processingConsentInput = document.getElementById('processingConsent');
        this.emailNotificationConsentInput = document.getElementById('emailNotificationConsent');
        this.submitButton = document.getElementById('submitButton');
        this.loadingContainer = document.getElementById('loadingContainer');
        this.errorContainer = document.getElementById('errorContainer');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryButton = document.getElementById('retryButton');
        this.apiAvailable = true;
        this.isSubmitting = false;
    }

    init() {
        if (!this.form) return;
        this.setDateLimits();
        this.restoreLastInput();
        this.syncBirthTimeState();
        this.syncPartnerBirthTimeState();
        this.syncCalendarState();
        this.syncPartnerCalendarState();
        this.updatePartnerVisibility();
        this.setupEventListeners();
        this.checkApiStatus();
    }

    setupEventListeners() {
        this.form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.handleSubmit();
        });

        this.relationshipInput?.addEventListener('change', () => this.updatePartnerVisibility());
        this.form.querySelectorAll('input[name="calendar_type"]').forEach((field) => {
            field.addEventListener('change', () => this.syncCalendarState());
        });
        document.getElementById('partner_calendar_type')?.addEventListener(
            'change',
            () => this.syncPartnerCalendarState(),
        );
        this.birthTimeUnknown?.addEventListener('change', () => this.syncBirthTimeState());
        this.partnerBirthTimeUnknown?.addEventListener('change', () => this.syncPartnerBirthTimeState());
        this.historyConsentInput?.addEventListener('change', () => {
            setHistoryEnabled(this.historyConsentInput.checked);
        });
        this.retryButton?.addEventListener('click', () => this.handleSubmit());

        const concernInput = document.getElementById('focus_concern');
        const charCount = document.getElementById('concernCharCount');
        if (concernInput && charCount) {
            const updateCount = () => {
                charCount.textContent = `${concernInput.value.length} / 200자`;
            };
            concernInput.addEventListener('input', updateCount);
            updateCount();
        }

        this.form.querySelectorAll('input, select, textarea').forEach((field) => {
            field.addEventListener('input', () => this.clearFieldError(field));
            field.addEventListener('change', () => this.clearFieldError(field));
        });
    }

    setDateLimits() {
        const today = new Date();
        const maxDate = [
            today.getFullYear(),
            String(today.getMonth() + 1).padStart(2, '0'),
            String(today.getDate()).padStart(2, '0'),
        ].join('-');
        this.birthDateInput?.setAttribute('max', maxDate);
        this.partnerBirthDateInput?.setAttribute('max', maxDate);
    }

    syncBirthTimeState() {
        if (!this.birthTimeInput || !this.birthTimeUnknown) return;
        if (this.birthTimeUnknown.checked) {
            this.birthTimeInput.value = '';
            this.birthTimeInput.readOnly = true;
            this.birthTimeInput.dataset.unknownValue = 'true';
            this.birthTimeInput.removeAttribute('required');
            this.clearFieldError(this.birthTimeInput);
            return;
        }

        this.birthTimeInput.readOnly = false;
        this.birthTimeInput.setAttribute('required', '');
        if (this.birthTimeInput.value === '12:00' && this.birthTimeInput.dataset.unknownValue === 'true') {
            this.birthTimeInput.value = '';
        }
        delete this.birthTimeInput.dataset.unknownValue;
    }

    syncPartnerBirthTimeState() {
        if (!this.partnerBirthTimeInput || !this.partnerBirthTimeUnknown) return;
        this.partnerBirthTimeInput.readOnly = this.partnerBirthTimeUnknown.checked;
        if (this.partnerBirthTimeUnknown.checked) {
            this.partnerBirthTimeInput.value = '';
            this.clearFieldError(this.partnerBirthTimeInput);
        }
    }

    syncCalendarState() {
        const calendarType = this.form.querySelector('input[name="calendar_type"]:checked')?.value || 'solar';
        const isLunar = calendarType === 'lunar';
        if (this.leapMonthRow) this.leapMonthRow.hidden = !isLunar;
        if (!isLunar && this.leapMonthInput) this.leapMonthInput.checked = false;
    }

    syncPartnerCalendarState() {
        const isLunar = document.getElementById('partner_calendar_type')?.value === 'lunar';
        if (this.partnerLeapMonthRow) this.partnerLeapMonthRow.hidden = !isLunar;
        if (!isLunar && this.partnerLeapMonthInput) this.partnerLeapMonthInput.checked = false;
        this.refreshPartnerDisclosureHeight();
    }

    updatePartnerVisibility() {
        if (!this.partnerSection) return;
        const hasPartner = ['dating', 'married'].includes(this.relationshipInput?.value || '');
        const isInitialRender = this.partnerSection.hidden;

        if (isInitialRender) {
            this.partnerSection.hidden = false;
        }

        this.refreshPartnerDisclosureHeight();

        this.partnerSection.classList.toggle('is-expanded', hasPartner);
        this.partnerSection.setAttribute('aria-hidden', String(!hasPartner));
        this.partnerSection.toggleAttribute('inert', !hasPartner);
        this.relationshipInput?.setAttribute('aria-expanded', String(hasPartner));

        if (isInitialRender) {
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    this.partnerSection?.classList.add('is-disclosure-ready');
                });
            });
        }
    }

    refreshPartnerDisclosureHeight() {
        if (!this.partnerSection || this.partnerSection.hidden) return;
        const expandedHeight = this.partnerSection.scrollHeight;
        if (expandedHeight <= 0) return;
        this.partnerSection.style.setProperty(
            '--partner-expanded-height',
            `${expandedHeight}px`,
        );
    }

    restoreLastInput() {
        const state = getLastInput();
        if (this.historyConsentInput) {
            this.historyConsentInput.checked = isHistoryEnabled();
        }
        if (!state) return;

        this.form.querySelectorAll('input, select, textarea').forEach((field) => {
            const key = field.name || field.id;
            if (!(key in state)) return;
            if (field.type === 'radio') {
                field.checked = field.value === state[key];
            } else if (field.type === 'checkbox') {
                field.checked = Boolean(state[key]);
            } else {
                field.value = state[key] ?? '';
            }
        });

        if (this.birthTimeUnknown) {
            this.birthTimeUnknown.checked = Boolean(state.birth_time_unknown);
            if (this.birthTimeUnknown.checked && this.birthTimeInput) {
                this.birthTimeInput.dataset.unknownValue = 'true';
            }
        }
        if (this.partnerBirthTimeUnknown) {
            this.partnerBirthTimeUnknown.checked = Boolean(state.partner_birth_time_unknown);
        }
        if (this.historyConsentInput) {
            this.historyConsentInput.checked = state.history_consent ?? isHistoryEnabled();
            setHistoryEnabled(this.historyConsentInput.checked);
        }
    }

    buildFormState(formData) {
        const state = {
            ...Object.fromEntries(formData.entries()),
            birth_time_unknown: Boolean(this.birthTimeUnknown?.checked),
            partner_birth_time_unknown: Boolean(this.partnerBirthTimeUnknown?.checked),
            history_consent: Boolean(this.historyConsentInput?.checked),
        };
        delete state.email_notification_consent;
        delete state.processing_consent;
        return state;
    }

    validate() {
        this.clearAllErrors();
        const errors = [];
        const nameInput = document.getElementById('name');
        const selectedGender = this.form.querySelector('input[name="gender"]:checked');

        if (!nameInput?.value.trim()) {
            errors.push([nameInput, '이름 또는 닉네임을 입력해주세요.']);
        }
        if (!this.birthDateInput?.value) {
            errors.push([this.birthDateInput, '생년월일을 선택해주세요.']);
        } else if (!this.birthDateInput.checkValidity()) {
            errors.push([this.birthDateInput, '올바른 생년월일을 선택해주세요.']);
        }
        if (!this.birthTimeUnknown?.checked && !this.birthTimeInput?.value) {
            errors.push([this.birthTimeInput, '태어난 시간을 입력하거나 시간 모름을 선택해주세요.']);
        }
        if (!selectedGender) {
            const genderFieldset = this.form.querySelector('.gender-control')?.closest('fieldset');
            errors.push([genderFieldset, '성별을 선택해주세요.']);
        }
        if (!this.processingConsentInput?.checked) {
            errors.push([
                this.processingConsentInput,
                '리포트 생성을 위해 개인정보 처리에 동의해주세요.',
            ]);
        }
        const hasPartner = ['dating', 'married'].includes(this.relationshipInput?.value || '');
        if (
            hasPartner
            && this.partnerBirthDateInput?.value
            && !this.partnerBirthDateInput.checkValidity()
        ) {
            errors.push([this.partnerBirthDateInput, '연인의 생년월일을 확인해주세요.']);
        }

        errors.forEach(([field, message]) => this.setFieldError(field, message));
        if (errors.length) {
            errors[0][0]?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
            const focusTarget = errors[0][0]?.matches?.('input, select, button')
                ? errors[0][0]
                : errors[0][0]?.querySelector?.('input, select, button');
            focusTarget?.focus({ preventScroll: true });
            return false;
        }
        return true;
    }

    setFieldError(field, message) {
        if (!field) return;
        const container = field.classList?.contains('field') || field.tagName === 'FIELDSET'
            ? field
            : field.closest('.field');
        if (!container) return;

        const error = document.createElement('p');
        const targetId = field.id || field.querySelector?.('input, select')?.id || `field-${Date.now()}`;
        error.id = `${targetId}-error`;
        error.className = 'field-error';
        error.setAttribute('role', 'alert');
        error.textContent = message;
        container.appendChild(error);

        const target = field.matches?.('input, select') ? field : field.querySelector?.('input, select');
        target?.setAttribute('aria-invalid', 'true');
        target?.setAttribute('aria-errormessage', error.id);
    }

    clearFieldError(field) {
        const container = field?.closest?.('.field') || field?.closest?.('fieldset');
        container?.querySelector('.field-error')?.remove();
        field?.removeAttribute?.('aria-invalid');
        field?.removeAttribute?.('aria-errormessage');
    }

    clearAllErrors() {
        this.form.querySelectorAll('.field-error').forEach((error) => error.remove());
        this.form.querySelectorAll('[aria-invalid="true"]').forEach((field) => {
            field.removeAttribute('aria-invalid');
            field.removeAttribute('aria-errormessage');
        });
    }

    getPayload(formData) {
        return buildSajuPayload(Object.fromEntries(formData.entries()), {
            birthTimeUnknown: Boolean(this.birthTimeUnknown?.checked),
            partnerBirthTimeUnknown: Boolean(this.partnerBirthTimeUnknown?.checked),
            isLeapMonth: Boolean(this.leapMonthInput?.checked),
            partnerIsLeapMonth: Boolean(this.partnerLeapMonthInput?.checked),
            processingConsent: Boolean(this.processingConsentInput?.checked),
            emailNotificationConsent: Boolean(this.emailNotificationConsentInput?.checked),
        });
    }

    async handleSubmit() {
        if (this.isSubmitting) return;
        if (!this.apiAvailable) {
            const recovered = await this.checkApiStatus();
            if (!recovered) {
                this.showError('분석 API 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해주세요.');
                return;
            }
        }
        if (!this.validate()) return;

        const formData = new FormData(this.form);
        const payload = this.getPayload(formData);
        setHistoryEnabled(Boolean(this.historyConsentInput?.checked));
        saveLastInput(this.buildFormState(formData));
        await this.sendUserInfo(payload);
    }

    async sendUserInfo(payload) {
        try {
            this.isSubmitting = true;
            this.submitButton?.setAttribute('disabled', '');
            this.showLoading();
            const data = await createSajuBook(payload);
            const result = this.extractAnalysisPayload(data, payload);

            if (result.analysis) {
                const taskId = result.taskId || this.createLocalTaskId();
                const analysis = {
                    ...result.analysis,
                    task_id: result.analysis.task_id || taskId,
                };
                saveCachedAnalysis(taskId, analysis, result.userData || payload);
                this.redirectToResult(taskId);
                return;
            }
            if (data?.task_id) {
                this.redirectToResult(data.task_id);
                return;
            }
            this.showError('분석 요청은 전송되었지만 작업 식별자를 받지 못했습니다. 다시 시도해주세요.');
        } catch (error) {
            console.error(error);
            const message = error instanceof ApiError
                ? error.getUserMessage()
                : '오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
            this.showError(message);
        } finally {
            this.isSubmitting = false;
            this.submitButton?.removeAttribute('disabled');
        }
    }

    extractAnalysisPayload(data, fallbackUserData = {}) {
        if (!data || typeof data !== 'object') {
            return { analysis: null, userData: fallbackUserData, taskId: null };
        }
        const directAnalysis = data.analysis || data.analysis_result || data;
        const hasAnalysis = Boolean(
            directAnalysis?.table_of_contents?.chapters?.length
            || Object.keys(directAnalysis || {}).some((key) => key.startsWith('section_'))
        );
        if (!hasAnalysis) {
            return { analysis: null, userData: fallbackUserData, taskId: data.task_id || null };
        }
        return {
            analysis: directAnalysis,
            userData: directAnalysis.user_data || fallbackUserData,
            taskId: directAnalysis.task_id || data.task_id || null,
        };
    }

    createLocalTaskId() {
        return window.crypto?.randomUUID
            ? `local-${window.crypto.randomUUID()}`
            : `local-${Date.now()}`;
    }

    redirectToResult(taskId) {
        window.location.href = `result.html?task_id=${encodeURIComponent(taskId)}`;
    }

    async checkApiStatus() {
        try {
            await checkHealth();
            this.apiAvailable = true;
            this.setApiStatusMessage('');
            return true;
        } catch (error) {
            console.warn('API health check failed:', error);
            this.apiAvailable = false;
            this.setApiStatusMessage('분석 API 서버에 연결할 수 없습니다. 서버를 실행한 뒤 다시 시도해주세요.');
            return false;
        }
    }

    setApiStatusMessage(message) {
        if (!this.apiStatusNotice) return;
        this.apiStatusNotice.textContent = message;
        this.apiStatusNotice.classList.toggle('hidden', !message);
    }

    showLoading() {
        this.errorContainer?.classList.add('hidden');
        this.loadingContainer?.classList.remove('hidden');
        this.loadingContainer?.focus();
    }

    showError(message) {
        this.loadingContainer?.classList.add('hidden');
        if (this.errorMessage) this.errorMessage.textContent = message;
        this.errorContainer?.classList.remove('hidden');
        this.errorContainer?.focus();
    }
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        new UserInfoFormHandler().init();
    });
}
