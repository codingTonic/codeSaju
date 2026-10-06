#!/usr/bin/env python3
"""Build public guides and SEO metadata; no network, credentials or paid API needed."""
from __future__ import annotations

import argparse
import base64
from datetime import date
import hashlib
from html import escape
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- SEO:START -->", "<!-- SEO:END -->"
INDEX_TITLE = "사주 읽는 법 — 신년운세·궁합·이직운 가이드"
INDEX_DESCRIPTION = "사주 기본 정보부터 2026년 신년운세, 궁합, 이직과 재회의 흐름까지, 풀이를 읽기 전에 알아두면 좋은 내용을 살펴보세요."
JSONLD_PATTERN = re.compile(r'<script\b(?=[^>]*\btype=[\"\']application/ld\+json[\"\'])[^>]*>(.*?)</script\s*>', re.I | re.S)


def validate_site_url(value: str) -> str:
    """Accept a real HTTPS origin, never a placeholder, private host or URL path."""
    if not value:
        return ""
    if value != value.strip() or any(c.isspace() for c in value):
        raise ValueError("SITE_URL에는 공백을 넣을 수 없습니다.")
    parsed = urlsplit(value)
    try:
        hostname = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (ValueError, UnicodeError) as error:
        raise ValueError("SITE_URL의 도메인을 확인하세요.") from error
    if (parsed.scheme != "https" or not hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or "?" in value or "#" in value or port not in (None, 443)):
        raise ValueError("SITE_URL은 경로·쿼리·인증정보 없는 HTTPS 운영 도메인이어야 합니다.")
    labels = hostname.split(".")
    reserved = ("localhost", "local", "test", "invalid", "example", "internal", "onion")
    if (len(labels) < 2 or labels[-1] in reserved
            or hostname in {"example.com", "example.net", "example.org"}
            or any(hostname.endswith("." + name) for name in ("example.com", "example.net", "example.org"))
            or not re.fullmatch(r"[a-z]{2,63}|xn--[a-z0-9-]+", labels[-1])
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
        raise ValueError("SITE_URL에 로컬 주소나 예시 도메인을 사용할 수 없습니다.")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("SITE_URL에는 IP 주소 대신 운영 도메인을 사용하세요.")
    return "https://" + hostname


def load_guides(source: Path = ROOT / "content/guides.json") -> list[dict]:
    guides = json.loads(source.read_text(encoding="utf-8"))
    slugs = [guide["slug"] for guide in guides]
    if len(set(slugs)) != len(slugs) or not all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s) for s in slugs):
        raise ValueError("Guide slugs must be unique, safe URL segments")
    for guide in guides:
        date.fromisoformat(guide["updated"])
        if any(related not in slugs for related in guide["related"]):
            raise ValueError("Unknown related guide")
    return guides


def jsonld(schema: dict) -> str:
    # Script data is not HTML: encode angle brackets rather than HTML-escaping JSON.
    data = json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">{data}</script>'


def metadata(site_url: str, path: str, title: str, description: str, *, article: dict | None = None) -> str:
    tags = [f'<meta name="robots" content="{"index, follow" if site_url else "noindex, nofollow"}" />',
            '<meta property="og:locale" content="ko_KR" />',
            '<meta property="og:site_name" content="여울" />',
            f'<meta property="og:type" content="{"article" if article else "website"}" />',
            f'<meta property="og:title" content="{escape(title, quote=True)}" />',
            f'<meta property="og:description" content="{escape(description, quote=True)}" />',
            '<meta name="twitter:card" content="summary_large_image" />']
    if not site_url:
        return "\n".join(tags)
    url = site_url + path
    tags += [f'<link rel="canonical" href="{url}" />',
             f'<meta property="og:url" content="{url}" />',
             f'<meta property="og:image" content="{site_url}/app/assets/higgsfield/hero-desktop.webp" />',
             '<meta property="og:image:alt" content="여울의 맑은 물길과 종이배 풍경" />',
             '<meta property="og:image:width" content="1920" />',
             '<meta property="og:image:height" content="1080" />']
    schema = {"@context": "https://schema.org", "@type": "Article" if article else "WebPage",
              "@id": url + "#article" if article else url + "#webpage", "url": url,
              "name": title, "description": description, "inLanguage": "ko-KR"}
    if article:
        schema.update({"headline": title, "dateModified": article["updated"],
                       "author": {"@type": "Organization", "name": "여울"},
                       "publisher": {"@type": "Organization", "name": "여울"},
                       "mainEntityOfPage": {"@type": "WebPage", "@id": url},
                       "articleSection": article["category"],
                       "image": site_url + "/app/assets/higgsfield/hero-desktop.webp"})
        tags.append(f'<meta property="article:modified_time" content="{article["updated"]}" />')
    tags.append(jsonld(schema))
    return "\n".join(tags)


def shell(site_url: str, path: str, title: str, description: str, main: str, article: dict | None = None) -> str:
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{escape(title)} | 여울</title>
  <meta name="description" content="{escape(description, quote=True)}" />
  <meta name="referrer" content="no-referrer" />
  <meta name="theme-color" content="#EDF3F9" />
  <link rel="icon" href="/app/mark.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="/guides/guides.css" />
  {metadata(site_url, path, title, description, article=article)}
</head>
<body>
  <a class="skip-link" href="#main">본문 바로가기</a>
  <header class="site-header"><a class="brand" href="/app/"><img src="/app/mark.svg" width="30" height="30" alt="" />여울</a><nav aria-label="주 메뉴"><a href="/guides/">사주 읽는 법</a><a href="/app/#start">내 사주 보기</a></nav></header>
  <main id="main" tabindex="-1">{main}</main>
  <footer><a href="/app/">여울 홈</a><a href="/app/#privacy">개인정보 안내</a><p>사주는 전통적 해석을 바탕으로 나를 돌아보는 참고 자료입니다. 미래의 사건이나 관계의 결과를 보장하지 않습니다.</p></footer>
</body>
</html>
'''


def render_guide(guide: dict, guides: list[dict], site_url: str) -> str:
    escape_text = escape
    toc = "".join(f'<li><a href="#section-{i}">{escape_text(s["heading"])}</a></li>' for i, s in enumerate(guide["sections"], 1))
    sections = "".join(f'<section aria-labelledby="section-{i}"><h2 id="section-{i}">{escape_text(s["heading"])}</h2>' + "".join(f'<p>{escape_text(p)}</p>' for p in s["paragraphs"]) + '</section>' for i, s in enumerate(guide["sections"], 1))
    checklist = "".join(f'<li>{escape_text(item)}</li>' for item in guide["checklist"])
    related = "".join(f'<li><a href="/guides/{other["slug"]}/">{escape_text(other["title"])}</a></li>' for other in guides if other["slug"] in guide["related"])
    main = f'''<nav class="breadcrumb" aria-label="현재 위치"><a href="/app/">여울</a><span aria-hidden="true">/</span><a href="/guides/">사주 읽는 법</a></nav>
    <article><header class="article-header"><p class="eyebrow">{escape_text(guide["category"])}</p><h1>{escape_text(guide["title"])}</h1><p class="lead">{escape_text(guide["intro"])}</p><p class="byline">여울 · AI 도움으로 작성한 가이드 · <time datetime="{guide["updated"]}">{guide["updated"]} 수정</time></p></header>
    <img class="guide-cover" src="/app/assets/higgsfield/hero-desktop.webp" width="1920" height="1080" alt="여울의 맑은 물길과 종이배 풍경" />
    <nav class="contents" aria-label="이 글의 순서"><p>이 글에서 살펴볼 것</p><ol>{toc}</ol></nav>
    <div class="article-body">{sections}<section class="checklist" aria-labelledby="checklist-title"><h2 id="checklist-title">읽고 나서 확인할 질문</h2><ul>{checklist}</ul></section>
    <aside class="cta" aria-labelledby="cta-title"><p class="eyebrow">이제, 나의 질문으로</p><h2 id="cta-title">내 사주 기본 정보부터 살펴보세요</h2><p>양력·음력 출생 정보로 사주 표와 다섯 요소의 구성을 확인해보세요. 회원가입 없이 무료로 시작할 수 있으며, 개인별 상세 리포트는 준비 중입니다.</p><a class="button" href="/app/#start">내 사주 기본 정보 보기 <span aria-hidden="true">→</span></a></aside>
    <section aria-labelledby="related-title"><h2 id="related-title">함께 읽으면 좋은 글</h2><ul class="related">{related}</ul></section></div></article>'''
    return shell(site_url, f'/guides/{guide["slug"]}/', guide["title"], guide["description"], main, guide)


class AppHeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def update_app(frontend: Path, site_url: str) -> None:
    app_path = frontend / "app/index.html"
    html = app_path.read_text(encoding="utf-8")
    if html.count(START) != 1 or html.count(END) != 1 or html.index(START) > html.index(END):
        raise ValueError("app/index.html <head>에 SEO:START / SEO:END 마커가 각각 하나 필요합니다.")
    parser = AppHeadParser()
    parser.feed(html)
    if not parser.title or not parser.description:
        raise ValueError("App title and description must exist before generating metadata")
    start, end = html.index(START) + len(START), html.index(END)
    html = html[:start] + "\n" + metadata(site_url, "/app/", parser.title, parser.description) + "\n" + html[end:]
    app_path.write_text(html, encoding="utf-8")


def build(frontend: Path, site_url: str = "", *, include_app: bool = False) -> dict:
    site_url = validate_site_url(site_url)
    guides = load_guides()
    frontend.mkdir(parents=True, exist_ok=True)
    # Validate/update app before writing public manifests so a missing marker fails closed.
    if include_app:
        update_app(frontend, site_url)
    guide_dir = frontend / "guides"
    guide_dir.mkdir(parents=True, exist_ok=True)
    cards = "".join(f'<li><article><p class="eyebrow">{escape(g["category"])}</p><h2><a href="/guides/{g["slug"]}/">{escape(g["title"])}</a></h2><p>{escape(g["description"])}</p></article></li>' for g in guides)
    index_main = f'<header class="index-header"><p class="eyebrow">여울 가이드</p><h1>{INDEX_TITLE}</h1><p class="lead">단정하는 답보다, 나를 이해할 질문을.<br />내 사주를 읽기 전에 알아두면 좋은 내용을 모았습니다.</p></header><ul class="guide-list">{cards}</ul>'
    (guide_dir / "index.html").write_text(shell(site_url, "/guides/", INDEX_TITLE, INDEX_DESCRIPTION, index_main), encoding="utf-8")
    paths = ["/guides/"]
    modified = {}
    for guide in guides:
        directory = guide_dir / guide["slug"]
        directory.mkdir(exist_ok=True)
        (directory / "index.html").write_text(render_guide(guide, guides, site_url), encoding="utf-8")
        path = f'/guides/{guide["slug"]}/'
        paths.append(path)
        modified[path] = guide["updated"]
    # Never add an app that has not been built for this same domain.
    app_path = frontend / "app/index.html"
    if site_url and app_path.exists() and f'<link rel="canonical" href="{site_url}/app/"' in app_path.read_text(encoding="utf-8"):
        paths.insert(0, "/app/")
    if not site_url:
        robots = "User-agent: *\nDisallow: /\n"
    else:
        robots = ("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /pages/\n"
                  "Disallow: /results/\nDisallow: /reports/\nDisallow: /checkout/\nDisallow: /drafts/\n"
                  f"\nSitemap: {site_url}/sitemap.xml\n")
    (frontend / "robots.txt").write_text(robots, encoding="utf-8")
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    urlset = ET.Element(f"{{{namespace}}}urlset")
    for path in paths if site_url else []:
        node = ET.SubElement(urlset, f"{{{namespace}}}url")
        ET.SubElement(node, f"{{{namespace}}}loc").text = site_url + path
        if path in modified:
            ET.SubElement(node, f"{{{namespace}}}lastmod").text = modified[path]
    ET.indent(urlset)
    ET.ElementTree(urlset).write(frontend / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    hashes = {}
    for path in paths:
        html = (frontend / path.strip("/") / "index.html").read_text(encoding="utf-8")
        hashes[path] = ["sha256-" + base64.b64encode(hashlib.sha256(data.encode("utf-8")).digest()).decode("ascii") for data in JSONLD_PATTERN.findall(html)]
    manifest = {"site_url": site_url, "public_paths": paths if site_url else [], "jsonld_csp_hashes": hashes}
    (frontend / "seo-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    parser.add_argument("--frontend", type=Path, default=ROOT / "frontend")
    parser.add_argument("--include-app", action="store_true", help="Replace the marked SEO block in app/index.html too")
    args = parser.parse_args()
    try:
        manifest = build(args.frontend.resolve(), args.site_url, include_app=args.include_app)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'SEO built: {len(manifest["public_paths"])} indexable URLs; ' + (manifest["site_url"] or "SITE_URL unset — noindex preview"))


if __name__ == "__main__":
    main()
