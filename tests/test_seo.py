from __future__ import annotations

import base64
from functools import partial
import hashlib
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


seo = module("build_seo", ROOT / "scripts/build_seo.py")
server_module = module("serve_frontend", ROOT / "serve_frontend.py")
SITE = "https://yeoul-deployment.kr"


class Page(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.tags = []
        self.links = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "a":
            self.links.append(attrs.get("href", ""))

    def handle_data(self, data):
        self.text.append(data)


@pytest.fixture
def frontend(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "index.html").write_text('<!doctype html><html lang="ko"><head><title>여울 사주</title><meta name="description" content="나의 기질과 삶의 흐름을 읽는 사주" /><!-- SEO:START --><!-- SEO:END --></head><body><h1>여울 사주</h1><a href="/guides/">사주 읽는 법</a></body></html>', encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("site", ["http://yeoul.kr", "https://localhost", "https://127.0.0.1", "https://example.com", "https://sub.example.org", "https://yeoul.test", "https://foo.local", "https://foo.invalid", "https://user:secret@yeoul.kr", "https://yeoul.kr/path", "https://yeoul.kr?token=x", "https://yeoul.kr?", "https://yeoul.kr/#x", "https://yeoul.kr#", "https://yeoul.kr:8080", "https://yeoul.kr\n", "https://-bad.kr"])
def test_production_url_rejects_placeholder_private_and_unsafe_origins(site):
    with pytest.raises(ValueError):
        seo.validate_site_url(site)


def test_url_normalization_is_deterministic():
    assert seo.validate_site_url("https://Yeoul.kr:443/") == "https://yeoul.kr"
    assert seo.validate_site_url("") == ""


def test_preview_build_never_invents_a_public_domain(frontend):
    manifest = seo.build(frontend, include_app=True)
    assert manifest["site_url"] == ""
    assert manifest["public_paths"] == []
    assert "Disallow: /" in (frontend / "robots.txt").read_text()
    assert len(ET.parse(frontend / "sitemap.xml").getroot()) == 0
    for path in [frontend / "app/index.html", *frontend.glob("guides/**/index.html")]:
        html = path.read_text()
        assert 'content="noindex, nofollow"' in html
        assert 'rel="canonical"' not in html
        assert 'property="og:url"' not in html


def test_public_sitemap_only_has_static_canonical_pages(frontend):
    manifest = seo.build(frontend, SITE, include_app=True)
    root = ET.parse(frontend / "sitemap.xml").getroot()
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in root.findall("s:url/s:loc", namespace)]
    assert len(urls) == 7  # App, guide index, five guides.
    assert urls == [SITE + path for path in manifest["public_paths"]]
    assert all("?" not in url and "#" not in url for url in urls)
    assert all(not any(part in url for part in ("api/", "pages/", "report", "result", "checkout", "draft")) for url in urls)
    assert f"Sitemap: {SITE}/sitemap.xml" in (frontend / "robots.txt").read_text()
    for path in manifest["public_paths"]:
        file = frontend / path.strip("/") / "index.html"
        html = file.read_text()
        assert f'<link rel="canonical" href="{SITE}{path}"' in html
        assert 'content="index, follow"' in html
        assert 'content="noindex' not in html
        blocks = seo.JSONLD_PATTERN.findall(html)
        assert len(blocks) == 1
        schema = json.loads(blocks[0])
        assert schema["url"] == SITE + path
        assert schema["@type"] in {"WebPage", "Article"}
        assert "aggregateRating" not in schema
        assert "review" not in schema


def test_guides_are_discoverable_without_javascript_and_match_schema(frontend):
    seo.build(frontend, SITE, include_app=True)
    page = Page((frontend / "guides/index.html").read_text())
    for guide in seo.load_guides():
        path = f'/guides/{guide["slug"]}/'
        assert path in page.links
        html = (frontend / path.strip("/") / "index.html").read_text()
        parsed = Page(html)
        assert len([tag for tag, _ in parsed.tags if tag == "h1"]) == 1
        assert any(tag == "article" for tag, _ in parsed.tags)
        assert len("".join(parsed.text)) > 1800
        assert "/app/#start" in parsed.links
        assert "/guides/" in parsed.links
        assert all(attrs.get("type") == "application/ld+json" for tag, attrs in parsed.tags if tag == "script")
        schema = json.loads(seo.JSONLD_PATTERN.findall(html)[0])
        for field in ("headline", "articleSection", "dateModified"):
            assert schema[field] in "".join(parsed.text)
        assert "여울 · AI 도움으로 작성한 가이드" in html


def test_schema_and_html_escape_content_without_executable_injection():
    guide = dict(seo.load_guides()[0], title='인용 "제목" </script><script>alert(1)</script>')
    html = seo.render_guide(guide, seo.load_guides(), SITE)
    blocks = seo.JSONLD_PATTERN.findall(html)
    assert len(blocks) == 1
    assert json.loads(blocks[0])["headline"] == guide["title"]
    assert "<script>alert(1)</script>" not in html


def test_rebuild_updates_app_metadata_once_and_preserves_app(frontend):
    seo.build(frontend, SITE, include_app=True)
    first = (frontend / "app/index.html").read_text()
    seo.build(frontend, SITE, include_app=True)
    assert (frontend / "app/index.html").read_text() == first
    seo.build(frontend, include_app=True)
    html = (frontend / "app/index.html").read_text()
    assert 'href="/guides/"' in html
    assert SITE not in html
    assert html.count('name="robots"') == 1


def test_missing_app_marker_cannot_enable_indexing(frontend):
    app = frontend / "app/index.html"
    app.write_text("<html><head><title>여울</title></head></html>")
    with pytest.raises(ValueError):
        seo.build(frontend, SITE, include_app=True)
    assert not (frontend / "seo-manifest.json").exists()


@pytest.fixture
def serving(frontend):
    seo.build(frontend, SITE, include_app=True)
    (frontend / ".private").write_text("SECRET")
    pages = frontend / "pages"
    pages.mkdir()
    (pages / "result.html").write_text("PRIVATE RESULT SHELL")
    outside = frontend.parent / "outside-secret.txt"
    outside.write_text("SECRET")
    (frontend / "leak.txt").symlink_to(outside)
    handler = partial(server_module.FrontendRequestHandler, directory=str(frontend))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def fetch(url, method="GET", production=True):
    headers = {"Host": "yeoul-deployment.kr"} if production else {}
    return urlopen(Request(url, method=method, headers=headers))


def test_served_schema_gets_exact_csp_hash_without_unsafe_inline(serving):
    with fetch(serving + "/guides/eulmok/") as response:
        assert response.status == 200
        assert response.headers.get("X-Robots-Tag") is None
        html = response.read().decode()
        data = seo.JSONLD_PATTERN.findall(html)[0]
        digest = base64.b64encode(hashlib.sha256(data.encode()).digest()).decode()
        scripts = response.headers["Content-Security-Policy"].split("script-src ")[1].split(";")[0]
        assert f"'sha256-{digest}'" in scripts
        assert "unsafe-inline" not in scripts
    with fetch(serving + "/guides/eulmok/", production=False) as response:
        assert "noindex" in response.headers["X-Robots-Tag"]


def test_shared_image_is_not_noindexed_on_production_host(frontend):
    seo.build(frontend, SITE, include_app=True)
    handler = server_module.FrontendRequestHandler.__new__(server_module.FrontendRequestHandler)
    handler.directory = str(frontend)
    handler.path = "/app/assets/higgsfield/hero-desktop.webp"
    handler.headers = {"Host": "yeoul-deployment.kr"}
    assert handler._is_public_page(handler.path)
    handler.headers = {"Host": "localhost"}
    assert not handler._is_public_page(handler.path)


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_served_private_paths_queries_and_files_remain_protected(serving, method):
    for path in ("/pages/result.html", "/guides/eulmok/?task_id=private"):
        with fetch(serving + path, method) as response:
            assert "noindex" in response.headers["X-Robots-Tag"]
    for path in ("/.private", "/%2eprivate", "/leak.txt", "/pages/"):
        with pytest.raises(HTTPError) as error:
            fetch(serving + path, method)
        assert error.value.code == 404
    with fetch(serving + "/api-config.js", method) as response:
        assert response.headers["Content-Type"].startswith("application/javascript")
        if method == "HEAD":
            assert response.read() == b""


@pytest.mark.parametrize("path,target", [("/", "/app/"), ("/app/index.html", "/app/"), ("/index.html?birth=private", "/app/"), ("/guides/eulmok/index.html", "/guides/eulmok/")])
def test_root_and_index_urls_redirect_to_one_canonical_path(serving, path, target):
    with fetch(serving + path) as response:
        assert response.url == serving + target
        assert response.status == 200
