# Personal OS API 계약

이 문서는 현재 프론트엔드와 `backend/app/main.py`가 공유하는 최소 API 계약입니다. 백엔드는 설정에 따라 Gemini API 또는 외부 전송 없는 로컬 템플릿을 사용합니다.

## 공통 원칙

- 운영 환경에서는 HTTPS를 사용합니다.
- API 키, 생년월일, 태어난 시간, 이름을 URL 또는 애플리케이션 로그에 기록하지 않습니다.
- 작업 ID와 별도의 256비트 조회 토큰을 사용합니다. 토큰은 URL·로그에 넣지 않고 Authorization 헤더로 전달합니다. 서버에는 토큰의 SHA-256 해시만 보관합니다.
- 현재는 단일 프로세스의 제한된 백그라운드 작업을 사용합니다. 다중 워커·복제 배포에는 공유 작업 저장소·할당량이 필요합니다.
- 오류 응답은 JSON 직렬화 가능한 값만 포함합니다.

## `GET /api/v1/health`

성공 응답 예시:

```json
{
  "status": "healthy",
  "mode": "gemini",
  "durable_tasks": false,
  "ai_configured": true,
  "email_enabled": true,
  "email_configured": true
}
```

`status`는 최소한 `healthy` 또는 `degraded` 중 하나입니다. `ai_configured`와 `email_configured`는 필요한 환경설정의 존재 여부이며 외부 서비스의 실시간 가용성까지 보장하지는 않습니다. API 키와 Gmail 앱 비밀번호 값은 응답에 포함하지 않습니다.

## `POST /api/v1/create-saju-book`

요청 예시:

```json
{
  "name": "사용자",
  "birth_date": "1990-05-15",
  "birth_time": "14:30",
  "birth_time_unknown": false,
  "gender": "male",
  "relationship_status": "single",
  "mbti": "INFP",
  "calendar_type": "solar",
  "is_leap_month": false,
  "processing_consent": true,
  "privacy_policy_version": "2026-09-07",
  "email_notification_consent": false
}
```

`calendar_type=lunar`이면 입력 날짜를 음력으로 해석합니다. 윤달 출생자는 `is_leap_month=true`를 함께 보내야 합니다. 출생 시간을 모르면 `birth_time_unknown=true`로 보내며 결과의 시주는 제외됩니다.

권장 응답은 HTTP `202 Accepted`와 작업 ID입니다.

```json
{
  "task_id": "opaque-task-id",
  "access_token": "43-character-base64url-secret-returned-once",
  "status": "queued"
}
```

생성 응답은 `202`이며 토큰은 이때 한 번만 발급됩니다. 개인정보 처리 동의는 boolean `true`와 현재 안내 버전이 필수입니다. 선택 메일 동의 기본값은 false이며 동의하지 않아도 분석할 수 있습니다.

본문은 `application/json`만 허용하고 실제 수신 크기가 기본 16 KiB를 넘으면 `413`을 반환합니다. 기본 제한은 IP당 10분에 5건, 프로세스 전체 동시 3건, 저장 200건, 최근 24시간 생성 100건입니다. 초과 시 `429`와 `Retry-After`를 반환합니다. 한 작업은 최대 600초 동안 처리합니다.

## `GET /api/v1/progress?task_id=...`

`Authorization: Bearer <access_token>`이 필수입니다. 토큰 누락·오류·다른 작업의 토큰·만료는 모두 `404`로 응답합니다. 응답에는 토큰, 해시, 동의 기록을 포함하지 않으며 `Cache-Control: no-store`를 적용합니다.

진행 중 응답 예시:

```json
{
  "task_id": "opaque-task-id",
  "status": "processing",
  "percent_overall": 42
}
```

완료 응답 예시:

```json
{
  "task_id": "opaque-task-id",
  "status": "completed",
  "email_notification": "sent",
  "analysis_result": {
    "task_id": "opaque-task-id",
    "user_data": {
      "name": "사용자"
    },
    "generation_mode": "gemini_book",
    "model": "gemini-3.6-flash",
    "requested_model": "gemini-3.6-flash",
    "models_used": ["gemini-3.6-flash"],
    "saju_profile": {
      "calculation_standard": "출생지 대한민국·한국표준시, 절기 기준 동아시아 만세력",
      "day_master": { "gan": "庚", "element": "금", "label": "경금 일간" },
      "pillars": [
        { "label": "연주", "gan_zhi": "庚午" },
        { "label": "월주", "gan_zhi": "辛巳" },
        { "label": "일주", "gan_zhi": "庚辰" },
        { "label": "시주", "gan_zhi": "癸未" }
      ],
      "element_counts": { "목": 0, "화": 2, "토": 2, "금": 3, "수": 1 },
      "luck": {
        "current_decade": { "gan_zhi": "甲申", "start_year": 2017, "end_year": 2026 },
        "current_year": { "year": 2026, "gan_zhi": "丙午", "stem_ten_god": "편관" }
      }
    },
    "table_of_contents": {
      "chapters": [
        {
          "chapter": 1,
          "title": "명식과 기질",
          "sections": [
            { "id": "section_1_1", "title": "나의 일간과 네 기둥" }
          ]
        }
      ]
    },
    "section_1_1": "분석 본문"
  }
}
```

지원 상태 값:

- 진행: `queued`, `processing`
- 완료: `completed`, `completed_with_errors`
- 실패: `failed`, `error`

`completed_with_errors`는 현재 Gemini 호출 실패 후 로컬 예시 결과를 대신 반환했을 때 사용합니다. 이 경우 `analysis_result.generation_mode`은 `local_fallback`이며 사용자에게 표시할 원인을 `warnings` 배열로 제공합니다.

이메일 알림 상태는 `queued`, `sent`, `failed`, `disabled`, `misconfigured`, `not_consented` 중 하나입니다. 메일 전송 실패는 분석 작업을 실패시키지 않습니다. `email_notification_consent=false`이면 Gmail 설정이 활성화되어 있어도 메일을 보내지 않습니다.

## 오류 응답

```json
{
  "error": "Validation Error",
  "detail": [
    {
      "loc": ["body", "birth_date"],
      "msg": "올바른 날짜를 입력해주세요."
    }
  ]
}
```

- 입력 오류: HTTP `422`
- 존재하지 않거나 만료된 작업: HTTP `404` 또는 `410`
- 요청 제한: HTTP `429`와 `Retry-After`
- 서버 오류: HTTP `5xx`; 내부 예외·키·스택 추적은 응답에 포함하지 않습니다.


## `DELETE /api/v1/tasks/{task_id}`

조회와 같은 Authorization 헤더를 검증하고 메모리 사본과 실행 중인 작업을 제거/취소합니다. 성공 `204`, 권한 없음·이미 만료됨 `404`입니다. 이미 외부 AI에 전송한 요청이나 이미 보낸 메일은 되돌릴 수 없습니다. 새 이메일에는 작업 번호만 들어갑니다.

생성 후 24시간이 지나면 조회할 수 없고 만료 데이터는 60초 주기의 정리 작업으로 제거합니다. 브라우저는 기본적으로 탭 세션에 토큰을 저장하며 기록 저장 선택 시에만 로컬 저장소를 사용합니다. 토큰의 사용 기간은 최대 24시간이며 원본 조회 링크 공유는 지원하지 않습니다.
