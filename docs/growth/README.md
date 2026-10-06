# 검색·스레드 콘텐츠 초안 파이프라인

`scripts/growth_pipeline.py`는 날짜별 검토 폴더에 롱테일 키워드 후보 **30개**, 블로그 초안 **3편**, 스레드 후킹 문장 **10개**를 만든다. 기본 실행은 로컬 편집 템플릿을 사용하므로 네트워크 요청이나 AI 비용이 없다. 블로그 업로드, 스레드 게시·댓글 전송, 광고 집행 기능은 실행하지 않는다.

## 바로 실행하기

프로젝트 루트에서 실행한다. 날짜를 생략하면 `Asia/Seoul` 기준 오늘 날짜를 사용한다.

```sh
.venv-security/bin/python scripts/growth_pipeline.py --date 2026-09-29
```

기본 출력 폴더는 `content/drafts/2026-09-29/`다.

| 파일 | 내용 |
| --- | --- |
| `keywords.csv` | 키워드 후보 30개, 주제, 검색량과 출처가 있다면 해당 값 |
| `01-eulmok.md` | 을목일간 특징 초안과 무료 원국 CTA |
| `02-reunion.md` | 재회운 보는 법 초안과 무료 원국 CTA |
| `03-wealth.md` | ‘올해 대박 나는 띠’ 주제를 신중하게 풀어낸 초안과 무료 원국 CTA |
| `threads.json` | 후킹 문장 10개, 게시물 ID 자리, 검토용 댓글 문구와 CTA 주소 |
| `manifest.json` | 생성 방식, 사이트 설정 여부, 가져온 검색량 개수, 중복 검사와 검토 상태 |

10개의 후킹 문장은 `threads.json`의 `hook`에서 확인한다. 조회수나 재회·수익을 보장하지 않으며, 가짜 경험담이나 공포를 이용한 구매 압박 문구를 만들지 않는다.

## 템플릿과 AI 초안의 차이

기본 `editorial_template` 모드는 검토 가능한 예시 콘텐츠를 만든다. 템플릿 본문은 날짜마다 새로 쓰이지 않으므로 다음 날짜에 같은 내용이 나오면 `duplicate_hold`로 표시한다. 이는 매일 세 편의 새로운 완성 글이 자동 발행된다는 뜻이 아니다.

새로운 AI 초안이 필요하면 `--ai`를 명시한다. 기존 Gemini 설정을 읽고 주제당 한 번, 총 세 번 API 요청을 보낸다. **API 비용이 발생할 수 있다.** 생성 결과는 계속 `review_required`이며 공개 발행되지 않는다.

```sh
.venv-security/bin/python scripts/growth_pipeline.py --date 2026-09-30 --ai
```

이미 그 날짜 폴더가 있으면 `--ai`를 추가해도 기존 파일을 덮어쓰거나 비용이 드는 호출을 하지 않는다. 같은 날짜의 새 버전을 검토하려면 `--output content/draft-revisions`처럼 별도 출력 위치를 지정한다. 기사 본문은 사실성·표현·출처·중복을 검토해야 한다. 문자열 구조 검사는 전문가 감수를 대신하지 않는다.

## 검색량 데이터 넣기

현재 30개는 세 주제에서 정리한 **편집용 후보**다. Google 검색량을 자동 수집하거나 인기 순위를 검증한 값이 아니다. 데이터가 없는 행의 `monthly_searches`는 비어 있고 `status`는 `unverified_candidate`다.

실제 키워드 도구에서 내보낸 자료를 다음 CSV 형태로 준비해 `--metrics`에 지정한다. 키워드는 현재 후보 문구와 정확히 일치해야 결합된다.

```csv
keyword,monthly_searches,source,measured_at
을목일간 성향 이해하기,120,실제 사용한 도구 또는 내보내기 출처,2026-09-28
재회운 보는 법과 한계,300,실제 사용한 도구 또는 내보내기 출처,2026-09-28
```

위 숫자는 **파일 형식을 설명하는 예시**다. 실제 검색량이라고 사용하지 않는다.

```sh
.venv-security/bin/python scripts/growth_pipeline.py --metrics /absolute/path/to/keyword-metrics.csv
```

필수 열·날짜·0 이상의 정수·비어 있지 않은 출처를 검사하며, 빈 키워드와 중복 키워드는 거부한다. `measured`와 `search_volume_verified`는 검사를 통과한 운영자 제공 자료의 수를 뜻하며, 파이프라인이 외부 검색량을 독립적으로 검증한 것은 아니다. 가져온 값은 후보 정렬에 반영되지만 글 주제는 세 그룹을 골고루 다루도록 선택된다.

## 도메인과 CTA

도메인이 없을 때는 `/app/` 상대 주소를 사용하고 `site_configured: false`로 표시한다. 외부 블로그나 스레드에 가져가기 전에 실제 배포 도메인을 지정하고 도착 페이지를 확인한다.

```sh
.venv-security/bin/python scripts/growth_pipeline.py --site-url https://your-owned-domain.example
```

이 도메인은 예시다. `SITE_URL` 환경 변수로도 지정할 수 있다. 경로·로그인 정보·쿼리·해시가 없는 올바른 HTTPS 출처만 허용한다. 블로그 CTA에는 `utm_source=blog`, 스레드에는 `utm_source=threads`가 붙는다. 모두 무료 원국으로 이동하며, 프리미엄은 준비 중임을 표시한다. 실제 결제가 연결되기 전 유료 리포트를 즉시 구매할 수 있는 것처럼 안내하지 않는다.

## 검토·반복 실행·오류 처리

- 같은 날짜 폴더는 그대로 반환한다. 사람이 고친 본문과 검토 상태를 보존한다.
- 기존 배치와 현재 배치에서 본문이 같으면 `duplicate_hold`로 표시한다. 단순 해시 비교이므로 표현만 바꾼 유사문서나 내용 오류를 모두 찾지는 못한다.
- 배치는 임시 폴더에서 완성한 뒤 날짜 폴더로 옮긴다. 생성 도중 실패하면 임시 폴더를 정리하고 일부 글만 있는 완성 배치를 남기지 않는다.
- 모든 배치의 `publish_enabled`는 `false`다. 검토 완료 표시만으로 게시 요청이 발생하지 않는다.

## 배포 스케줄러에 연결할 명령

현재 **cron·Codex 자동화·배포 스케줄러를 설치하거나 활성화하지 않았다.** 서버와 출력 저장소가 정해지면 운영하는 스케줄러의 매일 실행 작업에 다음 명령을 등록할 수 있다. 실행 시각은 스케줄러에서도 `Asia/Seoul`을 명시한다.

```sh
/absolute/path/to/project/.venv-security/bin/python /absolute/path/to/project/scripts/growth_pipeline.py --output /absolute/persistent/path/drafts
```

기본 명령은 로컬 초안만 만든다. AI 사용이 확정된 작업에만 `--ai`를 추가하고 비용 한도와 실패 알림을 설정한다. 같은 날짜의 겹치는 실행은 피하며 한 번만 실행하도록 스케줄러에서 동시 실행을 제한한다. 서버 재배포로 초안·검토 기록이 사라지지 않도록 출력 경로를 영속 저장소에 둔다.

## 공개 발행과 스레드 댓글의 후속 연결

연결된 블로그 계정·도메인·스레드 계정이 없어 공개 발행과 자동 댓글은 준비하지 않았다. `threads.json`의 `owned_post_id`는 모두 `null`이며 실제 반응 수나 게시물 ID를 만들지 않는다.

추후 댓글 기능은 **사용자가 운영하는 게시물**에 대해, 연결된 계정의 권한과 [공식 Threads API 문서](https://developers.facebook.com/docs/threads/)를 확인해 구현한다. 검토된 문구, 명시한 반응 기준, 이미 답글을 남겼는지 확인하는 영속 기록, 실패 재시도와 게시 한도를 함께 설계해야 한다. 타인 게시물에 무차별로 홍보 링크를 달거나 브라우저를 이용해 제한을 우회하는 방식은 이 파이프라인에 포함하지 않는다.

## 검증

```sh
.venv-security/bin/python -m pytest tests/test_growth_pipeline.py -q
```

네트워크 없는 기본 실행, 30/3/10 산출물, 편집 파일 보존, 날짜 간·같은 배치 안의 중복 보류, 잘못된 검색량, HTTPS CTA 검증, 실패 시 임시 파일 정리, AI 문자열의 HTML/Markdown 링크 이스케이프를 검증한다. 테스트의 AI 호출은 로컬 가짜 함수로 대체한다.
