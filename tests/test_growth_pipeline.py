"""Editorial batch tests run without network or content-provider credentials."""
import csv
from datetime import date
import importlib.util
import json
from pathlib import Path
import socket

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("growth_pipeline", ROOT / "scripts/growth_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def read_manifest(directory):
    return json.loads((directory / "manifest.json").read_text())


def write_metrics(path, values):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["keyword", "monthly_searches", "source", "measured_at"])
        writer.writeheader()
        writer.writerows(values)
    return path


def metric(**changes):
    return {"keyword": "을목일간 성향 이해하기", "monthly_searches": "120", "source": "operator-export", "measured_at": "2026-09-28", **changes}


def test_default_batch_never_calls_network_and_has_30_3_10(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Default editorial mode must not call a network or AI provider")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(pipeline, "ai_article", no_network)
    directory = pipeline.generate_batch(date(2026, 9, 29), tmp_path)
    with (directory / "keywords.csv").open(encoding="utf-8-sig", newline="") as file:
        keywords = list(csv.DictReader(file))
    manifest = read_manifest(directory)
    threads = json.loads((directory / "threads.json").read_text())
    assert len(keywords) == 30
    assert len({row["keyword"] for row in keywords}) == 30
    assert all(row["status"] == "unverified_candidate" and row["monthly_searches"] == "" for row in keywords)
    assert len(manifest["articles"]) == len(list(directory.glob("*.md"))) == 3
    assert len(threads) == 10
    assert all(item["status"] == "draft" and item["owned_post_id"] is None for item in threads)
    assert manifest["mode"] == "editorial_template"
    assert manifest["publish_enabled"] is False
    assert manifest["site_configured"] is False
    assert manifest["search_volume_verified"] == 0
    assert all(item["status"] == "review_required" for item in manifest["articles"])


def test_rerun_preserves_reviewed_and_edited_files(tmp_path, monkeypatch):
    day = date(2026, 9, 29)
    directory = pipeline.generate_batch(day, tmp_path)
    article = directory / "01-eulmok.md"
    article.write_text("# Reviewed by an editor\n\nKeep this exact edit.\n")
    manifest_path = directory / "manifest.json"
    manifest = read_manifest(directory)
    manifest["articles"][0]["status"] = "reviewed"
    manifest_path.write_text(json.dumps(manifest))
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    def no_ai(*args):
        pytest.fail("Existing daily batch must be returned before generation")
    monkeypatch.setattr(pipeline, "ai_article", no_ai)
    assert pipeline.generate_batch(day, tmp_path, ai=True) == directory
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_template_repetition_is_held_on_next_day(tmp_path):
    pipeline.generate_batch(date(2026, 9, 29), tmp_path)
    second = pipeline.generate_batch(date(2026, 9, 30), tmp_path)
    assert all(row["duplicate"] and row["status"] == "duplicate_hold" for row in read_manifest(second)["articles"])


def test_supplied_metrics_rank_candidates_without_fabricating_others(tmp_path):
    metrics = write_metrics(tmp_path / "metrics.csv", [metric(), metric(keyword="재회운 보는 법과 한계", monthly_searches="300")])
    rows = pipeline.keyword_rows(metrics)
    assert rows[0]["keyword"] == "재회운 보는 법과 한계"
    assert rows[0]["source"] == "operator-export"
    assert len([row for row in rows if row["status"] == "measured"]) == 2
    assert len([row for row in rows if row["status"] == "unverified_candidate"]) == 28
    batch = pipeline.generate_batch(date(2026, 9, 29), tmp_path / "batches", metrics=metrics)
    assert read_manifest(batch)["search_volume_verified"] == 2


@pytest.mark.parametrize("change", [
    {"monthly_searches": "-1"}, {"monthly_searches": "many"}, {"monthly_searches": "1.5"},
    {"measured_at": "yesterday"}, {"measured_at": "2026-02-30"}, {"source": " "}, {"keyword": ""},
])
def test_invalid_metrics_leave_no_daily_batch(tmp_path, change):
    metrics = write_metrics(tmp_path / "metrics.csv", [metric(**change)])
    with pytest.raises(ValueError):
        pipeline.generate_batch(date(2026, 9, 29), tmp_path / "drafts", metrics=metrics)
    assert not (tmp_path / "drafts/2026-09-29").exists()
    assert not list((tmp_path / "drafts").glob(".batch-*"))


def test_missing_metrics_columns_and_duplicate_keywords_are_rejected(tmp_path):
    path = tmp_path / "metrics.csv"
    path.write_text("keyword,monthly_searches\n을목일간 성향 이해하기,12\n")
    with pytest.raises(ValueError, match="열이 필요"):
        pipeline.keyword_rows(path)
    write_metrics(path, [metric(), metric(monthly_searches="999")])
    with pytest.raises(ValueError, match="중복"):
        pipeline.keyword_rows(path)


@pytest.mark.parametrize("origin", [
    "http://example.com", "javascript:alert(1)", "https://user:pass@example.com",
    "https://@example.com", "https://example.com/path", "https://example.com?next=evil",
    "https://example.com/#section", "https://example.com\n", "https://example.com:bad",
    "https://example.com:99999", "https://example.com:0", "https://example.com\\path",
    'https://example.com\"onclick=\"alert(1)', "https://-invalid.example",
])
def test_unsafe_or_malformed_cta_origin_rejected(origin):
    with pytest.raises(ValueError):
        pipeline.site_origin(origin)


@pytest.mark.parametrize("origin", ["https://example.com", "https://example.com/", "https://example.com:8443", "https://[::1]"])
def test_valid_https_origins_are_accepted(origin):
    assert pipeline.site_origin(origin) == origin.rstrip("/")


def test_cta_uses_configured_origin_and_owned_source(tmp_path):
    batch = pipeline.generate_batch(date(2026, 9, 29), tmp_path, "https://yeoul.example/")
    assert read_manifest(batch)["site_configured"] is True
    for article in batch.glob("*.md"):
        text = article.read_text()
        assert 'href="https://yeoul.example/app/?utm_source=blog&amp;utm_medium=owned&amp;utm_campaign=2026-09-29-' in text
        assert "무료로 내 사주 기본 정보 보기" in text
    threads = json.loads((batch / "threads.json").read_text())
    assert all(row["reply_url"].startswith("https://yeoul.example/app/?utm_source=threads&utm_medium=owned") for row in threads)


def test_explicit_ai_mode_calls_generator_three_times_and_holds_same_batch_duplicates(tmp_path, monkeypatch):
    calls = []
    async def fake_ai(topic, keyword, day, previous_titles):
        calls.append((topic, keyword, list(previous_titles)))
        return {
            "title": "생성 결과를 검토하는 테스트 제목",
            "description": "실제 외부 네트워크 호출 없이 세 편의 생성 흐름과 중복 검사를 확인하는 테스트입니다.",
            "sections": [{"heading": h, "body": b} for h, b in pipeline.SECTIONS["eulmok"]],
        }
    monkeypatch.setattr(pipeline, "ai_article", fake_ai)
    batch = pipeline.generate_batch(date(2026, 9, 29), tmp_path, ai=True)
    manifest = read_manifest(batch)
    assert len(calls) == 3
    assert manifest["mode"] == "ai_draft"
    assert [row["status"] for row in manifest["articles"]] == ["review_required", "duplicate_hold", "duplicate_hold"]
    assert len(calls[-1][2]) == 2


def test_generation_failure_cleans_staging_without_partial_batch(tmp_path, monkeypatch):
    async def broken_ai(*args):
        raise RuntimeError("Simulated provider failure")
    monkeypatch.setattr(pipeline, "ai_article", broken_ai)
    with pytest.raises(RuntimeError, match="Simulated"):
        pipeline.generate_batch(date(2026, 9, 29), tmp_path, ai=True)
    assert not (tmp_path / "2026-09-29").exists()
    assert not list(tmp_path.glob(".batch-*"))


def test_ai_prose_cannot_insert_raw_html_or_markdown_links(tmp_path, monkeypatch):
    async def markup_ai(topic, keyword, day, previous_titles):
        return {
            "title": "HTML과 링크 삽입을 검증하는 글 제목",
            "description": "모델이 지시를 따르지 않고 마크업을 넣어도 미리보기에서 활성화되지 않아야 합니다.",
            "sections": [{"heading": h, "body": b + '<script>alert(1)</script> [click](javascript:alert(1)) ![pixel](https://external.example/pixel)'} for h, b in pipeline.SECTIONS[topic]],
        }
    monkeypatch.setattr(pipeline, "ai_article", markup_ai)
    batch = pipeline.generate_batch(date(2026, 9, 29), tmp_path, ai=True)
    text = (batch / "01-eulmok.md").read_text()
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert r"\[click\](javascript:alert(1))" in text
    assert r"!\[pixel\](https://external.example/pixel)" in text
