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
// Fixed public messages emitted by backend/app/chart.py::_calendar.
const chartValidationMessages = [
    '생년월일을 변환할 수 없습니다. 날짜와 양력·음력·윤달 여부를 확인해주세요.',
    '생년월일은 1900-01-01부터 오늘 사이여야 합니다.',
    '만 18세 이상인 경우에 이용할 수 있습니다.',
];

test('원국 API의 검토된 422 문자열 이유를 그대로 안내한다', async () => {
    const previousFetch = globalThis.fetch;
    try {
        const client = new ApiClient('https://api.example.test');
        for (const detail of chartValidationMessages) {
            globalThis.fetch = async () => new Response(JSON.stringify({ detail }), {
                status: 422,
                headers: { 'content-type': 'application/json' },
            });
            await assert.rejects(client.post('/api/v2/chart', {}), (error) => {
                assert.ok(error instanceof ApiError);
                assert.equal(error.getUserMessage(), detail);
                return true;
            });
        }
    } finally {
        globalThis.fetch = previousFetch;
    }
});

test('422의 임의 문자열과 변형 문구는 내부 예외나 개인정보를 노출하지 않는다', () => {
    const privateText = 'private-user@example.test internal /srv/private/provider.py';
    for (const detail of [
        privateText,
        `<script>${privateText}</script>`,
        ...chartValidationMessages.flatMap((message) => [
            `${message} ${privateText}`,
            `${privateText} ${message}`,
            `${message.slice(0, -1)} ${privateText}.`,
        ]),
        { message: privateText, input: privateText },
        null,
    ]) {
        const error = new ApiError(privateText, 422, {
            detail,
            error: privateText,
            message: privateText,
            input: privateText,
        });
        assert.equal(error.getUserMessage(), '입력하신 정보를 다시 확인해주세요.');
    }
    assert.equal(new ApiError(privateText, 422, null).getUserMessage(), '입력하신 정보를 다시 확인해주세요.');
});

test('HTML 오류 본문도 사용자에게 그대로 전달하지 않는다', async () => {
    const previousFetch = globalThis.fetch;
    try {
        globalThis.fetch = async () => new Response('<h1>private exception details</h1>', {
            status: 422,
            headers: { 'content-type': 'text/html' },
        });
        await assert.rejects(new ApiClient('https://api.example.test').get('/api/v2/chart'), (error) => {
            assert.equal(error.getUserMessage(), '입력하신 정보를 다시 확인해주세요.');
            return true;
        });
    } finally {
        globalThis.fetch = previousFetch;
    }
});

test('배열 검증 오류는 기존 고정 안내와 항목 이름을 유지한다', () => {
    const cases = [
        ['processing_consent', '개인정보 처리 안내를 확인하고 분석에 동의해주세요.', '개인정보 처리 동의'],
        ['birth_date', '생년월일은 1900-01-01부터 오늘 사이여야 합니다.', '생년월일'],
        ['birth_time', '태어난 시간을 입력하거나 시간 모름을 선택해주세요.', '태어난 시간'],
    ];
    for (const [field, msg, label] of cases) {
        const error = new ApiError('Validation Error', 422, {
            detail: [{ loc: ['body', field], type: 'value_error', msg }],
        });
        assert.equal(error.getUserMessage(), `${label}: ${msg}`);
    }
});

test('배열의 임의 msg와 input/context/loc는 고정된 안전 안내로 대체한다', () => {
    const privateText = 'private-user@example.test';
    for (const msg of [
        privateText,
        `<script>${privateText}</script>`,
        `${chartValidationMessages[0]} ${privateText}`,
        { message: privateText },
    ]) {
        const error = new ApiError(privateText, 422, {
            detail: [{
                type: 'value_error',
                loc: ['body', privateText],
                msg,
                input: privateText,
                ctx: { error: privateText },
            }],
        });
        assert.equal(error.getUserMessage(), '입력값: 올바른 값을 입력해주세요.');
    }
    const dateError = new ApiError(privateText, 422, {
        detail: [{ type: 'date_from_datetime_parsing', loc: ['body', 'birth_date'], msg: privateText, input: privateText }],
    });
    assert.equal(dateError.getUserMessage(), '생년월일: 올바른 날짜를 선택해주세요.');
});

test('비정상 검증 배열과 프로토타입 항목명도 안전한 안내를 반환한다', () => {
    for (const detail of [
        [null],
        [{}],
        [{ type: { toString: 'private-value' }, loc: ['body', '__proto__'] }],
        [{ loc: ['body', 'constructor'] }],
    ]) {
        assert.equal(new ApiError('Validation Error', 422, { detail }).getUserMessage(), '입력값: 올바른 값을 입력해주세요.');
    }
});
