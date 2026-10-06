"""Yeoul uses the existing bounded task lifecycle and bearer authorization."""

import asyncio
from uuid import uuid4
import secrets
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from .models import TaskAccepted
from .security import admission, token_digest, TASK_TIMEOUT_SECONDS
from .yeoul import ReadingRequest, FollowupRequest, generate_reading, answer_followup
from .chart import ChartRequest, build_chart, chart_admission
from .saju import SajuCalculationError

router = APIRouter(prefix="/api/v2")


@router.post("/chart")
async def chart_preview(payload: ChartRequest, request: Request):
    chart_admission.admit(request.client.host if request.client else "unknown")
    try:
        return build_chart(payload)
    except SajuCalculationError as exc:
        raise HTTPException(422, str(exc)) from exc


async def run_reading(task_id, payload):
    from .main import tasks, running_jobs, utc_now

    if task_id not in tasks:
        admission.active.discard(task_id)
        return
    task = tasks[task_id]
    task.update(status="processing", percent_overall=8)

    def progress(done, total):
        task.update(percent_overall=10 + round(done / total * 85))

    job = asyncio.create_task(generate_reading(payload, progress))
    running_jobs[task_id] = job
    try:
        report = await asyncio.wait_for(job, timeout=TASK_TIMEOUT_SECONDS)
        if task_id in tasks:
            task.update(
                status="completed",
                percent_overall=100,
                analysis_result=report,
                completed_at=utc_now(),
            )
    except asyncio.CancelledError:
        job.cancel()
    except Exception:
        if task_id in tasks:
            task.update(
                status="failed",
                error="풀이를 완성하지 못했습니다. 연결 상태를 확인하고 다시 시도해주세요. 짧은 예시로 대체하지 않았습니다.",
                completed_at=utc_now(),
            )
    finally:
        running_jobs.pop(task_id, None)
        admission.active.discard(task_id)


@router.post("/readings", status_code=202, response_model=TaskAccepted)
async def create_reading(
    payload: ReadingRequest, request: Request, background: BackgroundTasks
):
    from .main import tasks, utc_now, cleanup_expired_tasks
    from .gemini import get_gemini_settings, GeminiConfigurationError
    from .commerce import assert_development_readings_enabled

    assert_development_readings_enabled()

    if (
        os.getenv("APP_ENV", "").lower() == "production"
        and os.getenv("GEMINI_PAID_SERVICE_CONFIRMED", "").lower() != "true"
    ):
        raise HTTPException(
            503, "개인정보 처리 설정을 확인하고 있습니다. 잠시 후 다시 이용해주세요."
        )
    try:
        get_gemini_settings()
    except GeminiConfigurationError:
        raise HTTPException(
            503, "분석 서비스 설정을 확인하고 있습니다. 잠시 후 다시 이용해주세요."
        )
    cleanup_expired_tasks()
    task_id = str(uuid4())
    admission.admit(
        request.client.host if request.client else "unknown", task_id, len(tasks)
    )
    token = secrets.token_urlsafe(32)
    tasks[task_id] = {
        "task_id": task_id,
        "access_digest": token_digest(token),
        "status": "queued",
        "percent_overall": 0,
        "created_at": utc_now(),
        "reading_input": payload,
        "consent": {
            "processing": True,
            "policy_version": "2026-09-08",
            "email": False,
            "at": utc_now(),
        },
    }
    background.add_task(run_reading, task_id, payload)
    return TaskAccepted(task_id=task_id, access_token=token, status="queued")


@router.post("/readings/{task_id}/questions")
async def ask_question(task_id: str, payload: FollowupRequest, request: Request):
    from .main import authorized_task, tasks, running_jobs

    task = authorized_task(task_id, request)
    report = task.get("analysis_result")
    if task.get("status") != "completed" or not report or report.get("version") != 2:
        raise HTTPException(409, "풀이가 완성된 뒤 이어서 질문해주세요.")
    if task.get("question_busy"):
        raise HTTPException(409, "앞선 질문에 답하는 중입니다.")
    if len(report.get("followups", [])) >= 5:
        raise HTTPException(429, "한 풀이에서 질문할 수 있는 5회를 모두 사용했습니다.")
    job_id = "question:" + task_id
    admission.admit(
        (request.client.host if request.client else "unknown") + ":followup",
        job_id,
        len(tasks),
    )
    task["question_busy"] = True
    job = asyncio.create_task(
        answer_followup(task["reading_input"], report, payload.question)
    )
    running_jobs[task_id] = job
    try:
        answer = await asyncio.wait_for(job, timeout=240)
        if task_id not in tasks:
            raise HTTPException(404, "삭제되었거나 만료된 풀이입니다.")
        report["followups"].append(answer)
        return {"answer": answer, "remaining": 5 - len(report["followups"])}
    except asyncio.CancelledError:
        raise HTTPException(404, "풀이가 삭제되어 질문을 중단했습니다.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            502, "답변을 완성하지 못했습니다. 잠시 후 다시 질문해주세요."
        )
    finally:
        task["question_busy"] = False
        running_jobs.pop(task_id, None)
        admission.active.discard(job_id)
