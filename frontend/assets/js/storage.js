const ANALYSIS_CACHE_KEY = 'saju-analysis-cache';
const SESSION_ANALYSIS_CACHE_KEY = 'saju-analysis-session-cache';
const ANALYSIS_HISTORY_KEY = 'saju-analysis-history';
const HISTORY_CONSENT_KEY = 'saju-history-consent';
const LAST_INPUT_KEY = 'saju-last-input';
const TASK_ACCESS_KEY = 'saju-task-access';
const SESSION_TASK_ACCESS_KEY = 'saju-session-task-access';
const ACCESS_TTL_MS = 1000 * 60 * 60 * 24;

const CACHE_TTL_MS = 1000 * 60 * 60 * 24 * 30;
const MAX_HISTORY_ITEMS = 12;
const MAX_CACHE_ITEMS = 12;

function readJson(storage, key, fallback) {
    try {
        const raw = storage.getItem(key);
        if (!raw) return fallback;
        return JSON.parse(raw);
    } catch {
        return fallback;
    }
}

function writeJson(storage, key, value) {
    try {
        storage.setItem(key, JSON.stringify(value));
        return true;
    } catch {
        return false;
    }
}

function removeKey(storage, key) {
    try {
        storage.removeItem(key);
        return true;
    } catch {
        return false;
    }
}

function isValidDate(value) {
    return Boolean(value) && !Number.isNaN(new Date(value).getTime());
}

function normalizeHistoryEntry(item) {
    if (!item || typeof item !== 'object') return null;

    const taskId = item.task_id || item.id;
    if (!taskId) return null;

    const analysisDate = isValidDate(item.analysis_date)
        ? item.analysis_date
        : isValidDate(item.saved_at)
            ? item.saved_at
            : null;
    if (!analysisDate) return null;

    return {
        id: String(item.id || taskId),
        task_id: String(taskId),
        display_name: String(item.display_name || item.name || '익명'),
        summary: String(item.summary || ''),
        analysis_date: analysisDate,
        saved_at: item.saved_at || analysisDate,
    };
}

function pruneExpiredCache(cache) {
    const pruned = {};
    const now = Date.now();

    Object.entries(cache || {}).forEach(([taskId, entry]) => {
        const savedAt = entry?.savedAt ? new Date(entry.savedAt).getTime() : Number.NaN;
        if (!entry || Number.isNaN(savedAt)) return;
        if (now - savedAt >= CACHE_TTL_MS || savedAt > now) return;
        pruned[taskId] = entry;
    });

    return pruned;
}

function trimCache(cache) {
    const entries = Object.entries(cache).map(([key, value], index) => ({ key, value, index }));
    entries.sort((left, right) => {
        const timeDifference = new Date(right.value.savedAt).getTime() - new Date(left.value.savedAt).getTime();
        return timeDifference || right.index - left.index;
    });

    return Object.fromEntries(
        entries.slice(0, MAX_CACHE_ITEMS).map(({ key, value }) => [key, value]),
    );
}

function readCache(storage, key) {
    const cache = readJson(storage, key, {});
    const normalized = typeof cache === 'object' && cache ? pruneExpiredCache(cache) : {};

    if (Object.keys(normalized).length !== Object.keys(cache || {}).length) {
        writeJson(storage, key, normalized);
    }

    return normalized;
}

function removeCacheEntry(storage, key, taskId) {
    const cache = readCache(storage, key);
    if (!cache[taskId]) return true;
    delete cache[taskId];
    return writeJson(storage, key, cache);
}

export {
    ANALYSIS_CACHE_KEY,
    SESSION_ANALYSIS_CACHE_KEY,
    ANALYSIS_HISTORY_KEY,
    HISTORY_CONSENT_KEY,
    LAST_INPUT_KEY,
};

export function isHistoryEnabled() {
    try {
        return localStorage.getItem(HISTORY_CONSENT_KEY) === 'true';
    } catch {
        return false;
    }
}

export function setHistoryEnabled(enabled) {
    try {
        localStorage.setItem(HISTORY_CONSENT_KEY, enabled ? 'true' : 'false');

        if (!enabled) {
            removeKey(localStorage, ANALYSIS_CACHE_KEY);
            removeKey(localStorage, ANALYSIS_HISTORY_KEY);
            removeKey(sessionStorage, SESSION_ANALYSIS_CACHE_KEY);
            clearLastInput();
            removeKey(localStorage, TASK_ACCESS_KEY);
            removeKey(sessionStorage, SESSION_TASK_ACCESS_KEY);
        }

        return true;
    } catch {
        return false;
    }
}

export function getAnalysisCache() {
    return readCache(localStorage, ANALYSIS_CACHE_KEY);
}

export function getCachedAnalysis(taskId) {
    if (!taskId) return null;

    const sessionCache = readCache(sessionStorage, SESSION_ANALYSIS_CACHE_KEY);
    if (sessionCache[taskId]) {
        return sessionCache[taskId];
    }

    if (!isHistoryEnabled()) return null;
    return getAnalysisCache()[taskId] || null;
}

export function saveCachedAnalysis(taskId, analysis, userData) {
    if (!taskId) return false;

    const persist = isHistoryEnabled();
    const storage = persist ? localStorage : sessionStorage;
    const key = persist ? ANALYSIS_CACHE_KEY : SESSION_ANALYSIS_CACHE_KEY;
    const cache = readCache(storage, key);
    cache[taskId] = {
        analysis,
        userData,
        savedAt: cache[taskId]?.savedAt || new Date().toISOString(),
    };

    const saved = writeJson(storage, key, trimCache(cache));
    if (saved && persist) {
        removeCacheEntry(sessionStorage, SESSION_ANALYSIS_CACHE_KEY, taskId);
    }
    return saved;
}

export function removeCachedAnalysis(taskId) {
    if (!taskId) return false;
    const persistentRemoved = removeCacheEntry(localStorage, ANALYSIS_CACHE_KEY, taskId);
    const sessionRemoved = removeCacheEntry(sessionStorage, SESSION_ANALYSIS_CACHE_KEY, taskId);
    return persistentRemoved && sessionRemoved;
}

export function clearCachedAnalyses() {
    const persistentRemoved = removeKey(localStorage, ANALYSIS_CACHE_KEY);
    const sessionRemoved = removeKey(sessionStorage, SESSION_ANALYSIS_CACHE_KEY);
    const inputRemoved = clearLastInput();
    removeKey(localStorage, TASK_ACCESS_KEY);
    removeKey(sessionStorage, SESSION_TASK_ACCESS_KEY);
    return persistentRemoved && sessionRemoved && inputRemoved;
}

export function getAnalysisHistory() {
    const history = readJson(localStorage, ANALYSIS_HISTORY_KEY, []);
    if (!Array.isArray(history)) return [];
    const now = Date.now();
    const active = history.map(normalizeHistoryEntry).filter((entry) => {
        if (!entry) return false;
        const age = now - new Date(entry.saved_at).getTime();
        return Number.isFinite(age) && age >= 0 && age < CACHE_TTL_MS;
    }).sort((a, b) => new Date(b.analysis_date).getTime() - new Date(a.analysis_date).getTime())
        .slice(0, MAX_HISTORY_ITEMS);
    writeJson(localStorage, ANALYSIS_HISTORY_KEY, active);
    return active;
}

export function saveHistoryEntry(entry) {
    const now = new Date().toISOString();
    const existing = getAnalysisHistory().find((item) => item.task_id === entry?.task_id);
    const normalized = normalizeHistoryEntry({ ...entry, analysis_date: entry?.analysis_date || now, saved_at: existing?.saved_at || entry?.saved_at || now });
    if (!normalized || !isHistoryEnabled()) return false;

    const history = getAnalysisHistory().filter((item) => item.task_id !== normalized.task_id);
    history.unshift(normalized);

    return writeJson(localStorage, ANALYSIS_HISTORY_KEY, history.slice(0, MAX_HISTORY_ITEMS));
}

export function removeHistoryEntryById(entryId) {
    if (!entryId) return false;
    const history = getAnalysisHistory();
    const updated = history.filter((entry) => `${entry.id}` !== `${entryId}`);
    return writeJson(localStorage, ANALYSIS_HISTORY_KEY, updated);
}

export function clearHistory() {
    return removeKey(localStorage, ANALYSIS_HISTORY_KEY);
}

export function getHistoryDateLabel(item) {
    if (!item?.analysis_date || !isValidDate(item.analysis_date)) {
        return '날짜 정보 없음';
    }

    return new Date(item.analysis_date).toLocaleDateString('ko-KR');
}

export function saveLastInput(state) {
    const { processing_consent, email_notification_consent, privacy_policy_version, ...input } = state;
    return writeJson(sessionStorage, LAST_INPUT_KEY, { ...input, stored_at: new Date().toISOString() });
}

export function getLastInput() {
    const input = readJson(sessionStorage, LAST_INPUT_KEY, null);
    const age = Date.now() - new Date(input?.stored_at).getTime();
    if (!Number.isFinite(age) || age < 0 || age >= ACCESS_TTL_MS) {
        clearLastInput();
        return null;
    }
    // Never restore consent from legacy or manually edited stored inputs.
    const { processing_consent, email_notification_consent, privacy_policy_version, ...safeInput } = input;
    return safeInput;
}


export function clearLastInput() {
    return removeKey(sessionStorage, LAST_INPUT_KEY);
}

function readTaskAccess(storage, key) {
    const entries = readJson(storage, key, {});
    const valid = Object.fromEntries(Object.entries(entries || {}).filter(([id, entry]) => {
        const age = Date.now() - new Date(entry?.savedAt).getTime();
        return id && typeof entry?.token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(entry.token)
            && Number.isFinite(age) && age >= 0 && age < ACCESS_TTL_MS;
    }));
    writeJson(storage, key, valid);
    return valid;
}

export function saveTaskAccess(taskId, token) {
    if (!taskId || !/^[A-Za-z0-9_-]{43}$/.test(token || '')) return false;
    const persist = isHistoryEnabled();
    const storage = persist ? localStorage : sessionStorage;
    const key = persist ? TASK_ACCESS_KEY : SESSION_TASK_ACCESS_KEY;
    const entries = readTaskAccess(storage, key);
    entries[taskId] = { token, savedAt: new Date().toISOString() };
    return writeJson(storage, key, trimCache(entries));
}

export function getTaskAccess(taskId) {
    return readTaskAccess(sessionStorage, SESSION_TASK_ACCESS_KEY)[taskId]?.token
        || (isHistoryEnabled() ? readTaskAccess(localStorage, TASK_ACCESS_KEY)[taskId]?.token : null)
        || null;
}

export function getTaskAccessIds() {
    return [...new Set([
        ...Object.keys(readTaskAccess(sessionStorage, SESSION_TASK_ACCESS_KEY)),
        ...Object.keys(readTaskAccess(localStorage, TASK_ACCESS_KEY)),
    ])];
}

export function removeTaskAccess(taskId) {
    for (const [storage, key] of [[localStorage, TASK_ACCESS_KEY], [sessionStorage, SESSION_TASK_ACCESS_KEY]]) {
        const entries = readTaskAccess(storage, key);
        delete entries[taskId];
        writeJson(storage, key, entries);
    }
}
