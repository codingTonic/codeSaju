import assert from 'node:assert/strict';
import test from 'node:test';

import { buildSajuPayload } from '../frontend/assets/js/input.js';

const baseValues = {
  name: '테스트 사용자',
  birth_date: '1992-04-20',
  birth_time: '11:40',
  gender: 'female',
  relationship_status: 'single',
  calendar_type: 'solar',
  mbti: 'infp',
};

test('한 화면의 기본 입력값을 사주 API 형식으로 변환한다', () => {
  const payload = buildSajuPayload(baseValues, { emailNotificationConsent: true });

  assert.deepEqual(payload, {
    name: '테스트 사용자',
    birth_date: '1992-04-20',
    birth_time: '11:40',
    gender: 'female',
    relationship_status: 'single',
    mbti: 'INFP',
    calendar_type: 'solar',
    is_leap_month: false,
    processing_consent: false,
    privacy_policy_version: '2026-09-07',
    email_notification_consent: true,
  });
});

test('출생 시간 모름을 선택하면 정오 기준값과 플래그를 보낸다', () => {
  const payload = buildSajuPayload(baseValues, { birthTimeUnknown: true });

  assert.equal(payload.birth_time, '12:00');
  assert.equal(payload.birth_time_unknown, true);
});

test('이메일 알림 동의 여부를 명시적으로 전송한다', () => {
  const payload = buildSajuPayload(baseValues);

  assert.equal(payload.email_notification_consent, false);
});

test('음력 윤달 선택을 명시적으로 전송한다', () => {
  const payload = buildSajuPayload(
    { ...baseValues, calendar_type: 'lunar' },
    { isLeapMonth: true },
  );

  assert.equal(payload.calendar_type, 'lunar');
  assert.equal(payload.is_leap_month, true);
});

test('직접 입력한 고민은 공백을 정리해 분석 요청에 포함한다', () => {
  const payload = buildSajuPayload({
    ...baseValues,
    focus_concern: '  이직과 커리어 전환  ',
  });

  assert.equal(payload.focus_concern, '이직과 커리어 전환');
});

test('고민을 입력하지 않으면 불필요한 필드를 보내지 않는다', () => {
  const payload = buildSajuPayload({ ...baseValues, focus_concern: '   ' });

  assert.equal('focus_concern' in payload, false);
});

test('솔로 사용자의 숨겨진 연인 입력값은 전송하지 않는다', () => {
  const payload = buildSajuPayload({
    ...baseValues,
    partner_name: '남아 있는 값',
    partner_birth_date: '1993-01-01',
  });

  assert.equal('partner_name' in payload, false);
  assert.equal('partner_birth_date' in payload, false);
});

test('연애 중 사용자가 입력한 연인 정보를 함께 전송한다', () => {
  const payload = buildSajuPayload({
    ...baseValues,
    relationship_status: 'dating',
    partner_name: '연인',
    partner_birth_date: '1993-01-01',
    partner_birth_time: '08:10',
    partner_gender: 'male',
    partner_mbti: 'entj',
    partner_calendar_type: 'lunar',
  }, { partnerIsLeapMonth: true });

  assert.equal(payload.partner_name, '연인');
  assert.equal(payload.partner_birth_time, '08:10');
  assert.equal(payload.partner_mbti, 'ENTJ');
  assert.equal(payload.partner_calendar_type, 'lunar');
  assert.equal(payload.partner_is_leap_month, true);
});
