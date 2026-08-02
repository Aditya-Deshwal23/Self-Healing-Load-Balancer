from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shlb_api.audit import publish_pending_outbox
from shlb_api.database import get_session_factory
from shlb_api.problem import ApiProblem, install_problem_handlers, problem_payload
from shlb_api.routers import auth, events, projects, registry, system
from shlb_api.runtime import get_redis
from shlb_api.settings import get_settings

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    settings = get_settings()
    del settings
    with get_session_factory()() as db:
        db.execute(text("SELECT 1"))
        get_redis().ping()
        publish_pending_outbox(db, get_redis())
    yield


app = FastAPI(
    title="Self Healing Load Balancer Control API",
    version="2.0.0-foundation",
    description=(
        "Phase 2 identity, registry, policy, audit, idempotency, and event contracts. "
        "This process has no HAProxy or host actuation authority."
    ),
    docs_url="/api/v1/docs",
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)
install_problem_handlers(app)


@app.middleware("http")
async def contract_middleware(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid.uuid4())
    request.state.correlation_id = request_id
    settings = get_settings()
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            too_large = int(content_length) > settings.request_body_limit
        except ValueError:
            too_large = True
        if too_large:
            problem = ApiProblem(
                status=413,
                code="PAYLOAD_TOO_LARGE",
                title="Request body is too large",
                detail="Ordinary API request bodies may not exceed 1 MiB.",
            )
            response = JSONResponse(
                status_code=413,
                content=problem_payload(request, problem),
                media_type="application/problem+json",
            )
            response.headers["X-Request-ID"] = request_id
            return response
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api/") and request.url.path != "/api/v1/events":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(registry.router)
app.include_router(events.router)
