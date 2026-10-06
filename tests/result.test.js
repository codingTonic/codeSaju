import assert from 'node:assert/strict';
import test from 'node:test';

globalThis.localStorage = globalThis.localStorage || {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
};
globalThis.sessionStorage = globalThis.sessionStorage || globalThis.localStorage;

const { PersonalOSResultHandler } = await import('../frontend/assets/js/result.js');

function createHandler() {
    const handler = Object.create(PersonalOSResultHandler.prototype);
    handler.pages = [];
    handler.renderChapterTabs = () => {};
    handler.showError = (message) => {
        handler.errorMessage = message;
    };
    return handler;
}

test('무료 요약은 자기이해 해석을 우선하고 이전 결과도 표시한다', () => {
    const previousDocument = globalThis.document;
    globalThis.document = { getElementById: () => null, querySelector: () => null };
    try {
        const handler = createHandler();
        handler.quickSummaryPanel = { classList: { remove() {} } };
        handler.sharpSummaryHeadline = {};
        handler.sharpSummaryBody = {};
        handler.sharpSummaryFocus = {};
        handler.sharpStrengthTitle = {};
        handler.renderTextList = () => {};
        handler.restoreInterpretationFeedback = () => {};
        handler.renderQuickSummary({self_portrait: {
            headline: '내가 편안해지는 조건', body: '조건에 따라 다르게 드러나는 기질입니다.',
            closing: '같은 행동에도 다른 이유가 있습니다.', scene: '역할을 직접 고른 때와 맡겨진 때를 비교합니다.',
        }});
        assert.equal(handler.sharpSummaryHeadline.textContent, '내가 편안해지는 조건');
        assert.equal(handler.sharpSummaryBody.textContent, '조건에 따라 다르게 드러나는 기질입니다.');
        assert.equal(handler.sharpSummaryFocus.textContent, '같은 행동에도 다른 이유가 있습니다.');
        assert.equal(handler.sharpStrengthTitle.textContent, '역할을 직접 고른 때와 맡겨진 때를 비교합니다.');
        handler.renderQuickSummary({one_line:'이전 해석', direct_answer:'이전 방향'});
        assert.equal(handler.sharpSummaryHeadline.textContent, '이전 해석');
        assert.equal(handler.sharpSummaryFocus.textContent, '이전 방향');
    } finally {
        globalThis.document = previousDocument;
    }
});

test('이전 카드 보기 설정은 스크롤 보기로 안전하게 전환된다', () => {
    const storage = globalThis.localStorage;
    try {
        globalThis.localStorage = { getItem: () => 'card' };
        const handler = createHandler();
        assert.equal(handler.loadViewMode(), 'all');
        globalThis.localStorage = { getItem: () => 'page' };
        assert.equal(handler.loadViewMode(), 'page');
        globalThis.localStorage = { getItem: () => 'unknown' };
        assert.equal(handler.loadViewMode(), 'all');
    } finally {
        globalThis.localStorage = storage;
    }
});

test('기존 카드 모드 요청도 빈 화면 대신 스크롤 본문을 표시한다', () => {
    const handler = createHandler();
    handler.viewModeButtons = [];
    handler.saveViewMode = (mode) => { handler.savedMode = mode; };
    handler.renderAllSections = () => { handler.rendered = true; };
    handler.switchViewMode('card');
    assert.equal(handler.currentViewMode, 'all');
    assert.equal(handler.savedMode, 'all');
    assert.equal(handler.rendered, true);
});

test('리포트 탭 키보드 이동은 순환하며 선택 권한을 바꾸지 않는다', () => {
    const handler = createHandler();
    let focused = -1;
    handler.premiumUnlocked = false;
    handler.stepTabButtons = [0, 1, 2].map((index) => ({
        tabIndex: index === 0 ? 0 : -1,
        focus() { focused = index; },
    }));
    let prevented = false;
    handler.focusAdjacentStepTab({
        key: 'ArrowLeft',
        currentTarget: handler.stepTabButtons[0],
        preventDefault() { prevented = true; },
    });
    assert.equal(focused, 2);
    assert.equal(prevented, true);
    assert.deepEqual(handler.stepTabButtons.map((tab) => tab.tabIndex), [-1, -1, 0]);
    assert.equal(handler.premiumUnlocked, false);
    handler.focusAdjacentStepTab({
        key: 'Home', currentTarget: handler.stepTabButtons[2], preventDefault() {},
    });
    assert.equal(focused, 0);
});

test('목차가 없어도 모든 section 키를 페이지로 만든다', () => {
    const handler = createHandler();
    handler.renderPage = () => {};
    const rendered = handler.buildBookPages({
        section_1_1: '첫 번째',
        section_1_2: '두 번째',
        section_2_1: '세 번째',
    });

    assert.equal(rendered, true);
    assert.deepEqual(handler.pages.map((page) => page.id), [
        'section_1_1',
        'section_1_2',
        'section_2_1',
    ]);
});

test('표시 가능한 섹션이 없으면 실패를 반환한다', () => {
    const handler = createHandler();
    handler.renderPage = () => {};

    assert.equal(handler.buildBookPages({}), false);
    assert.equal(handler.errorMessage, '표시할 분석 섹션을 찾지 못했습니다.');
});

test('페이지 이동 시 현재 위치와 버튼 상태를 갱신한다', () => {
    const handler = createHandler();
    handler.pages = [
        { chapter: 1, chapterTitle: '정체성', title: '첫째', markdown: '본문 1' },
        { chapter: 1, chapterTitle: '정체성', title: '둘째', markdown: '본문 2' },
    ];
    handler.pageChapterEl = { textContent: '' };
    handler.pageTitleEl = { textContent: '' };
    handler.pageNumberEl = { textContent: '' };
    handler.pageChapterMetaEl = { textContent: '' };
    handler.previousPageButton = { disabled: false };
    handler.nextPageButton = { disabled: false };
    handler.renderMarkdown = (markdown) => {
        handler.renderedMarkdown = markdown;
    };
    globalThis.document = { querySelectorAll: () => [] };

    handler.renderPage(1);

    assert.equal(handler.currentPageIndex, 1);
    assert.equal(handler.pageNumberEl.textContent, '2 / 2');
    assert.equal(handler.previousPageButton.disabled, false);
    assert.equal(handler.nextPageButton.disabled, false);
    assert.equal(handler.nextPageButton.textContent, '한눈에 요약 보기 →');
    assert.equal(handler.renderedMarkdown, '본문 2');
});

test('마지막 이야기의 다음 버튼은 실전 요약으로 이동한다', () => {
    const handler = createHandler();
    handler.pages = [{ title: '마지막 이야기' }];
    handler.currentPageIndex = 0;
    handler.scrollToPracticalReport = () => {
        handler.scrolledToSummary = true;
    };
    handler.renderPage = () => {
        handler.renderedAnotherPage = true;
    };

    handler.goToNextDestination();

    assert.equal(handler.scrolledToSummary, true);
    assert.equal(handler.renderedAnotherPage, undefined);
});

test('이전 결과에도 실전 요약 폴백을 만든다', () => {
    const handler = createHandler();
    const summary = handler.buildPracticalSummaryFallback(
        { name: '테스트', relationship_status: 'single' },
        { section_1_1: '## #정리형탐색가\n\n본문' },
    );

    assert.equal(summary.type.label, '정리형 탐색가');
    assert.equal(summary.chart.length, 5);
    assert.equal(summary.actions.length, 3);
    assert.match(summary.social_profile.share_text, /#나의결/);
});

test('페이지 제목과 같은 본문 첫 제목은 한 번만 표시한다', () => {
    const handler = createHandler();

    const cleaned = handler.stripDuplicatePageHeading(
        '## 건강과 소진 신호\n\n첫 문단입니다.',
        '건강과 소진 신호',
    );

    assert.equal(cleaned, '첫 문단입니다.');
    assert.equal(
        handler.stripDuplicatePageHeading('## 다른 제목\n\n본문', '페이지 제목'),
        '## 다른 제목\n\n본문',
    );
});

test('내용이 없는 근거 레이블은 렌더링하지 않는다', () => {
    const handler = createHandler();

    assert.equal(handler.isEmptyReasonLine('> **사주에서 본 이유**:'), true);
    assert.equal(handler.isEmptyReasonLine('> **입력 정보에서 본 이유**:   '), true);
    assert.equal(
        handler.isEmptyReasonLine('> **사주에서 본 이유**: 실제 계산 근거가 있습니다.'),
        false,
    );
});

test('몰입형 소제목과 강조된 선택 기준은 본문 정리 후에도 유지된다', () => {
    const handler = createHandler();
    const copy = '### 인연의 이름보다, 이어지는 행동을 보세요\n\n궁금한 사람이 있다면 행동을 살펴보세요.\n\n**반가운 말 이후의 행동을 보세요.**';
    const cleaned = handler.removeStandaloneBasisSection(
        handler.stripDuplicatePageHeading(`## 좋은 인연\n\n${copy}`, '좋은 인연'),
    );
    assert.equal(cleaned, copy);
});

test('유료 상세 원고에서 별도 사주 근거 절을 제거한다', () => {
    const handler = createHandler();
    const cleaned = handler.removeStandaloneBasisSection(
        '### 사주 근거와 운의 해석\n\n전문 근거 설명입니다.\n\n### 한눈에 보는 핵심\n\n지금 내릴 판단입니다.',
    );

    assert.equal(cleaned.includes('사주 근거와 운의 해석'), false);
    assert.equal(cleaned.includes('전문 근거 설명입니다.'), false);
    assert.equal(cleaned.includes('지금 내릴 판단입니다.'), true);
});

test('결제 확인 값이 있을 때만 유료 접근을 허용한다', () => {
    const handler = createHandler();

    assert.equal(handler.resolvePremiumAccess({}), false);
    assert.equal(handler.resolvePremiumAccess({ access: { premium_unlocked: false } }), false);
    assert.equal(handler.resolvePremiumAccess({ access: { premium_unlocked: true } }), true);
    assert.equal(handler.resolvePremiumAccess({ access: { level: 'premium' } }), true);
});

test('CTA 클릭 시 unlockPremiumAccess가 유료 페이지를 열고 상태를 갱신한다', () => {
    const handler = createHandler();
    let switchedStep = null;
    handler.stepTabButtons = [];
    handler.switchStep = (step) => {
        switchedStep = step;
    };
    handler.analysisData = { access: { premium_unlocked: false } };

    handler.unlockPremiumAccess(2);

    assert.equal(handler.premiumUnlocked, true);
    assert.equal(handler.analysisData.access.premium_unlocked, true);
    assert.equal(switchedStep, 2);
});
