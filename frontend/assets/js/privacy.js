// Shared exports contain only aggregate counts and fixed, reviewed copy.
// Never attempt to anonymize arbitrary generated prose by string replacement.
const ELEMENTS = ['목', '화', '토', '금', '수'];
const DESCRIPTIONS = {
    목: '성장과 확장의 상징', 화: '표현과 활력의 상징', 토: '안정과 조율의 상징',
    금: '기준과 정돈의 상징', 수: '관찰과 유연함의 상징',
};

export function buildAnonymousProfile(analysis) {
    const raw = analysis?.saju_profile?.element_counts || {};
    const valid = ELEMENTS.every((key) => Number.isInteger(raw[key]) && raw[key] >= 0 && raw[key] <= 8)
        && [6, 8].includes(ELEMENTS.reduce((sum, key) => sum + raw[key], 0));
    const chart = valid ? ELEMENTS.map((key) => ({ label: key, value: raw[key] })) : [];
    const strongest = chart.reduce((best, item) => !best || item.value > best.value ? item : best, null);
    const label = strongest ? `${strongest.label} · ${DESCRIPTIONS[strongest.label]}` : '나의 결 프로필';
    const summary = chart.length ? chart.map((item) => `${item.label} ${item.value}`).join(' · ') : '오행 요약을 표시할 수 없습니다.';
    return {
        label, summary, chart,
        shareText: `나의 결 | ${label}\n${summary}\n#나의결 #자기이해`,
    };
}

export function buildAnonymousReportHtml(analysis) {
    const profile = buildAnonymousProfile(analysis);
    // All interpolated values originate from finite numeric validation or static copy above.
    return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>나의 결 · 익명 요약</title>
<style>body{max-width:42rem;margin:4rem auto;padding:1.5rem;background:#f8f5ed;color:#19231f;font-family:system-ui,sans-serif;line-height:1.8}h1{color:#123b31}li{margin:.5rem 0}</style></head>
<body><main><p>나의 결 · 익명 공유용 요약</p><h1>${profile.label}</h1><p>${profile.summary}</p>
<ul>${profile.chart.map((item) => `<li>${item.label}: ${item.value}개</li>`).join('')}</ul>
<p>공유본에는 오행의 합계와 고정 설명만 포함됩니다. 이름, 출생 정보, 고민, 연인 정보, 리포트 본문은 포함하지 않습니다.</p>
<p>전통 상징을 활용한 자기이해 참고 자료입니다.</p></main></body></html>`;
}
