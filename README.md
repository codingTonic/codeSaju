# 여울 — 내 삶의 흐름을 읽는 사주

지금 궁금한 질문에서 시작해, 나의 기질과 삶의 흐름을 충분히 읽고 이어서 대화하는 사주 서비스입니다. 설문과 실제 앱 리뷰를 조사해 제품 방향을 정하고, 브랜드·첫 화면·입력·풀이·보관 경험을 새로 만들었습니다.

## 2026-09-29 적용: 무료 원국과 프리미엄 준비

현재 첫 이용 흐름은 **무료 원국 확인 → 프리미엄 리포트 준비 안내**입니다. 도메인과 결제·콘텐츠 계정이 없는 개발 환경으로 구현했습니다.

- `/app/#start`: 회원가입 없이 양력·음력·윤달·시간 미상으로 원국, 오행 글자 수, 십성·지장간을 확인합니다. Gemini 호출이나 출생 정보 저장은 없습니다.
- `/guides/`: 2026년 신년운세, 사주 궁합, 이직운, 을목일간, 재회운의 공개 안내 5편. 도메인 미설정 상태에서는 `noindex`이며 sitemap에 가짜 URL을 넣지 않습니다.
- `npm run build:seo`: 공개 도메인 `SITE_URL`을 사용해 canonical·OG·JSON-LD·robots·sitemap을 재생성합니다. [SEO 운영 안내](docs/seo-implementation.md)를 참고하세요.
- `npm run content:draft`: 30개 키워드 후보·블로그 초안 3편·스레드 문구 10개를 날짜별로 준비합니다. 기본 실행은 외부 API 호출 없이 편집 템플릿을 생성합니다. 실제 신규 AI 집필은 명시적인 `--ai` 옵션이며 자동 발행은 하지 않습니다. [콘텐츠 도구](docs/growth/README.md)
- 결제는 **테스트 전용** 주문·서버 승인·웹훅 검증까지 구현했습니다. 실제 과금과 유료 권한 발급, 2만 자 PDF 자동 생성, 카카오톡 발송은 제공하지 않습니다. [결제 준비 상태](docs/commerce.md)
- 용신·신살은 미지원입니다. 한국 음력 전체 대조, 역사적 시차·진태양시, 기존 상세 풀이 엔진의 절기 기준 통일은 추가 검증이 필요합니다. [계산 기준](docs/engine-calculation.md)

상세 풀이의 로컬 개발 기능은 `ALLOW_FREE_DEVELOPMENT_READINGS=true`일 때만 사용할 수 있습니다. 운영 환경에서는 이 플래그로 유료 풀이를 우회할 수 없습니다. 기존 생성 코드와 전체 예시는 보존했습니다. 아래의 상세 풀이 설명은 이 개발 기능에 해당합니다.

## 실행

등록된 키와 모델은 기존 `backend/.env`에서 읽습니다. 새 여울의 생성은 **Gemini 전용**이며, 오류가 나면 짧은 예시로 대체하지 않습니다. `AI_PROVIDER`와 `LOCAL_FALLBACK_ON_AI_ERROR`는 구버전 API에만 적용됩니다. 여울 경로는 이메일을 보내지 않습니다.

```bash
./start_servers.sh
```

기본 주소는 `http://127.0.0.1:3000/`이며, 포트가 사용 중이면 실행 로그에 새 주소를 출력합니다. 파일을 더블클릭하지 말고 서버 주소로 접속하세요. 예시는 API 없이도 읽을 수 있습니다.

```bash
# 포트를 직접 지정할 때
FRONTEND_PORT=3766 BACKEND_PORT=8766 ./start_servers.sh
```

Python 환경이 없는 경우 다음과 같이 준비합니다. 프런트엔드는 별도 런타임 패키지 없이 동작합니다.

```bash
python3 -m venv .venv-security
.venv-security/bin/python -m pip install --require-hashes -r requirements-dev.txt
```

## 새로 만든 경험

- **질문 중심 입력:** 나 자신 / 일과 진로 / 연애와 관계 / 돈과 생활 / 올해의 흐름. 개인 질문은 선택 입력이며 최대 600자입니다.
- **출생 정보:** 양력·음력·윤달, 시간 미상, 출생 시 성별을 반영합니다. 대한민국 표준시를 사용하며 진태양시·역사적 시차는 보정하지 않습니다. Gemini의 이용 조건에 따라 만 18세 이상으로 제한합니다.
- **8개 장의 전체 풀이:** 기질, 일, 돈, 연애, 인간관계, 올해, 세 달, 나의 질문. 각 장은 본문 700자 이상, 질문 장은 1,000자 이상이어야 통과합니다. 문단 길이·중복·사실 근거 번호·절기 경계를 검사합니다.
- **읽기와 대화:** 나의 질문을 먼저 읽고, 핵심 문장·본문·명식 근거·돌아볼 질문·작은 시도를 확인합니다. 같은 명식과 풀이를 바탕으로 최대 5번 이어서 물어볼 수 있습니다.
- **내 서랍:** 문장 표시, 개인 메모, 글자 크기와 야간 읽기, 전체 텍스트 다운로드, 인쇄/PDF 저장, 선택적 30일 기기 보관과 삭제를 제공합니다.
- **실제 공개 예시:** 가상 인물의 정보를 실제 Gemini로 생성한 8개 장의 전체 결과입니다. 예시임을 표시하고 대화 생성은 제공하지 않습니다.

무료 원국에는 결제가 없습니다. 프리미엄 판매는 준비 중이며, 기존 상세 풀이는 명시적으로 켠 로컬 개발 기능과 공개 예시로만 확인할 수 있습니다.

## 코드 구조

```text
frontend/app/                 새 여울 앱 (HTML/CSS/ES modules)
  index.html                 홈, 입력, 개인정보 안내
  main.js                    화면 전환, API 흐름, 읽기와 대화
  domain.js                  입력 검증, 보관 기한, 안전한 출력과 내보내기
  example.json               가상 인물의 실제 Gemini 풀이
backend/app/yeoul.py          새 입력 모델, 사실 묶음, 집필과 품질 검증
backend/app/yeoul_routes.py   /api/v2 생성·대화 API
backend/app/saju.py           검증된 절기·만세력 계산 엔진
backend/app/security.py       기존 조회 권한·요청 한도·본문 크기 제한
frontend/pages/, assets/     구버전 호환 화면과 공통 API 클라이언트
```

기존 계산 엔진과 보안 장치를 재사용하고, 새 제품은 독립된 `/app/`과 `/api/v2/`로 연결했습니다. 기본 `/`는 새 앱으로 이동합니다. 구버전 결과 주소는 기존 호환 화면에서 열립니다. production에서는 구버전 생성 API를 차단해 새 동의·연령·처리 조건을 우회할 수 없게 했습니다. 구버전 설명은 `docs/legacy/README-before-yeoul.md`에 보관했습니다.

## API와 개인정보

| 메서드 | 주소 | 동작 |
| --- | --- | --- |
| POST | `/api/v2/chart` | 개인정보를 보관하지 않는 무료 원국 계산 |
| GET | `/api/v2/commerce/config` | 결제 준비 상태 확인 |
| POST | `/api/v2/readings` | 동의와 성인 여부를 검증하고 작업 ID·조회 토큰 반환 |
| GET | `/api/v1/progress?task_id=...` | Bearer 토큰으로 진행률·결과 조회 |
| POST | `/api/v2/readings/{task_id}/questions` | Bearer 토큰으로 같은 풀이에 후속 질문 |
| DELETE | `/api/v1/tasks/{task_id}` | Bearer 토큰으로 입력·결과·실행 중 작업 삭제 |

원래 출생 날짜·시각을 계산한 후, Gemini에는 별명·질문·관계 상태와 명식 및 운의 계산값을 보냅니다. `store:false`로 요청하며 조회 토큰과 API 키는 주소에 넣지 않습니다. 모델 출력은 HTML로 해석하지 않고 이스케이프합니다.

서버 작업은 **단일 프로세스 메모리에 최대 24시간** 보관합니다. 재시작 시 사라지므로 대화도 종료될 수 있습니다. 조회 토큰은 탭 세션에만 남고, 직접 선택한 풀이·메모만 브라우저에 최대 12개·30일 보관합니다. 기기 보관은 계정 동기화가 아닙니다.

## 공개 운영 전 필요한 설정

현재 구현은 로컬에서 사용할 수 있는 완성된 개발 버전입니다. 인터넷에 배포한 상태가 아닙니다.

- `APP_ENV=production`에는 명시적인 `ALLOWED_HOSTS`, HTTPS `CORS_ORIGINS`, TLS 프록시가 필요합니다. 개발 서버로는 공개하지 않습니다.
- Google의 무료 API 약관은 개인정보 전송을 허용하지 않습니다. 실제 이용자에게 공개하기 전 활성 결제 계정이 연결된 API 프로젝트인지 확인하고 `GEMINI_PAID_SERVICE_CONFIRMED=true`를 설정해야 합니다. 미확인 상태의 production 생성 요청은 503으로 차단합니다. 이 설정은 결제를 활성화하거나 구매하는 기능이 아닙니다. [Gemini 공식 약관](https://ai.google.dev/gemini-api/terms)
- 프로세스 1개·워커 1개로 운영해야 합니다. 다중 인스턴스나 재시작 후 이어 읽기가 필요하면 공유 작업 큐·할당량 저장소·암호화된 결과 DB를 연결해야 합니다. 상세 풀이에는 계정·영속 DB가 없습니다. 테스트 결제 주문만 별도 SQLite로 보관합니다.
- 생성 및 후속 질문은 각각 IP당 기본 10분에 5회, 전체 일일 요청은 100회, 동시 작업은 3개로 제한합니다. 실패·취소도 비용 한도에 포함됩니다. 프록시 환경에서는 실제 클라이언트 IP를 신뢰할 수 있는 경로에서만 전달해야 합니다.
- 운영자 정보와 문의 수단은 실제 서비스 운영 주체를 정한 뒤 개인정보 안내에 반영해야 합니다.

## 검증

```bash
npm run check
npm test
AI_PROVIDER=local_template EMAIL_NOTIFICATIONS_ENABLED=false .venv-security/bin/python -m pytest -q
```

Python 테스트에서는 Gemini를 모킹하므로 실제 API 비용이 발생하지 않습니다. 새 앱 테스트는 `tests/test_yeoul.py`와 `tests/yeoul.test.js`에 있습니다. 실제 가상 인물 생성·후속 대화·반응형 검증 결과는 `docs/rebuild/verification.md`를 참고하세요.

## 근거와 백업

- 조사 및 제품 결정: `docs/rebuild/research-and-product.md`
- 디자인 시스템: `design-system/yeoul/MASTER.md`
- 기존 보안 개선: `docs/security-improvements-2026-09-07.md`
- 변경 전 백업: `backups/20260908-131113-before-rebuild/` (복원 안내·파일별 해시 포함)

백업에는 기존 환경 설정이 포함되어 있으므로 공개하거나 업로드하지 마세요. 등록된 `.env`와 Gemini 키는 변경하지 않았습니다.
