import assert from 'node:assert/strict';
import test from 'node:test';

class MemoryStorage {
    constructor() {
        this.values = new Map();
    }

    getItem(key) {
        return this.values.has(key) ? this.values.get(key) : null;
    }

    setItem(key, value) {
        this.values.set(key, String(value));
    }

    removeItem(key) {
        this.values.delete(key);
    }

    clear() {
        this.values.clear();
    }
}

globalThis.localStorage = new MemoryStorage();
globalThis.sessionStorage = new MemoryStorage();

const storage = await import('../frontend/assets/js/storage.js');

function resetStorage() {
    localStorage.clear();
    sessionStorage.clear();
}

test.beforeEach(resetStorage);

test('비동의 분석 결과는 현재 세션에만 저장한다', () => {
    storage.setHistoryEnabled(false);
    storage.saveCachedAnalysis('task-session', { section_1_1: '결과' }, { name: '테스트' });

    assert.equal(localStorage.getItem(storage.ANALYSIS_CACHE_KEY), null);
    assert.ok(sessionStorage.getItem(storage.SESSION_ANALYSIS_CACHE_KEY));
    assert.equal(storage.getCachedAnalysis('task-session').userData.name, '테스트');
});

test('동의한 분석 결과는 영구 캐시에 저장한다', () => {
    storage.setHistoryEnabled(true);
    storage.saveCachedAnalysis('task-local', { section_1_1: '결과' }, { name: '테스트' });

    assert.ok(localStorage.getItem(storage.ANALYSIS_CACHE_KEY));
    assert.equal(sessionStorage.getItem(storage.SESSION_ANALYSIS_CACHE_KEY), null);
    assert.equal(storage.getCachedAnalysis('task-local').analysis.section_1_1, '결과');
});

test('동의 철회는 저장된 기록과 모든 캐시를 삭제한다', () => {
    storage.setHistoryEnabled(true);
    storage.saveCachedAnalysis('task-local', { section_1_1: '결과' }, { name: '테스트' });
    storage.saveHistoryEntry({ id: 'task-local', task_id: 'task-local', display_name: '테스트' });

    storage.setHistoryEnabled(false);

    assert.equal(localStorage.getItem(storage.ANALYSIS_CACHE_KEY), null);
    assert.equal(localStorage.getItem(storage.ANALYSIS_HISTORY_KEY), null);
    assert.equal(sessionStorage.getItem(storage.SESSION_ANALYSIS_CACHE_KEY), null);
});

test('캐시는 최근 12개까지만 유지한다', () => {
    storage.setHistoryEnabled(true);
    for (let index = 0; index < 14; index += 1) {
        storage.saveCachedAnalysis(`task-${index}`, { section_1_1: `${index}` }, {});
    }

    assert.equal(Object.keys(storage.getAnalysisCache()).length, 12);
    assert.equal(storage.getCachedAnalysis('task-13').analysis.section_1_1, '13');
});
