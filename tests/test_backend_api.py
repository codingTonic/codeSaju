from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import main as main_module
from app.gemini import GeminiGenerationError


@pytest.fixture(autouse=True)
def reset_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    main_module.tasks.clear()
    main_module.admission.clear()
    monkeypatch.setattr(main_module, "ANALYSIS_STEP_DELAY_SECONDS", 0.0)
    monkeypatch.setenv("AI_PROVIDER", "local_template")
    for name in (
        "EMAIL_NOTIFICATIONS_ENABLED",
        "GMAIL_SMTP_USER",
        "GMAIL_APP_PASSWORD",
        "EMAIL_NOTIFICATION_TO",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(main_module.app)


def valid_payload() -> dict[str, object]:
    return {
        "processing_consent": True,
        "privacy_policy_version": "2026-09-07",
        "name": "테스트 사용자",
        "birth_date": "1990-05-15",
        "birth_time": "14:30",
        "gender": "male",
        "relationship_status": "single",
        "mbti": "infp",
        "calendar_type": "solar",
    }


def test_health_reports_local_mode(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "mode": "local_template",
        "durable_tasks": False,
        "ai_configured": False,
        "email_enabled": False,
        "email_configured": False,
    }


def test_health_reports_configured_gemini_without_exposing_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "mode": "gemini",
        "durable_tasks": False,
        "ai_configured": True,
        "email_enabled": False,
        "email_configured": False,
    }
    assert "private-test-key" not in response.text


def test_cors_allows_current_frontend_port(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:3005",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3005"


def test_create_and_read_completed_analysis(client: TestClient) -> None:
    payload = valid_payload()
    payload["writing_style"] = "legacy-field-is-ignored"

    created = client.post("/api/v1/create-saju-book", json=payload)

    assert created.status_code == 202
    task_id = created.json()["task_id"]

    progress = client.get("/api/v1/progress", params={"task_id": task_id},
                          headers={"Authorization": f"Bearer {created.json()['access_token']}"})
    assert progress.status_code == 200
    body = progress.json()
    assert body["status"] == "completed"
    assert body["email_notification"] == "not_consented"
    assert body["percent_overall"] == 100
    assert len(body["analysis_result"]["table_of_contents"]["chapters"]) == 5
    relationship_titles = [
        section["title"]
        for section in body["analysis_result"]["table_of_contents"]["chapters"][3]["sections"]
    ]
    assert relationship_titles == [
        "어떤 대화에서 마음이 열리고 가까워질까?",
        "새로운 인연을 알아채는 기회 신호",
        "나를 살려주는 공간 에너지와 일상 정돈법",
    ]
    assert body["analysis_result"]["section_4_1"]
    assert body["analysis_result"]["section_5_4"]
    assert len(body["analysis_result"]["special_dates"]) == 5
    assert len(body["analysis_result"]["quick_summary"]["timing_windows"]) == 12
    assert body["analysis_result"]["saju_profile"]["luck"]["next_transition_date"]
    timing_titles = [
        section["title"]
        for section in body["analysis_result"]["table_of_contents"]["chapters"][4]["sections"]
    ]
    assert timing_titles == [
        "내 생활 리듬과 회복을 돕는 쉼 루틴",
        "앞으로 3개월, 내가 주목해야 할 월별 타이밍",
        "선택한 변화를 이어가는 90일 실행 계획",
        "나만의 속도로 나아가기 위한 마지막 제언",
    ]
    assert body["analysis_result"]["user_data"]["mbti"] == "INFP"
    assert "birth_date" not in body["analysis_result"]["user_data"]
    practical = body["analysis_result"]["practical_summary"]
    assert practical["type"]["label"] == "경금 · 결단하고 단련하는 쇠형"
    assert practical["type"]["tagline"]
    assert len(practical["type"]["traits"]) == 3
    assert len(practical["chart"]) == 5
    assert all(metric["label"] for metric in practical["chart"])
    assert sum(metric["count"] for metric in practical["chart"]) == 8
    assert sum(metric["value"] for metric in practical["chart"]) == 8
    assert max(metric["bar_percent"] for metric in practical["chart"]) == 100
    assert sum(bool(metric["is_month_command"]) for metric in practical["chart"]) == 1
    assert len(practical["actions"]) == 3
    assert all(action["period"] and action["timing"] and action["action"] for action in practical["actions"])
    assert practical["social_profile"]["headline"].startswith("나의 결 |")
    assert practical["social_profile"]["summary"]
    assert practical["social_profile"]["hashtags"]
    assert "테스트 사용자" not in practical["social_profile"]["share_text"]
    assert "#나의결" in practical["social_profile"]["share_text"]
    profile = body["analysis_result"]["saju_profile"]
    assert profile["day_master"]["label"] == "경금 일간"
    assert [pillar["gan_zhi"] for pillar in profile["pillars"]] == [
        "庚午",
        "辛巳",
        "庚辰",
        "癸未",
    ]
    assert profile["luck"]["current_year"]["gan_zhi"] == "丙午"


def test_focus_concern_creates_an_additional_report_page(client: TestClient) -> None:
    payload = valid_payload()
    payload["focus_concern"] = "  이직과 커리어 전환  "

    created = client.post("/api/v1/create-saju-book", json=payload)
    progress = client.get(
        "/api/v1/progress",
        params={"task_id": created.json()["task_id"]},
        headers={"Authorization": f"Bearer {created.json()['access_token']}"},
    )

    analysis = progress.json()["analysis_result"]
    last_sections = analysis["table_of_contents"]["chapters"][4]["sections"]
    assert analysis["user_data"]["focus_concern"] == "이직과 커리어 전환"
    assert last_sections[-2]["id"] == "section_5_5"
    assert last_sections[-1]["id"] == "section_5_4"
    assert "이직과 커리어 전환" in last_sections[-2]["title"]
    assert "유지·탐색·전환" in analysis["section_5_5"]
    assert "공고 세 건" in analysis["section_5_5"]
    assert "이력서 성과 문장" in analysis["section_5_5"]


def test_email_health_reports_enabled_but_incomplete_configuration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMAIL_NOTIFICATIONS_ENABLED", "true")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["email_enabled"] is True
    assert response.json()["email_configured"] is False


def test_consented_request_runs_email_notification_with_analysis(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: dict[str, object] = {}

    async def fake_delivery(task_id: str, request: object) -> str:
        delivered["task_id"] = task_id
        delivered["request"] = request
        return "sent"

    monkeypatch.setattr(main_module, "deliver_user_info_notification", fake_delivery)
    payload = valid_payload()
    payload["email_notification_consent"] = True

    created = client.post("/api/v1/create-saju-book", json=payload)
    progress = client.get(
        "/api/v1/progress",
        params={"task_id": created.json()["task_id"]},
        headers={"Authorization": f"Bearer {created.json()['access_token']}"},
    )

    assert created.status_code == 202
    assert progress.json()["status"] == "completed"
    assert progress.json()["email_notification"] == "sent"
    assert delivered["task_id"] == created.json()["task_id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("birth_date", "1899-12-31"),
        ("gender", "unknown"),
        ("mbti", "ABCD"),
        ("focus_concern", "가" * 201),
    ],
)
def test_invalid_payload_returns_422(
    client: TestClient,
    field: str,
    value: str,
) -> None:
    payload = valid_payload()
    payload[field] = value

    response = client.post("/api/v1/create-saju-book", json=payload)

    assert response.status_code == 422


def test_missing_birth_time_requires_unknown_flag(client: TestClient) -> None:
    payload = valid_payload()
    payload["birth_time"] = None

    response = client.post("/api/v1/create-saju-book", json=payload)

    assert response.status_code == 422


def test_leap_month_requires_lunar_calendar(client: TestClient) -> None:
    payload = valid_payload()
    payload["is_leap_month"] = True

    response = client.post("/api/v1/create-saju-book", json=payload)

    assert response.status_code == 422
    assert "윤달" in response.text


def test_valid_lunar_leap_month_is_converted(client: TestClient) -> None:
    payload = valid_payload()
    payload.update(
        birth_date="2023-02-01",
        calendar_type="lunar",
        is_leap_month=True,
    )

    created = client.post("/api/v1/create-saju-book", json=payload)
    progress = client.get(
        "/api/v1/progress",
        params={"task_id": created.json()["task_id"]},
        headers={"Authorization": f"Bearer {created.json()['access_token']}"},
    )

    assert created.status_code == 202
    profile = progress.json()["analysis_result"]["saju_profile"]
    assert profile["solar_birth"].startswith("2023-03-22")
    assert profile["is_leap_month"] is True


def test_invalid_lunar_day_returns_422(client: TestClient) -> None:
    payload = valid_payload()
    payload.update(birth_date="1990-05-31", calendar_type="lunar")

    response = client.post("/api/v1/create-saju-book", json=payload)

    assert response.status_code == 422
    assert "음력 날짜" in response.text


def test_unknown_task_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/progress", params={"task_id": "missing-task"})

    assert response.status_code == 404


def test_gemini_failure_is_visible_when_local_fallback_is_used(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_gemini(*args: object, **kwargs: object) -> dict[str, object]:
        raise GeminiGenerationError("테스트용 Gemini 오류")

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setattr(main_module, "generate_gemini_analysis", fail_gemini)

    created = client.post("/api/v1/create-saju-book", json=valid_payload())
    progress = client.get(
        "/api/v1/progress",
        params={"task_id": created.json()["task_id"]},
        headers={"Authorization": f"Bearer {created.json()['access_token']}"},
    )

    assert progress.status_code == 200
    body = progress.json()
    assert body["status"] == "completed_with_errors"
    assert body["analysis_result"]["generation_mode"] == "local_fallback"
    assert "Gemini" in " ".join(body["warnings"])
