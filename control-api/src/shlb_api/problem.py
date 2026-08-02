from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("shlb_api")


@dataclass
class ApiProblem(Exception):
    status: int
    code: str
    title: str
    detail: str
    errors: list[dict[str, str]] = field(default_factory=list)
    retryable: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def problem_payload(request: Request, problem: ApiProblem) -> dict[str, Any]:
    return {
        "type": f"https://shlb.local/problems/{problem.code.lower().replace('_', '-')}",
        "title": problem.title,
        "status": problem.status,
        "code": problem.code,
        "detail": problem.detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "correlation_id", "unavailable"),
        "errors": problem.errors,
        "retryable": problem.retryable,
    }


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def handle_api_problem(request: Request, exc: ApiProblem) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=problem_payload(request, exc),
            media_type="application/problem+json",
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part not in {"body", "query", "path"}),
                "reason": str(error["msg"]),
            }
            for error in exc.errors()
        ]
        problem = ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Request validation failed",
            detail="One or more request fields do not satisfy the API contract.",
            errors=errors,
        )
        return JSONResponse(
            status_code=422,
            content=problem_payload(request, problem),
            media_type="application/problem+json",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        problem = ApiProblem(
            status=exc.status_code,
            code=code,
            title="Resource not found" if exc.status_code == 404 else "Request failed",
            detail="No API resource matches this request." if exc.status_code == 404 else str(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_payload(request, problem),
            media_type="application/problem+json",
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled control API error request_id=%s path=%s",
            getattr(request.state, "correlation_id", "unavailable"),
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        problem = ApiProblem(
            status=500,
            code="INTERNAL_ERROR",
            title="Internal control API error",
            detail="The request could not be completed. Use the request ID for operator correlation.",
            retryable=False,
        )
        return JSONResponse(
            status_code=500,
            content=problem_payload(request, problem),
            media_type="application/problem+json",
        )
