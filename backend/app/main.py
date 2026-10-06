from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import secrets
from datetime import UTC, datetime, timedelta
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .analysis import build_local_analysis
from .email_service import (
    deliver_user_info_notification,
    get_email_settings,
    initial_delivery_status,
)
from .gemini import (
    GeminiConfigurationError,
    GeminiGenerationError,
    generate_gemini_analysis,
    get_gemini_settings,
)
from .models import HealthResponse, SajuRequest, TaskAccepted


LOGGER = logging.getLogger("personal_os")
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

from .security import RequestSecurityMiddleware, admission, token_digest, TASK_TIMEOUT_SECONDS

TASK_RETENTION = timedelta(hours=24)
ANALYSIS_STEP_DELAY_SECONDS = max(float(os.getenv("ANALYSIS_STEP_DELAY_SECONDS", "0.2")), 0.0)


def get_ai_provider() -> str:
    return os.getenv("AI_PROVIDER", "local_template").strip().lower()


def local_fallback_enabled() -> bool:
    return os.getenv("LOCAL_FALLBACK_ON_AI_ERROR", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def utc_now() -> datetime:
    return datetime.now(UTC)


tasks: dict[str, dict[str, Any]] = {}
running_jobs: dict[str, asyncio.Task] = {}
TASK_SWEEP_SECONDS = 60


def cleanup_expired_tasks() -> None:
    cutoff = utc_now() - TASK_RETENTION
    expired = [task_id for task_id, task in tasks.items() if task["created_at"] < cutoff]
    for task_id in expired:
        tasks.pop(task_id, None)
        job = running_jobs.get(task_id)
        if job:
            job.cancel()
    admission.cleanup()


async def generate_analysis_task(task_id: str, request: SajuRequest) -> None:
    task = tasks.get(task_id)
    if not task:
        return

    try:
        task.update(status="processing", percent_overall=10)
        provider = get_ai_provider()

        if provider == "gemini":
            task.update(percent_overall=25)
            analysis_result = await generate_gemini_analysis(
                task_id,
                request,
                progress_callback=lambda completed, total: task.update(
                    percent_overall=25 + round((completed / total) * 65)
                ),
            )
            task.update(percent_overall=90)
        elif provider == "local_template":
            for percent in (35, 65, 90):
                await asyncio.sleep(ANALYSIS_STEP_DELAY_SECONDS)
                task.update(percent_overall=percent)
            analysis_result = build_local_analysis(task_id, request)
        else:
            raise GeminiConfigurationError(
                f"지원하지 않는 AI_PROVIDER입니다: {provider or '(비어 있음)'}"
            )

        task.update(
            status="completed",
            percent_overall=100,
            analysis_result=analysis_result,
            completed_at=utc_now(),
        )
        LOGGER.info(
            "Analysis completed",
            extra={"task_id": task_id, "provider": provider},
        )
    except (GeminiConfigurationError, GeminiGenerationError):
        LOGGER.warning("AI analysis failed", extra={"task_id": task_id})
        if local_fallback_enabled():
            task.update(
                status="completed_with_errors",
                percent_overall=100,
                analysis_result=build_local_analysis(
                    task_id,
                    request,
                    generation_mode="local_fallback",
                ),
                warnings=[
                    "Gemini 분석에 실패해 로컬 예시 결과를 표시합니다.",
                ],
                completed_at=utc_now(),
            )
            return
        task.update(
            status="failed",
            error="AI 분석을 완료하지 못했습니다. 잠시 후 다시 시도해주세요.",
            completed_at=utc_now(),
        )
    except Exception:
        LOGGER.error("Analysis failed", extra={"task_id": task_id})
        task.update(
            status="failed",
            error="분석 결과를 생성하지 못했습니다.",
            completed_at=utc_now(),
        )


async def process_saju_request(task_id: str, request: SajuRequest) -> None:
    async def deliver_notification() -> None:
        delivery_status = await deliver_user_info_notification(task_id, request)
        task = tasks.get(task_id)
        if task:
            task["email_notification"] = delivery_status

    async def run():
        # A task group cancels sibling work when one operation fails or is deleted.
        async with asyncio.TaskGroup() as group:
            group.create_task(generate_analysis_task(task_id, request))
            group.create_task(deliver_notification())

    if task_id not in tasks:
        admission.active.discard(task_id)
        return
    job = asyncio.create_task(run())
    running_jobs[task_id] = job
    try:
        await asyncio.wait_for(job, timeout=TASK_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        job.cancel()
    except Exception:
        LOGGER.error("Analysis job stopped", extra={"task_id": task_id})
        if task_id in tasks:
            tasks[task_id].update(status="failed", percent_overall=100,
                                 error="분석을 완료하지 못했습니다. 잠시 후 다시 시도해주세요.",
                                 completed_at=utc_now())
    finally:
        running_jobs.pop(task_id, None)
        admission.active.discard(task_id)


async def sweep_expired_tasks() -> None:
    while True:
        cleanup_expired_tasks()
        await asyncio.sleep(TASK_SWEEP_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper = asyncio.create_task(sweep_expired_tasks())
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        jobs = list(running_jobs.values())
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        tasks.clear()
        admission.clear()


production = os.getenv("APP_ENV", "development") == "production"
app = FastAPI(
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
    title="여울 API",
    version="2.0.0",
    description="Question-led Saju readings and follow-up conversations with Gemini.",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        (
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:3001,http://127.0.0.1:3001,"
            "http://localhost:3005,http://127.0.0.1:3005"
        ),
    ).split(",")
    if origin.strip()
]
allowed_hosts = [host.strip() for host in os.getenv(
    "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver"
).split(",") if host.strip()]
if production and (
    not os.getenv("ALLOWED_HOSTS") or not os.getenv("CORS_ORIGINS")
    or "*" in allowed_hosts or any(not origin.startswith("https://") for origin in cors_origins)
):
    raise RuntimeError("Production requires explicit ALLOWED_HOSTS and HTTPS CORS_ORIGINS")
if "*" in cors_origins or "null" in cors_origins:
    raise RuntimeError("Explicit browser origins are required")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(RequestSecurityMiddleware, allowed_origins=cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Retry-After"],
)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "Personal OS API", "docs": "/docs"}


@app.get("/api/v1/", include_in_schema=False)
async def api_root() -> dict[str, object]:
    return {
        "endpoints": {
            "create_saju_book": "POST /api/v1/create-saju-book",
            "health": "GET /api/v1/health",
            "progress": "GET /api/v1/progress?task_id=...",
        }
    }


@app.get("/api/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    provider = get_ai_provider()
    email_settings = get_email_settings()
    email_degraded = email_settings.enabled and not email_settings.configured
    if provider == "local_template":
        return HealthResponse(
            status="degraded" if email_degraded else "healthy",
            mode=provider,
            durable_tasks=False,
            ai_configured=False,
            email_enabled=email_settings.enabled,
            email_configured=email_settings.configured,
        )
    if provider == "gemini":
        try:
            get_gemini_settings()
        except GeminiConfigurationError:
            return HealthResponse(
                status="degraded",
                mode=provider,
                durable_tasks=False,
                ai_configured=False,
                email_enabled=email_settings.enabled,
                email_configured=email_settings.configured,
            )
        return HealthResponse(
            status="degraded" if email_degraded else "healthy",
            mode=provider,
            durable_tasks=False,
            ai_configured=True,
            email_enabled=email_settings.enabled,
            email_configured=email_settings.configured,
        )
    return HealthResponse(
        status="degraded",
        mode=provider or "unconfigured",
        durable_tasks=False,
        ai_configured=False,
        email_enabled=email_settings.enabled,
        email_configured=email_settings.configured,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default response can echo the entire submitted personal input.
    allowed_messages = {
        "개인정보 처리 안내를 확인하고 분석에 동의해주세요.",
        "만 18세 이상인 경우에 이용할 수 있습니다.", "현재 버전에서는 본인의 정보만 입력해주세요.",
        "생년월일은 1900-01-01부터 오늘 사이여야 합니다.", "올바른 MBTI 형식이 아닙니다.",
        "태어난 시간을 입력하거나 시간 모름을 선택해주세요.",
        *(f"{subject}의 윤달은 음력을 선택했을 때만 사용할 수 있습니다." for subject in ("본인", "연인")),
        *(f"{subject}의 음력 날짜를 변환할 수 없습니다. 날짜와 윤달 여부를 확인해주세요." for subject in ("본인", "연인")),
    }
    errors = []
    for error in exc.errors():
        message = error.get("msg", "").removeprefix("Value error, ")
        errors.append({"loc": error["loc"], "type": error["type"], "msg": message if message in allowed_messages
                       else "입력값의 형식과 허용 범위를 확인해주세요."})
    return JSONResponse({"detail": errors}, status_code=422)


@app.post(
    "/api/v1/create-saju-book",
    response_model=TaskAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_saju_book(
    request: SajuRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> TaskAccepted:
    if os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(410, detail="새 여울 화면에서 풀이를 시작해주세요.")
    if not request.processing_consent or request.privacy_policy_version != "2026-09-07":
        raise HTTPException(422, detail=[{
            "loc": ["body", "processing_consent"], "type": "consent_required",
            "msg": "개인정보 처리 안내를 확인하고 분석에 동의해주세요.",
        }])
    cleanup_expired_tasks()
    task_id = str(uuid4())
    admission.admit(http_request.client.host if http_request.client else "unknown", task_id, len(tasks))
    access_token = secrets.token_urlsafe(32)
    tasks[task_id] = {
        "task_id": task_id,
        "access_digest": token_digest(access_token),
        "status": "queued",
        "percent_overall": 0,
        "created_at": utc_now(),
        "consent": {"processing": True, "policy_version": request.privacy_policy_version,
                    "email": request.email_notification_consent, "at": utc_now()},
        "email_notification": initial_delivery_status(request),
    }
    background_tasks.add_task(process_saju_request, task_id, request)
    return TaskAccepted(task_id=task_id, status="queued", access_token=access_token)


def authorized_task(task_id: str, request: Request) -> dict[str, Any]:
    cleanup_expired_tasks()
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    task = tasks.get(task_id)
    supplied_digest = token_digest(token) if scheme.lower() == "bearer" and len(token) <= 128 else ""
    expected_digest = task.get("access_digest", "") if task else "0" * 64
    if not token or not secrets.compare_digest(supplied_digest, expected_digest) or not task:
        raise HTTPException(404, detail="작업이 만료되었거나 이 브라우저에 조회 권한이 없습니다.")
    return task


@app.get("/api/v1/progress")
async def progress(request: Request, task_id: str = Query(min_length=1, max_length=100)) -> dict[str, object]:
    task = authorized_task(task_id, request)
    public_fields = {"task_id", "status", "percent_overall", "analysis_result", "email_notification", "warnings", "error"}
    return {key: value for key, value in task.items() if key in public_fields}


@app.delete("/api/v1/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request) -> Response:
    authorized_task(task_id, request)
    tasks.pop(task_id, None)
    job = running_jobs.get(task_id)
    if job:
        job.cancel()
    return Response(status_code=204)

# The new experience shares the tested request guards and task lifecycle.
from .yeoul_routes import router as yeoul_router
app.include_router(yeoul_router)
from .commerce_routes import router as commerce_router
app.include_router(commerce_router)
