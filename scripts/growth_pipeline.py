#!/usr/bin/env python3
"""Prepare a daily editorial batch. Never publishes, scrapes, or sends comments."""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date, datetime
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "eulmok": ("을목일간 특징", ["을목일간 성향 이해하기", "을목일간 인간관계", "을목일간 일하는 방식", "을목일간 연애 성향", "을목일간과 월지", "을목일간 오행 분포", "을목일간 십성 읽기", "을목일간 강점 돌아보기", "을목일간 사주 원국", "을목일간 해석 주의점"]),
    "reunion": ("재회운 보는 법", ["재회운 보는 법과 한계", "재회운과 상대방 마음", "재회운 연락 시기", "재회운 사주 궁합", "재회운 월운 보는 법", "재회운 관계 돌아보기", "재회운과 현실의 신호", "재회운 상담 전 질문", "재회운 생년월일 시간", "재회운 오해 바로잡기"]),
    "wealth": ("올해 대박 나는 띠", ["올해 대박 나는 띠 해석", "띠별 재물운 보는 법", "재물운과 재성의 차이", "올해 재물운 사주 원국", "재물운 월운 읽기", "띠별 운세의 한계", "재물운과 소비 습관", "재물운과 이직운", "재물운 사주 십성", "돈복 사주 오해"]),
}
HOOKS = [
    "새벽에 전 연인 계정을 열었다면, 재회운보다 먼저 적어볼 질문이 있어요.",
    "을목일간이라는 설명, 내 경험과 얼마나 맞을까요? 세 장면을 떠올려보세요.",
    "올해 돈복 터지는 띠? 같은 띠인데 삶이 다른 이유부터 읽어봐요.",
    "‘이직운이 좋다’는 말을 듣고도 망설이는 마음에는 이유가 있어요.",
    "궁합 점수보다 오래 남는 건, 서로 불편함을 말하는 방식일지도 몰라요.",
    "사주에 오행 하나가 없다고, 내게 그 능력이 없는 건 아니에요.",
    "태어난 시간을 몰라도 볼 수 있는 것, 조심해서 읽어야 할 것.",
    "누구에게나 맞는 사주 풀이처럼 느껴졌다면, 계산 근거를 확인해보세요.",
    "재회가 궁금할 때 상대의 마음을 추측하는 대신 확인할 수 있는 것들.",
    "내 사주 원국을 처음 펼칠 때, 여덟 글자를 전부 외울 필요는 없어요.",
]
SECTIONS = {
    "eulmok": [
        ("을목은 어디서 확인하나요?", "사주 원국의 일주에서 천간이 乙이면 을목일간이라고 부릅니다. 띠는 태어난 해의 지지이고 일간은 태어난 날의 천간이므로 서로 다른 항목입니다. 만세력에 입력한 양력·음력 구분과 윤달 여부를 먼저 확인한 다음 일주를 살펴보세요."),
        ("유연하다는 상징을 내 경험에 비춰보기", "전통 해석에서는 을목을 풀이나 덩굴 같은 상징으로 설명하기도 합니다. 이를 모든 사람에게 적용되는 성격 진단으로 받아들이기보다, 의견이 달랐던 회의나 관계에서 실제로 어떻게 반응했는지 떠올려보세요. 상대에게 맞췄던 때와 내 생각을 지켰던 때를 함께 적으면 한 가지 단어로 자신을 제한하지 않을 수 있습니다."),
        ("일간 하나로 해석을 끝내지 않기", "같은 을목일간이라도 월지와 다른 천간·지지, 십성의 배치가 다릅니다. 보이는 오행의 글자 수는 확인할 수 있지만, 적은 오행이 곧 부족한 능력을 뜻하지는 않습니다. 용신이나 신강·신약은 학파와 판단 기준이 필요한 영역이므로 단순 개수만으로 자동 확정하는 설명은 근거를 더 확인해야 합니다."),
        ("나에게 남길 질문", "최근 새로운 상황에 적응한 경험 하나와 적응하지 않기로 선택한 경험 하나를 적어보세요. 각각 어떤 정보와 여유가 있었는지 비교해보면 ‘유연하다’는 설명보다 구체적인 자기 이해가 됩니다. 사주는 그 질문을 여는 참고자료로 사용하고, 경험과 맞지 않는 해석은 받아들이지 않아도 괜찮습니다."),
    ],
    "reunion": [
        ("재회운이 알려줄 수 없는 것", "재회운은 상대방의 현재 마음이나 연락할 날짜를 확인하는 방법이 아닙니다. 한 사람의 출생 정보로 다른 사람의 의사나 미래 행동을 확정할 수는 없습니다. 보고 싶은 답을 찾기 전에, 내가 다시 만나고 싶은 이유와 이전 관계에서 달라져야 할 점을 구분해 적어보세요."),
        ("사주의 흐름과 관계의 사실을 구분하기", "전통 해석은 대운·세운·월운을 관계를 돌아보는 관점으로 활용합니다. 다만 같은 글자에 대한 해석도 원국과 계산 기준에 따라 달라질 수 있고, 실제 재회 여부를 증명하지 않습니다. 상대가 먼저 대화를 이어가는지, 약속을 지키는지처럼 관찰할 수 있는 사실은 운세 설명과 별도로 살펴보는 편이 좋습니다."),
        ("연락을 고민할 때 정리할 세 가지", "첫째, 마지막 대화에서 상대가 말한 경계를 떠올려보세요. 둘째, 내가 원하는 대화가 사과인지, 안부인지, 다시 만날 제안인지 하나로 정리해보세요. 셋째, 답이 없거나 거절했을 때 연락을 멈출 수 있는지 생각해보세요. 상대가 연락하지 말라고 했다면 그 의사를 존중하는 것이 먼저입니다."),
        ("궁합을 읽을 때의 질문", "궁합을 좋다거나 나쁘다는 점수로만 보면 실제 관계에서 조율할 수 있는 부분을 놓치기 쉽습니다. 갈등 때 대화 속도, 혼자 있는 시간, 연락 빈도처럼 서로 말로 합의할 수 있는 주제를 골라보세요. 상대방의 개인정보를 동의 없이 입력하는 대신 자신의 소통 습관부터 돌아볼 수도 있습니다."),
    ],
    "wealth": [
        ("같은 띠이면 같은 재물운일까요?", "띠는 태어난 해의 지지를 기준으로 묶는 넓은 분류입니다. 같은 띠라도 태어난 달·날·시간과 살아온 환경, 일과 지출 조건은 다릅니다. ‘올해 대박 나는 띠’라는 제목만으로 개인의 소득이나 행운을 예측할 수는 없습니다. 띠별 설명은 가볍게 읽고 자신의 상황을 살펴보는 질문으로 바꿔보세요."),
        ("재성은 수익 보장과 다릅니다", "십성의 재성은 일간과 다른 글자 사이의 관계를 나타내는 전통 분류입니다. 재성이 보인다는 사실과 돈을 많이 번다는 결론은 같은 말이 아닙니다. 원국의 특정 글자만으로 금액이나 확률을 계산할 수 없으며, 보이는 글자가 없다고 재능이나 가능성이 없다고 볼 수도 없습니다."),
        ("이직운과 돈의 흐름을 함께 볼 때", "일을 바꾸는 고민에는 급여뿐 아니라 업무 시간, 통근, 역할, 계약 조건과 성장 기회가 함께 있습니다. 운세 문장 하나로 결론을 내리기보다 현재와 제안받은 조건을 같은 항목으로 정리해보세요. 아직 확인되지 않은 항목은 추측으로 채우지 않고 질문으로 남겨두면 선택의 근거가 더 또렷해집니다."),
        ("오늘 남길 생활 기록", "최근 반복해서 나간 비용 중 만족한 것 하나와 아쉬웠던 것 하나를 적어보세요. 이 글은 특정 투자나 구매를 추천하지 않습니다. 지출의 크기만 평가하기보다 어떤 필요를 충족했는지 살펴보는 자기 관찰입니다. 운세를 읽고 불안해져 서둘러 돈을 쓰게 된다면 잠시 멈추고 실제 조건을 다시 확인하세요."),
    ],
}


def site_origin(value: str) -> str:
    if not value:
        return ""
    u = urlsplit(value)
    if u.scheme != "https" or not u.hostname or u.username is not None or u.password is not None or "?" in value or "#" in value or u.path not in ("", "/") or any(c.isspace() for c in value) or "\\" in value:
        raise ValueError("SITE_URL에는 경로나 인증정보 없는 HTTPS 도메인을 넣어주세요.")
    # urlsplit alone accepts malformed authorities and never validates ports.
    port = u.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("SITE_URL 포트가 올바르지 않습니다.")
    host = u.hostname.encode("idna").decode("ascii")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in host.split(".")):
            raise ValueError("SITE_URL 도메인이 올바르지 않습니다.")
    return value.rstrip("/")


def keyword_rows(metrics: Path | None = None) -> list[dict]:
    evidence = {}
    if metrics:
        with metrics.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {"keyword", "monthly_searches", "source", "measured_at"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError("검색량 CSV에는 keyword, monthly_searches, source, measured_at 열이 필요합니다.")
            for row in reader:
                keyword = (row.get("keyword") or "").strip()
                if not keyword or keyword in evidence or any(row.get(field) is None for field in required):
                    raise ValueError("검색량 CSV의 빈 키워드·중복 키워드·누락된 값을 확인해주세요.")
                volume = int(row["monthly_searches"])
                date.fromisoformat(row["measured_at"])
                if volume < 0 or not row.get("source", "").strip():
                    raise ValueError("검색량에는 0 이상의 값과 출처가 필요합니다.")
                evidence[keyword] = row
    rows = []
    for group, (_, keywords) in GROUPS.items():
        for keyword in keywords:
            m = evidence.get(keyword, {})
            rows.append(dict(keyword=keyword, topic=group, monthly_searches=m.get("monthly_searches", ""), source=m.get("source", "editorial_seed"), measured_at=m.get("measured_at", ""), status="measured" if m else "unverified_candidate"))
    return sorted(rows, key=lambda x: int(x["monthly_searches"] or -1), reverse=True)


def validate_article(value):
    if not isinstance(value, dict) or set(value) != {"title", "description", "sections"}:
        raise ValueError("Invalid article fields")
    if not isinstance(value["title"], str) or not 8 <= len(value["title"]) <= 100:
        raise ValueError("Invalid title")
    if not isinstance(value["description"], str) or not 25 <= len(value["description"]) <= 200:
        raise ValueError("Invalid description")
    sections = value["sections"]
    if not isinstance(sections, list) or not 4 <= len(sections) <= 6:
        raise ValueError("4–6 sections required")
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"heading", "body"}:
            raise ValueError("Invalid section")
        if not all(isinstance(section[k], str) for k in ("heading", "body")) or not 100 <= len(section["body"]) <= 1500:
            raise ValueError("Invalid section body")
    if len({s["body"] for s in sections}) != len(sections):
        raise ValueError("Duplicate paragraphs")
    return value


def draft_text(value: str) -> str:
    """Keep generated prose from inserting HTML or Markdown links/images."""
    return re.sub(r"([\\`*_\[\]])", r"\\\1", html.escape(value))


async def ai_article(topic: str, keyword: str, day: date, previous_titles: list[str]):
    # Explicit --ai only. Reads existing key without logging or copying it.
    sys.path.insert(0, str(ROOT / "backend"))
    import httpx
    from dotenv import load_dotenv
    from app.gemini import get_gemini_settings
    from app.yeoul import extract_json, GEMINI_INTERACTIONS_URL
    load_dotenv(ROOT / "backend/.env")
    settings = get_gemini_settings()
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        response = await client.post(GEMINI_INTERACTIONS_URL, headers={"x-goog-api-key": settings.api_key}, json={
            "model": settings.model, "store": False,
            "system_instruction": "한국어 사주 교육 콘텐츠 편집자입니다. 전통 해석과 사실을 구분하세요. 미래·재회·수익·검색순위·검색량을 보장하지 마세요. 가짜 경험담, 연구, 출처, 리뷰, 진단, 숫자를 만들지 마세요. 불안이나 결핍으로 구매를 압박하지 마세요. 검토용 초안을 씁니다. JSON만 반환하세요.",
            "input": json.dumps({"date": day.isoformat(), "keyword": keyword, "topic": GROUPS[topic][0], "reference": SECTIONS[topic], "avoid_previous_titles": previous_titles[-30:], "task": "이 키워드의 질문에 답하는 서로 다른 4–6절의 글. 각 본문 250–450자. title, description(50–120자), sections:[{heading,body}] JSON. HTML이나 마크다운 링크 없이 본문만 작성."}, ensure_ascii=False),
            "generation_config": {"temperature": 0.7, "max_output_tokens": 6500},
        })
        if response.status_code != 200:
            raise RuntimeError(f"콘텐츠 생성 실패 (HTTP {response.status_code}); 발행하지 않았습니다.")
        return validate_article(extract_json(response.json()))


def generate_batch(day: date, output: Path, origin: str = "", metrics: Path | None = None, ai: bool = False):
    origin = site_origin(origin)
    destination = output / day.isoformat()
    if destination.exists():
        return destination  # Never overwrite an edited or reviewed daily batch.
    output.mkdir(parents=True, exist_ok=True)
    rows = keyword_rows(metrics)
    prior_titles, prior_hashes = [], set()
    for previous in sorted(output.glob("*/manifest.json")):
        saved = json.loads(previous.read_text())
        prior_titles.extend(item["title"] for item in saved.get("articles", []))
        prior_hashes.update(item["body_hash"] for item in saved.get("articles", []))
    staging = Path(tempfile.mkdtemp(prefix=".batch-", dir=output))
    try:
        with (staging / "keywords.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        articles = []
        for index, group in enumerate(GROUPS):
            candidates = [row for row in rows if row["topic"] == group]
            keyword = candidates[(day.toordinal() + index) % len(candidates)]["keyword"]
            article = asyncio.run(ai_article(group, keyword, day, prior_titles)) if ai else {
                "title": GROUPS[group][0] + ": 단정하기 전에 살펴볼 것들",
                "description": f"{GROUPS[group][0]}을 전통 해석의 관점으로 살펴보고, 내 경험과 현실의 조건을 함께 확인하는 여울의 안내입니다.",
                "sections": [{"heading": h, "body": b} for h, b in SECTIONS[group]],
            }
            validate_article(article)
            body_hash = hashlib.sha256(json.dumps(article["sections"], ensure_ascii=False).encode()).hexdigest()
            duplicate = body_hash in prior_hashes
            prior_hashes.add(body_hash)
            prior_titles.append(article["title"])
            cta = f"{origin}/app/?utm_source=blog&utm_medium=owned&utm_campaign={day.isoformat()}-{group}#start"
            banner = f'<aside class="yeoul-cta"><p>내 글자에서 시작해보세요.</p><a href="{html.escape(cta, quote=True)}">무료로 내 사주 기본 정보 보기</a><p>사주 기본 정보는 무료 · 개인 풀이는 준비 중</p></aside>'
            copy = f"# {draft_text(article['title'])}\n\n> 검토용 초안 · {day} · {'AI 생성, 사실 확인 필요' if ai else '편집 템플릿, 보완 필요'}\n\n{draft_text(article['description'])}\n"
            copy += "".join(f"\n## {draft_text(s['heading'])}\n\n{draft_text(s['body'])}\n" for s in article["sections"])
            copy += f"\n{banner}\n\n편집 검토: 계산 기준·출처·중복·단정적 표현·CTA 도착 페이지를 확인하세요.\n"
            filename = f"{index+1:02d}-{group}.md"
            (staging / filename).write_text(copy)
            articles.append({"file": filename, "title": article["title"], "keyword": keyword, "body_hash": body_hash, "duplicate": duplicate, "status": "duplicate_hold" if duplicate else "review_required"})
        threads = [{"hook": hook, "status": "draft", "owned_post_id": None, "reply_text": "무료로 내 사주 원국을 확인하고, 글자가 뜻하는 바부터 읽어보세요.", "reply_url": f"{origin}/app/?utm_source=threads&utm_medium=owned&utm_campaign={day.isoformat()}#start"} for hook in HOOKS]
        (staging / "threads.json").write_text(json.dumps(threads, ensure_ascii=False, indent=2))
        manifest = {"date": day.isoformat(), "timezone": "Asia/Seoul", "mode": "ai_draft" if ai else "editorial_template", "publish_enabled": False, "site_configured": bool(origin), "search_volume_verified": sum(row["status"] == "measured" for row in rows), "articles": articles}
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        staging.rename(destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Seoul")).date())
    parser.add_argument("--output", type=Path, default=ROOT / "content/drafts")
    parser.add_argument("--site-url", default=os.getenv("SITE_URL", ""))
    parser.add_argument("--metrics", type=Path, help="CSV: keyword,monthly_searches,source,measured_at")
    parser.add_argument("--ai", action="store_true", help="Gemini API로 세 초안 생성 (API 비용 발생 가능). 기본은 외부 호출 없음.")
    args = parser.parse_args()
    print(generate_batch(args.date, args.output, args.site_url, args.metrics, args.ai))


if __name__ == "__main__":
    main()
