import assert from 'node:assert/strict';
import test from 'node:test';

const { ApiClient, ApiError } = await import('../frontend/assets/js/api.js');

test('API 요청은 기본 헤더와 사용자 헤더를 함께 전달한다', async () => {
    let capturedRequest;
    globalThis.fetch = async (url, options) => {
        capturedRequest = { url, options };
        return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'content-type': 'application/json' },
        });
    };

    const client = new ApiClient('https://api.example.test');
    const response = await client.request('/health', {
        method: 'GET',
        headers: { 'X-Request-Id': 'request-1' },
        timeoutMs: 100,
    });

    assert.deepEqual(response, { ok: true });
    assert.equal(capturedRequest.url, 'https://api.example.test/health');
    assert.equal(capturedRequest.options.headers['Content-Type'], 'application/json');
    assert.equal(capturedRequest.options.headers['X-Request-Id'], 'request-1');
});

test('응답 제한 시간을 넘기면 사용자용 ApiError를 반환한다', async () => {
    globalThis.fetch = async (_url, { signal }) => {
        return new Promise((_resolve, reject) => {
            signal.addEventListener('abort', () => {
                const error = new Error('aborted');
                error.name = 'AbortError';
                reject(error);
            }, { once: true });
        });
    };

    const client = new ApiClient('https://api.example.test');
    await assert.rejects(
        client.request('/slow', { timeoutMs: 5 }),
        (error) => error instanceof ApiError && error.data.cause === 'timeout',
    );
});

test('날짜 검증 오류를 사용자 친화적인 한국어로 표시한다', () => {
    const error = new ApiError('Validation Error', 422, {
        detail: [
            {
                type: 'date_from_datetime_parsing',
                loc: ['body', 'birth_date'],
                msg: 'Input should be a valid date or datetime, input is too short',
            },
        ],
    });

    assert.equal(error.getUserMessage(), '생년월일: 올바른 날짜를 선택해주세요.');
});
