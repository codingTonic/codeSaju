import asyncio
from datetime import date
import json
from pathlib import Path
import sys
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import main, security, yeoul, yeoul_routes
from app.gemini import GeminiGenerationError


def payload(**overrides):
    return dict(
        name="가상 검증",
        birth_date="1990-05-15",
        birth_time="09:30",
        gender="female",
        topic="career",
        processing_consent=True,
        privacy_policy_version="2026-09-08",
        age_confirmed=True,
        **overrides,
    )


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    main.tasks.clear()
    security.admission.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-secret")
    monkeypatch.setenv("GEMINI_MODEL", "unit-test-model")
    monkeypatch.setenv("EMAIL_NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("ALLOW_FREE_DEVELOPMENT_READINGS", "true")
    yield
    main.tasks.clear()
    security.admission.clear()


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_confirmed", False),
        ("age_confirmed", "true"),
        ("processing_consent", False),
        ("privacy_policy_version", "2026-09-07"),
        ("birth_date", "2020-05-15"),
        ("partner_name", "다른 사람"),
    ],
)
def test_consent_age_and_third_party_inputs_fail_before_cost(field, value):
    body = payload()
    body[field] = value
    response = TestClient(main.app).post("/api/v2/readings", json=body)
    assert response.status_code == 422
    assert not main.tasks and not security.admission.daily
    assert "가상 검증" not in response.text


def test_optional_relationship_and_unknown_time_calculation():
    p = payload()
    p.pop("birth_time")
    p["birth_time_unknown"] = True
    request = yeoul.ReadingRequest(**p)
    profile = yeoul.build_saju_profile(request)
    assert request.relationship_status == "unspecified"
    assert not profile["time_known"] and len(profile["pillars"]) == 3
    assert "time" not in {f["id"] for f in yeoul.facts_for(profile)}
    context = yeoul.context_for(request, profile)
    assert "1990-05-15" not in context
    assert "09:30" not in context


def test_interactions_completed_steps_extract_text_only():
    body = {
        "status": "completed",
        "steps": [
            {"type": "thought", "content": [{"type": "text", "text": "hidden"}]},
            {
                "type": "model_output",
                "content": [{"type": "text", "text": '{"answer":1}'}],
            },
        ],
    }
    assert yeoul.extract_json(body) == {"answer": 1}
    body["status"] = "in_progress"
    with pytest.raises(GeminiGenerationError):
        yeoul.extract_json(body)


def test_long_chapter_guards_reject_missing_basis_short_and_repeated_content():
    report = json.loads(
        (Path(__file__).resolve().parents[1] / "frontend/app/example.json").read_text()
    )
    c = report["chapters"][0]
    data = {k: v for k, v in c.items() if k not in {"id", "category"}}
    assert yeoul.validate_chapter(data, c["id"], report["facts"])
    for broken in [
        dict(data, basis=["unknown_fact"]),
        dict(data, paragraphs=["짧은 내용"] * 4),
        dict(data, paragraphs=[data["paragraphs"][0]] * 4),
    ]:
        with pytest.raises((ValidationError, ValueError)):
            yeoul.validate_chapter(broken, c["id"], report["facts"])


def test_missing_key_fails_closed_without_using_local_template(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("AI_PROVIDER", "local_template")
    response = TestClient(main.app).post("/api/v2/readings", json=payload())
    assert response.status_code == 503 and not main.tasks


def test_reading_authorization_followups_limit_and_deletion(monkeypatch):
    async def fake_reading(request, progress):
        progress(8, 8)
        return {"version": 2, "name": request.name, "followups": []}

    async def fake_answer(request, report, question):
        return {
            "question": question,
            "paragraphs": ["답변"],
            "basis": ["center"],
            "reflection": "확인해보세요.",
        }

    monkeypatch.setattr(yeoul_routes, "generate_reading", fake_reading)
    monkeypatch.setattr(yeoul_routes, "answer_followup", fake_answer)
    monkeypatch.setattr(security, "RATE_REQUESTS", 20)
    client = TestClient(main.app)
    created = client.post("/api/v2/readings", json=payload()).json()
    taskid = created["task_id"]
    headers = {"Authorization": "Bearer " + created["access_token"]}
    route = f"/api/v2/readings/{taskid}/questions"
    assert (
        client.post(route, json={"question": "어떤 일을 살펴볼까요?"}).status_code
        == 404
    )
    result = client.get("/api/v1/progress", params={"task_id": taskid}, headers=headers)
    assert result.json()["status"] == "completed"
    assert (
        "reading_input" not in result.text
        and "access_digest" not in result.text
        and "unit-test-secret" not in result.text
    )
    assert main.tasks[taskid]["reading_input"].email_notification_consent is False
    for remaining in range(4, -1, -1):
        response = client.post(
            route, json={"question": "어떤 일을 살펴볼까요?"}, headers=headers
        )
        assert response.status_code == 200 and response.json()["remaining"] == remaining
    assert (
        client.post(
            route, json={"question": "다른 이야기도 해주세요."}, headers=headers
        ).status_code
        == 429
    )
    assert not security.admission.active and taskid not in main.running_jobs
    assert client.delete(f"/api/v1/tasks/{taskid}", headers=headers).status_code == 204
    assert (
        client.post(
            route, json={"question": "어떤 일을 살펴볼까요?"}, headers=headers
        ).status_code
        == 404
    )


def test_failed_generation_never_becomes_a_short_completed_example(monkeypatch):
    async def fail(*args):
        raise GeminiGenerationError("provider failure")

    monkeypatch.setattr(yeoul_routes, "generate_reading", fail)
    client = TestClient(main.app)
    created = client.post("/api/v2/readings", json=payload()).json()
    task = main.tasks[created["task_id"]]
    assert task["status"] == "failed" and "analysis_result" not in task
    assert not security.admission.active


def test_request_json_does_not_store_conversation_or_follow_redirects(monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": '{"ok":true}'}],
                    }
                ],
            },
        )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False
        ) as client:
            value, _ = await yeoul.request_json(
                client, "synthetic", {"type": "object"}, lambda d: d
            )
            assert value == {"ok": True}

    asyncio.run(run())
    assert len(seen) == 1 and seen[0]["store"] is False
    assert "previous_interaction_id" not in seen[0]


def test_production_requires_paid_data_processing_confirmation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("GEMINI_PAID_SERVICE_CONFIRMED", raising=False)
    response = TestClient(main.app).post("/api/v2/readings", json=payload())
    assert response.status_code == 503 and not main.tasks


def test_all_five_followups_are_available_after_creation_under_default_ip_limit(
    monkeypatch,
):
    async def generated(*args):
        return {"version": 2, "followups": []}

    async def answered(*args):
        return {"paragraphs": ["검증 답변"]}

    monkeypatch.setattr(yeoul_routes, "generate_reading", generated)
    monkeypatch.setattr(yeoul_routes, "answer_followup", answered)
    monkeypatch.setattr(security, "RATE_REQUESTS", 5)
    client = TestClient(main.app)
    created = client.post("/api/v2/readings", json=payload()).json()
    for i in range(5):
        response = client.post(
            f"/api/v2/readings/{created['task_id']}/questions",
            json={"question": f"후속 질문 {i}번째입니다."},
            headers={"Authorization": "Bearer " + created["access_token"]},
        )
        assert response.status_code == 200
    assert len(security.admission.daily) == 6


def test_personal_question_is_not_repeated_in_unrelated_chapters():
    request = yeoul.ReadingRequest(
        **payload(focus_concern="개인적인 진로 고민의 고유한 문장")
    )
    profile = yeoul.build_saju_profile(request)
    assert request.focus_concern in yeoul.context_for(request, profile)
    assert request.focus_concern not in yeoul.context_for(
        request, profile, include_question=False
    )


def test_solar_term_boundary_cannot_be_relabelled_as_previous_day():
    report = json.loads(
        (Path(__file__).resolve().parents[1] / "frontend/app/example.json").read_text()
    )
    chapter = next(c for c in report["chapters"] if c["id"] == "season")
    data = {k: v for k, v in chapter.items() if k not in {"id", "category"}}
    data["paragraphs"] = [
        data["paragraphs"][0] + " 다음 절기의 전날입니다.",
        *data["paragraphs"][1:],
    ]
    with pytest.raises(ValueError, match="절기 경계"):
        yeoul.validate_chapter(data, "season", report["facts"])


def test_lunar_age_uses_converted_solar_birthday(monkeypatch):
    monkeypatch.setattr(yeoul, "analysis_today", lambda: date(2026, 9, 8))
    p = payload()
    p["birth_date"] = "2008-09-01"
    p["calendar_type"] = "lunar"
    with pytest.raises(ValueError, match="18세"):
        yeoul.ReadingRequest(**p)


def test_legacy_create_cannot_bypass_v2_policy_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    body = payload()
    body.update(privacy_policy_version="2026-09-07", relationship_status="single")
    assert (
        TestClient(main.app).post("/api/v1/create-saju-book", json=body).status_code
        == 410
    )
    assert not main.tasks
