# 여울 공개 가이드와 SEO 빌드

2026-09-29 적용. 실제 배포 도메인과 Search Console 계정은 제공되지 않았으므로 공개 배포·소유권 확인·사이트맵 제출·색인 요청을 실행하지 않았다. 검색 순위와 색인 채택은 보장하지 않는다.

## 공개 URL 구조

| URL | 내용 |
| --- | --- |
| `/app/` | 여울 랜딩·출생 정보 입력 |
| `/guides/` | 사주 읽는 법 목록 |
| `/guides/2026-new-year/` | 2026년 신년운세와 원국·절기 기준 |
| `/guides/compatibility/` | 사주 궁합과 실제 관계의 대화 |
| `/guides/career-change/` | 이직운과 현실의 직무·제안 비교 |
| `/guides/eulmok/` | 을목일간의 뜻과 비유의 한계 |
| `/guides/reunion/` | 재회운, 상대의 의사와 연락의 경계 |

본문은 `content/guides.json`에서 생성한다. 다섯 글은 별개의 질문에 답하고 서로 관련 글을 연결한다. 실제 검색량·CPC 데이터를 확보하지 않았으므로 “고단가”나 “검색량 상위”라고 표시하지 않았다. 저자 표시는 실제 서비스명인 여울이며 AI 도움으로 작성했음을 표시한다. 전문가 검수, 경력, 후기, 별점, 성공률을 만들어 넣지 않는다. 궁합 가이드는 현재 앱에 두 명식 비교 기능이 없다는 점도 명시한다.

## 빌드

```bash
# 로컬 기본값: 모든 페이지 noindex, robots Disallow /, 빈 sitemap
python3 scripts/build_seo.py --include-app

# 실제 운영 도메인을 환경변수에 설정한 뒤 실행
python3 scripts/build_seo.py --site-url "$SITE_URL" --include-app
```

`SITE_URL`은 실제 HTTPS 도메인 원점만 허용한다. HTTP, IP, localhost, `.test`·`.local` 등 예약 이름, example.com 계열 예시 도메인, 인증 정보, 경로, 쿼리, 프래그먼트, 비표준 포트를 거절한다. DNS 소유권·TLS·외부 접근 가능 여부를 이 빌드가 검증하는 것은 아니다. 실제 공개 호스트에서 별도 확인해야 한다.

`--include-app`은 `frontend/app/index.html`의 `<!-- SEO:START -->`부터 `<!-- SEO:END -->` 사이만 교체한다. 기존 title과 description을 읽어 동일한 OG·WebPage 데이터를 생성한다. 마커가 없으면 오류로 종료한다. 앱 편집과 병렬 작업할 때에는 옵션을 생략할 수 있지만, 배포 빌드에는 반드시 포함한다. 사이트맵에 `/app/`이 없으면 앱을 같은 도메인으로 빌드하지 않은 상태다.

실제 도메인이 없으면 canonical·og:url·URL 기반 JSON-LD를 꾸며 넣지 않는다. 도메인을 설정하면 각 글에 Article JSON-LD, 가이드 목록과 앱에 WebPage JSON-LD를 정적 HTML로 넣는다. OG 제목·설명은 실제 본문과 일치한다. Article의 수정일은 원본 데이터의 실제 수정일이며 빌드 실행일로 자동 갱신하지 않는다. 공개 전 내용과 날짜를 검토하고, 수정할 때 데이터의 updated도 변경한다.

## 서버와 배포 조건

- `serve_frontend.py`는 `/`, `/index.html`, `/app/index.html`을 `/app/`으로 한 번에 301 이동한다. `/guides/.../index.html`도 디렉터리 canonical로 이동한다. query는 옮기지 않는다.
- 운영 빌드 manifest의 공개 경로만 검색 허용한다. 쿼리가 있는 요청, 구버전 결과 HTML 등 다른 주소에는 `X-Robots-Tag: noindex, nofollow`를 보낸다. 운영 번들을 localhost나 다른 preview 호스트에서 열어도 noindex 헤더를 보낸다.
- 파일·디렉터리 보호는 GET과 HEAD에 함께 적용한다. 디렉터리 목록과 숨김 파일, 프런트엔드 밖을 향한 심볼릭 링크는 차단한다.
- JSON-LD의 실제 문자열에 대한 SHA-256 CSP 해시만 `script-src`에 추가한다. 실행 가능한 inline JavaScript 허용을 위해 `unsafe-inline`을 추가하지 않는다.
- `frontend/seo-manifest.json`에는 공개 경로와 페이지별 JSON-LD CSP 해시가 있다. 정적 호스팅이나 운영 프록시를 사용할 경우 같은 redirect·noindex·CSP 정책을 해당 플랫폼 설정으로 옮겨야 한다. 이 개발 서버를 그대로 공개 운영하는 것을 전제로 하지 않는다.
- `robots.txt`는 접근 제어가 아니다. 개인 결과와 다운로드는 기존 Bearer 조회 권한으로 계속 보호해야 한다. 사이트맵에는 API·결과·다운로드·결제·초안 주소를 넣지 않는다.

정적 호스트에서는 디렉터리 URL이 실제 200 응답으로 `index.html`을 제공해야 한다. 알 수 없는 URL에 앱 HTML을 무조건 200으로 돌려주는 SPA fallback을 공개 가이드 경로에 사용하지 않는다. CSP가 별도 프록시에도 있다면 두 정책을 모두 만족하도록 manifest 해시를 반영한다. `og:image`의 공개 이미지도 접근을 허용한다.

## 검증과 공개 후 확인

```bash
.venv-security/bin/python -m pytest -q tests/test_seo.py
```

검증은 도메인 유효성, 미설정 noindex, 공개 페이지 전용 sitemap, JS 없이 본문·링크 발견, JSON-LD와 본문 일치, 스크립트 이스케이프, 빌드 반복성, 실제 HTTP canonical 이동, CSP, GET/HEAD 파일 보호를 포함한다. 임시 디렉터리에서 운영 빌드를 테스트하며 실제 저장소에는 예시 운영 도메인을 남기지 않는다.

실제 도메인과 계정 연결 뒤 진행할 순서:

1. HTTPS에서 `/app/`·가이드 5개·`/robots.txt`·`/sitemap.xml`의 200 응답, canonical, robots 헤더를 확인한다.
2. Search Console에서 해당 도메인의 소유권을 확인한다. Domain 속성은 DNS TXT 값 설정이 필요할 수 있다. 사용자 인증·DNS 관리자 권한 없이는 확인 완료를 대신할 수 없다.
3. 실제 운영 도메인의 `/sitemap.xml`을 사이트맵 메뉴에 제출한다.
4. `/app/`과 가이드 5개를 URL 검사로 확인하고 가능한 경우 색인 생성 요청을 제출한다. 소유권, 제출, 색인 채택을 서로 구분해 기록한다.
5. 페이지 색인 보고서에서 제출 URL과 Google 선택 canonical을 확인한다. 검색 실적이 쌓이면 노출·클릭·검색어로 다음 콘텐츠를 결정한다. 요청만으로 즉시 수집되거나 순위가 오르지는 않는다.

## 적용 근거

사용자가 지정한 [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo)의 실제 지침을 원격으로 읽어 적용했다. 전역 설치나 외부 스크립트 실행은 하지 않았다.

- [SEO 허브 SKILL.md](https://github.com/AgriciDaniel/claude-seo/blob/main/skills/seo/SKILL.md): 관련 개별 지침을 선택해 적용.
- [technical SKILL.md](https://github.com/AgriciDaniel/claude-seo/blob/main/skills/seo-technical/SKILL.md): 정적 본문, 짧은 발견 경로, canonical과 indexability 점검.
- [schema SKILL.md](https://github.com/AgriciDaniel/claude-seo/blob/main/skills/seo-schema/SKILL.md): 실제 내용만 표현하는 JSON-LD, 가짜 후기 제외.
- [sitemap SKILL.md](https://github.com/AgriciDaniel/claude-seo/blob/main/skills/seo-sitemap/SKILL.md): 공개 canonical·200 응답 URL만 수록하고 실제 수정일 유지.
- [Google 구조화 데이터 지침](https://developers.google.com/search/docs/appearance/structured-data/sd-policies): 사용자에게 보이는 본문과 일치하는 구조화 데이터.
- [Google 스팸 정책](https://developers.google.com/search/docs/essentials/spam-policies): 검색 순위 조작을 위한 대량 저가치 콘텐츠와 키워드 반복을 피하고 독자에게 유용한 내용을 제공.

라이브 도메인이 없어 Search Console, Rich Results Test와 현장 Core Web Vitals 측정은 아직 수행하지 않았다. 로컬 테스트 통과는 외부 검색엔진의 수집·색인·순위 확인을 대신하지 않는다.
