import test from 'node:test';
import assert from 'node:assert/strict';
import { validateChart, chartHTML, chartIssues } from '../frontend/app/free-chart.js';

const valid = {birth_date:'2000-02-30', birth_time_unknown:true, processing_consent:true, age_confirmed:true};

test('free chart accepts lunar date shape while exact validation stays server-side', () => {
  assert.equal(validateChart(valid), '');
  assert.match(validateChart({...valid,birth_date:'00-02-30'}), /생년월일/);
  assert.match(validateChart({...valid,birth_time_unknown:false,birth_time:'25:00'}), /태어난 시간/);
  assert.match(validateChart({...valid,processing_consent:false}), /동의/);
});

function fixture() {
  return {
    profile: {
      day_master:{label:'갑목 일간',archetype:'<img src=x onerror=alert(1)>'},
      pillars:[{key:'year',gan_zhi_ko:'경진',gan_zhi:'庚辰',estimated:true,stem_ten_god:'편관',branch_main_ten_god:'편재',hidden_stems:[{stem:'戊',ten_god:'편재'}]}],
      uncertain_pillars:['year'],element_counts:{목:1,화:0,토:2,금:2,수:1},element_count_total:6,element_note:'보이는 글자 수',
    },
    method:{engine:'lunar-python',engine_version:'1.4.8',timezone:'UTC+9',day_boundary:'00시',limitations:['<script>bad()</script>']},
    yongshin:{reason:'지원하지 않아요'},shinsal:{reason:'지원하지 않아요'},
  };
}

test('chart explicitly marks missing time and estimated boundary columns', () => {
  const result = chartHTML(fixture());
  assert.match(result, /시간 미상/);
  assert.match(result, /태어난 해 \(연주\) · 추정/);
  assert.match(result, /낮 12시를 기준으로 예상한 값/);
  assert.match(result, /다섯 요소의 개수와 글자 사이의 관계도 태어난 시간에 따라/);
});

test('chart escapes all human-readable dynamic content', () => {
  const result = chartHTML(fixture());
  assert.ok(!result.includes('<img src=x'));
  assert.ok(!result.includes('<script>'));
  assert.ok(result.includes('&lt;script&gt;'));
});


test('free chart reports every missing field and excludes time when unknown', () => {
  assert.deepEqual(chartIssues({}).map(issue => issue.field), ['birth_date', 'birth_time', 'processing_consent', 'age_confirmed']);
  assert.deepEqual(chartIssues({...valid, processing_consent:false, age_confirmed:false}).map(issue => issue.field), ['processing_consent', 'age_confirmed']);
  assert.deepEqual(chartIssues(valid), []);
});
