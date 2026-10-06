import { getTaskAccess, getTaskAccessIds, saveTaskAccess, removeTaskAccess } from './storage.js';

const LOCAL_API_ORIGIN = 'http://localhost:8000';
const VALIDATION_FIELD_LABELS = {
    processing_consent: '개인정보 처리 동의',
    privacy_policy_version: '개인정보 처리 안내',
    name: '이름',
    birth_date: '생년월일',
    birth_time: '태어난 시간',
    gender: '성별',
    relationship_status: '연애 상태',
    mbti: 'MBTI',
    focus_concern: '지금 가장 궁금한 고민',
    calendar_type: '달력 유형',
    partner_name: '연인 이름',
    partner_birth_date: '연인 생년월일',
    partner_birth_time: '연인 태어난 시간',
    partner_gender: '연인 성별',
    partner_mbti: '연인 MBTI',
};

// Exact, fixed user messages reviewed in backend/app/main.py::validation_error
// and backend/app/chart.py::_calendar. Never display arbitrary server exception
// text or Pydantic msg/input/context values; new messages need explicit review.
const SAFE_VALIDATION_MESSAGES = new Set([
    '개인정보 처리 안내를 확인하고 분석에 동의해주세요.',
    '만 18세 이상인 경우에 이용할 수 있습니다.',
    '현재 버전에서는 본인의 정보만 입력해주세요.',
    '생년월일은 1900-01-01부터 오늘 사이여야 합니다.',
    '올바른 MBTI 형식이 아닙니다.',
    '태어난 시간을 입력하거나 시간 모름을 선택해주세요.',
    '본인의 윤달은 음력을 선택했을 때만 사용할 수 있습니다.',
    '연인의 윤달은 음력을 선택했을 때만 사용할 수 있습니다.',
    '본인의 음력 날짜를 변환할 수 없습니다. 날짜와 윤달 여부를 확인해주세요.',
    '연인의 음력 날짜를 변환할 수 없습니다. 날짜와 윤달 여부를 확인해주세요.',
    '생년월일을 변환할 수 없습니다. 날짜와 양력·음력·윤달 여부를 확인해주세요.',
    '입력값의 형식과 허용 범위를 확인해주세요.',
]);

function getValidationMessage(error) {
    const type = typeof error?.type === 'string' ? error.type : '';
    if (type === 'missing') return '필수 항목입니다.';
    if (type.includes('date')) return '올바른 날짜를 선택해주세요.';
    if (type.includes('time')) return '올바른 시간을 입력해주세요.';
    if (type.includes('literal')) return '제공된 항목 중에서 선택해주세요.';
    if (type.includes('string_too_short')) return '값을 입력해주세요.';
    return SAFE_VALIDATION_MESSAGES.has(error?.msg) ? error.msg : '올바른 값을 입력해주세요.';
}

function resolveApiBaseUrl() {
    if (typeof window === 'undefined') {
        return LOCAL_API_ORIGIN;
    }

    const override = window.__PERSONAL_OS_API_BASE__;
    if (typeof override === 'string' && override.trim()) {
        return override.trim().replace(/\/$/, '');
    }

    const { hostname, port } = window.location;

    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        const frontendPort = parseInt(port, 10);
        if (frontendPort >= 3000 && frontendPort < 4000) {
            return `http://${hostname}:${frontendPort - 3000 + 8000}`;
        }
        return LOCAL_API_ORIGIN;
    }

    return window.location.origin;
}

async function parseResponseBody(response) {
    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
        return response.json();
    }

    const text = await response.text();
    return text ? { message: text } : {};
}

class ApiError extends Error {
    constructor(message, status = 0, data = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }

    isValidationError() {
        return this.status === 422;
    }

    isServerError() {
        return this.status >= 500;
    }

    isClientError() {
        return this.status >= 400 && this.status < 500;
    }

    getUserMessage() {
        if (this.isValidationError()) {
            const details = this.data?.detail;
            if (SAFE_VALIDATION_MESSAGES.has(details)) return details;
            if (Array.isArray(details) && details.length > 0) {
                const firstError = details[0];
                const location = Array.isArray(firstError?.loc) ? firstError.loc : [];
                const fieldKey = location.at(-1);
                const field = typeof fieldKey === 'string' && Object.hasOwn(VALIDATION_FIELD_LABELS, fieldKey)
                    ? VALIDATION_FIELD_LABELS[fieldKey] : '입력값';
                return `${field}: ${getValidationMessage(firstError)}`;
            }
            return '입력하신 정보를 다시 확인해주세요.';
        }

        if (this.isServerError()) {
            return '서버에서 문제가 발생했습니다. 잠시 후 다시 시도해주세요.';
        }

        if (this.isClientError()) {
            return this.message || '요청을 처리할 수 없습니다.';
        }

        return this.message || '알 수 없는 오류가 발생했습니다.';
    }
}

class ApiClient {
    constructor(baseURL = resolveApiBaseUrl()) {
        const parsed = new URL(baseURL);
        const local = ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
        if (parsed.username || parsed.password || parsed.search || parsed.hash
            || (parsed.protocol !== 'https:' && !(local && parsed.protocol === 'http:'))) {
            throw new Error('API 주소는 HTTPS 또는 로컬 개발 주소여야 합니다.');
        }
        this.baseURL = baseURL.replace(/\/$/, '');
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const {
            headers = {},
            timeoutMs = 15000,
            signal: externalSignal,
            ...fetchOptions
        } = options;
        const controller = new AbortController();
        const abortFromExternalSignal = () => controller.abort(externalSignal?.reason);
        const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

        if (externalSignal) {
            if (externalSignal.aborted) {
                abortFromExternalSignal();
            } else {
                externalSignal.addEventListener('abort', abortFromExternalSignal, { once: true });
            }
        }

        const config = {
            ...fetchOptions,
            credentials: 'omit',
            cache: 'no-store',
            referrerPolicy: 'no-referrer',
            redirect: 'error',
            headers: {
                'Content-Type': 'application/json',
                ...headers,
            },
            signal: controller.signal,
        };

        try {
            const response = await fetch(url, config);
            const data = await parseResponseBody(response);

            if (!response.ok) {
                throw new ApiError(
                    data.error || data.detail || data.message || `HTTP ${response.status}`,
                    response.status,
                    data,
                );
            }

            return data;
        } catch (error) {
            if (error instanceof ApiError) {
                throw error;
            }

            if (error?.name === 'AbortError') {
                throw new ApiError(
                    '서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.',
                    0,
                    { cause: 'timeout' },
                );
            }

            throw new ApiError(
                '분석 API 서버에 연결할 수 없습니다. localhost:8000 또는 동일 출처 API가 실행 중인지 확인해주세요.',
                0,
                { originalError: error.message },
            );
        } finally {
            globalThis.clearTimeout(timeoutId);
            externalSignal?.removeEventListener('abort', abortFromExternalSignal);
        }
    }

    get(endpoint, params = {}, options = {}) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                searchParams.set(key, value);
            }
        });

        const query = searchParams.toString();
        const url = query ? `${endpoint}?${query}` : endpoint;
        return this.request(url, { ...options, method: 'GET' });
    }

    post(endpoint, data = {}, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    healthCheck() {
        return this.get('/api/v1/health', {}, { timeoutMs: 5000 });
    }

    async createSajuBook(userData) {
        const created = await this.post('/api/v1/create-saju-book', userData, { timeoutMs: 30000 });
        if (!saveTaskAccess(created.task_id, created.access_token)) {
            // Revoke an unreachable task if the browser blocks its secure storage.
            if (created.task_id && created.access_token) {
                await this.request(`/api/v1/tasks/${encodeURIComponent(created.task_id)}`, {
                    method: 'DELETE', headers: { Authorization: `Bearer ${created.access_token}` },
                }).catch(() => {});
            }
            throw new ApiError('조회 권한을 저장하지 못했습니다. 브라우저 저장소를 허용한 뒤 다시 시도해주세요.', 0);
        }
        return created;
    }

    fetchProgress(taskId) {
        const token = getTaskAccess(taskId);
        if (!token) throw new ApiError('이 탭에 조회 권한이 없습니다. 분석을 시작한 탭이나 기록 메뉴에서 확인해주세요.', 403);
        return this.get('/api/v1/progress', { task_id: taskId }, {
            timeoutMs: 15000, headers: { Authorization: `Bearer ${token}` },
        });
    }
}

const apiClient = new ApiClient();

export { apiClient, ApiClient, ApiError, resolveApiBaseUrl };

export function checkHealth() {
    return apiClient.healthCheck();
}

export function createSajuBook(sajuData) {
    return apiClient.createSajuBook(sajuData);
}

export function fetchProgress(taskId) {
    return apiClient.fetchProgress(taskId);
}


export async function deleteAnalysis(taskId) {
    const token = getTaskAccess(taskId);
    if (token) {
        try {
            await apiClient.request(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
                method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
            });
        } catch (error) {
            if (error.status !== 404) throw error;
        }
    }
    removeTaskAccess(taskId);
}

export async function deleteStoredTasks() {
    const results = await Promise.allSettled(getTaskAccessIds().map(deleteAnalysis));
    return results.every((result) => result.status === 'fulfilled');
}
