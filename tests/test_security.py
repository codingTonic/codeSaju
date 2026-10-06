from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import main, security
from app.gemini import GeminiGenerationError


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    main.tasks.clear()
    security.admission.clear()
    monkeypatch.setenv("AI_PROVIDER", "local_template")
    monkeypatch.setenv("EMAIL_NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("LOCAL_FALLBACK_ON_AI_ERROR", "true")
    monkeypatch.setattr(main, "ANALYSIS_STEP_DELAY_SECONDS", 0)
    yield
    main.tasks.clear()
    security.admission.clear()


def payload(**overrides):
    return dict(name="PRIVATE-NAME", birth_date="1990-05-15", birth_time="14:30",
                gender="male", relationship_status="single", processing_consent=True,
                privacy_policy_version="2026-09-07", **overrides)


def auth(created):
    return {"Authorization": f"Bearer {created.json()['access_token']}"}


def test_known_task_id_cannot_reveal_or_delete_without_its_separate_token():
    owner, other = TestClient(main.app), TestClient(main.app)
    created = owner.post("/api/v1/create-saju-book", json=payload())
    task_id = created.json()["task_id"]
    assert len(created.json()["access_token"]) == 43
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        response = other.get("/api/v1/progress", params={"task_id": task_id}, headers=headers)
        assert response.status_code == 404
        assert "PRIVATE-NAME" not in response.text
        assert other.delete(f"/api/v1/tasks/{task_id}", headers=headers).status_code == 404
    response = owner.get("/api/v1/progress", params={"task_id": task_id}, headers=auth(created))
    assert response.status_code == 200
    assert "PRIVATE-NAME" in response.text
    assert "access_digest" not in response.text and "consent" not in response.json()
    assert created.json()["access_token"] not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert owner.delete(f"/api/v1/tasks/{task_id}", headers=auth(created)).status_code == 204
    assert task_id not in main.tasks
    assert owner.get("/api/v1/progress", params={"task_id": task_id}, headers=auth(created)).status_code == 404


def test_token_for_another_task_is_rejected():
    client = TestClient(main.app)
    a = client.post("/api/v1/create-saju-book", json=payload())
    b = client.post("/api/v1/create-saju-book", json=payload())
    assert client.get("/api/v1/progress", params={"task_id": a.json()["task_id"]}, headers=auth(b)).status_code == 404


@pytest.mark.parametrize("value", [None, False, "true", 1])
def test_processing_consent_must_be_explicit_boolean_true(value):
    body = payload()
    if value is None:
        del body["processing_consent"]
    else:
        body["processing_consent"] = value
    assert TestClient(main.app).post("/api/v1/create-saju-book", json=body).status_code == 422
    assert not main.tasks and not security.admission.daily


def test_old_or_missing_policy_version_is_rejected():
    body = payload()
    body.pop("privacy_policy_version")
    assert TestClient(main.app).post("/api/v1/create-saju-book", json=body).status_code == 422


def test_rate_limit_rejects_before_generation(monkeypatch):
    monkeypatch.setattr(security, "RATE_REQUESTS", 2)
    client = TestClient(main.app)
    assert client.post("/api/v1/create-saju-book", json=payload()).status_code == 202
    assert client.post("/api/v1/create-saju-book", json=payload()).status_code == 202
    response = client.post("/api/v1/create-saju-book", json=payload())
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    assert len(main.tasks) == 2 and not security.admission.active


@pytest.mark.parametrize("limit", ["MAX_STORED_TASKS", "DAILY_REQUESTS"])
def test_global_limits_apply_to_different_clients(monkeypatch, limit):
    monkeypatch.setattr(security, limit, 1)
    assert TestClient(main.app).post("/api/v1/create-saju-book", json=payload()).status_code == 202
    client = TestClient(main.app, client=("192.0.2.2", 4321))
    assert client.post("/api/v1/create-saju-book", json=payload()).status_code == 429


def test_running_task_limit_and_timeout_release_capacity(monkeypatch):
    async def slow(*args):
        await asyncio.sleep(60)
    monkeypatch.setattr(main, "generate_analysis_task", slow)
    monkeypatch.setattr(main, "TASK_TIMEOUT_SECONDS", 0.01)
    created = TestClient(main.app).post("/api/v1/create-saju-book", json=payload())
    assert main.tasks[created.json()["task_id"]]["status"] == "failed"
    assert not security.admission.active and not main.running_jobs
    security.admission.active.update(str(i) for i in range(security.MAX_ACTIVE_TASKS))
    assert TestClient(main.app).post("/api/v1/create-saju-book", json=payload()).status_code == 429


def test_periodic_cleanup_runs_without_result_requests(monkeypatch):
    monkeypatch.setattr(main, "TASK_SWEEP_SECONDS", 0.01)
    async def check():
        main.tasks["expired"] = {"created_at": main.utc_now() - timedelta(hours=25)}
        async with main.lifespan(main.app):
            await asyncio.sleep(0.03)
            assert "expired" not in main.tasks
    asyncio.run(check())


def test_body_size_content_type_origin_and_host():
    client = TestClient(main.app)
    assert client.post("/api/v1/create-saju-book", json=payload(padding="x" * 20000)).status_code == 413
    assert client.post("/api/v1/create-saju-book", content=b"{}").status_code == 415
    assert client.post("/api/v1/create-saju-book", json=payload(), headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.get("/api/v1/health", headers={"Host": "evil.invalid"}).status_code == 400
    assert not main.tasks


def test_chunked_actual_bytes_cannot_bypass_size_limit():
    async def chunks():
        for _ in range(5):
            yield b"x" * 4096
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as client:
            response = await client.post("/api/v1/create-saju-book", content=chunks(), headers={"Content-Type": "application/json"})
            assert response.status_code == 413
            assert not main.tasks
    asyncio.run(check())


def test_cors_accepts_authorization_and_exposes_retry_after():
    response = TestClient(main.app).options("/api/v1/progress", headers={
        "Origin": "http://127.0.0.1:3005", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize("fallback", ["true", "false"])
def test_provider_errors_are_not_exposed_in_responses_or_logs(monkeypatch, caplog, fallback):
    async def fail(*args, **kwargs):
        raise GeminiGenerationError("PRIVATE-PROVIDER-KEY-AND-PERSONAL-DATA")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("LOCAL_FALLBACK_ON_AI_ERROR", fallback)
    monkeypatch.setattr(main, "generate_gemini_analysis", fail)
    client = TestClient(main.app)
    created = client.post("/api/v1/create-saju-book", json=payload())
    response = client.get("/api/v1/progress", params={"task_id": created.json()["task_id"]}, headers=auth(created))
    assert response.status_code == 200
    assert "PRIVATE-PROVIDER" not in response.text and "PRIVATE-PROVIDER" not in caplog.text


def test_validation_errors_do_not_echo_personal_input():
    body = payload()
    body["birth_time"] = "PRIVATE-INVALID-TIME"
    response = TestClient(main.app).post("/api/v1/create-saju-book", json=body)
    assert response.status_code == 422
    assert "PRIVATE" not in response.text
