import assert from 'node:assert/strict';
import test from 'node:test';
import { buildAnonymousProfile, buildAnonymousReportHtml } from '../frontend/assets/js/privacy.js';
import { ApiClient, ApiError } from '../frontend/assets/js/api.js';
import * as storage from '../frontend/assets/js/storage.js';

class MemoryStorage {
    constructor() { this.values = new Map(); }
    getItem(key) { return this.values.get(key) ?? null; }
    setItem(key, value) { this.values.set(key, String(value)); }
    removeItem(key) { this.values.delete(key); }
}

test.beforeEach(() => {
    globalThis.localStorage = new MemoryStorage();
    globalThis.sessionStorage = new MemoryStorage();
});

test('anonymous exports exclude arbitrary original prose, partner data and escaped names', () => {
    const analysis = {
        user_data: { name: 'A&B', focus_concern: 'PRIVATE-CONCERN', partner_name: 'PRIVATE-PARTNER' },
        task_id: 'PRIVATE-TASK',
        section_1_1: 'A&amp;B, PRIVATE-PARTNER, 1991년 6월 1일 <script>alert(1)</script>',
        saju_profile: { solar_birth: '1990-05-15 14:30:00', element_counts: { 목: 1, 화: 2, 토: 3, 금: 1, 수: 1 } },
    };
    const html = buildAnonymousReportHtml(analysis);
    const shareText = buildAnonymousProfile(analysis).shareText;
    for (const secret of ['A&B', 'A&amp;B', 'PRIVATE', '1990', '1991', '<script>']) {
        assert.equal(html.includes(secret), false);
        assert.equal(shareText.includes(secret), false);
    }
    assert.ok(html.includes('토: 3개'));
    assert.ok(html.includes('Content-Security-Policy'));
});

test('anonymous numeric fields cannot carry injected markup', () => {
    const html = buildAnonymousReportHtml({ saju_profile: { element_counts: {
        목: '<img src=x onerror=alert(1)>', 화: 2, 토: 2, 금: 1, 수: 1,
    } } });
    assert.equal(html.includes('<img'), false);
    assert.ok(html.includes('오행 요약을 표시할 수 없습니다'));
});

test('history TTL removes names and summaries and rereading does not extend retention', () => {
    storage.setHistoryEnabled(true);
    localStorage.setItem(storage.ANALYSIS_HISTORY_KEY, JSON.stringify([
        { task_id: 'expired', display_name: 'PRIVATE', summary: 'PRIVATE', saved_at: '2020-01-01', analysis_date: '2020-01-01' },
    ]));
    assert.deepEqual(storage.getAnalysisHistory(), []);
    assert.equal(localStorage.getItem(storage.ANALYSIS_HISTORY_KEY).includes('PRIVATE'), false);
    const yesterday = new Date(Date.now() - 86400000).toISOString();
    storage.saveHistoryEntry({ task_id: 'valid', analysis_date: yesterday, saved_at: yesterday });
    storage.saveHistoryEntry({ task_id: 'valid', analysis_date: new Date().toISOString() });
    assert.equal(storage.getAnalysisHistory()[0].saved_at, yesterday);
});

test('full deletion and consent withdrawal clear input and access credentials', () => {
    for (const clear of [() => storage.setHistoryEnabled(false), () => storage.clearCachedAnalyses()]) {
        storage.setHistoryEnabled(true);
        storage.saveLastInput({ name: 'PRIVATE', processing_consent: true, email_notification_consent: true });
        storage.saveTaskAccess('task', 'a'.repeat(43));
        assert.equal(storage.getLastInput().processing_consent, undefined);
        assert.equal(storage.getLastInput().email_notification_consent, undefined);
        clear();
        assert.equal(storage.getLastInput(), null);
        assert.equal(storage.getTaskAccess('task'), null);
    }
});

test('legacy undated inputs and expired access credentials fail closed', () => {
    sessionStorage.setItem(storage.LAST_INPUT_KEY, JSON.stringify({ name: 'PRIVATE' }));
    assert.equal(storage.getLastInput(), null);
    sessionStorage.setItem('saju-session-task-access', JSON.stringify({ task: { token: 'a'.repeat(43), savedAt: '2020-01-01' } }));
    assert.equal(storage.getTaskAccess('task'), null);
});

test('creation stores a token and progress sends it only in the authorization header', async () => {
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        return new Response(JSON.stringify(url.endsWith('create-saju-book')
            ? { task_id: 'task', access_token: 'a'.repeat(43), status: 'queued' }
            : { status: 'processing' }), { headers: { 'content-type': 'application/json' } });
    };
    const client = new ApiClient('https://api.example.test');
    await client.createSajuBook({ processing_consent: true });
    await client.fetchProgress('task');
    assert.equal(calls[1].options.headers.Authorization, `Bearer ${'a'.repeat(43)}`);
    assert.equal(calls[1].url.includes('a'.repeat(43)), false);
    assert.equal(calls[1].options.referrerPolicy, 'no-referrer');
    assert.equal(calls[1].options.redirect, 'error');
    assert.equal(calls[1].options.cache, 'no-store');
    assert.equal(localStorage.getItem('saju-task-access'), null);
    assert.throws(() => client.fetchProgress('other'), (error) => error instanceof ApiError && error.status === 403);
});

test('non-local plaintext API endpoints are rejected', () => {
    assert.throws(() => new ApiClient('http://api.example.test'));
    assert.throws(() => new ApiClient('https://user:password@api.example.test'));
    assert.doesNotThrow(() => new ApiClient('http://127.0.0.1:8000'));
});
