from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from shlb_api.contracts import resource_envelope
from shlb_api.database import get_db
from shlb_api.dependencies import AuthContext, get_auth_context, require_csrf
from shlb_api.models import Team, TeamMembership, User
from shlb_api.problem import ApiProblem
from shlb_api.runtime import get_redis
from shlb_api.schemas import LoginRequest
from shlb_api.security import (
    dummy_password_hash,
    encode_session,
    new_csrf_token,
    new_session_id,
    session_key,
    stable_hash,
    unix_time,
    verify_password,
)
from shlb_api.settings import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _apply_login_rate_limit(redis_client: Redis, request: Request, email: str) -> None:
    address = request.client.host if request.client else "unknown"
    windows = (
        (f"ratelimit:login:ip:{stable_hash(address)}", 60, 12),
        (f"ratelimit:login:account:{stable_hash(email)}", 600, 10),
    )
    for key, ttl, maximum in windows:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, ttl)
        if count > maximum:
            raise ApiProblem(
                status=429,
                code="RATE_LIMITED",
                title="Sign-in temporarily limited",
                detail="Too many sign-in attempts. Wait before trying again.",
                retryable=True,
                headers={"Retry-After": str(ttl)},
            )


def _scope_rows(db: Session, user_id) -> list[dict[str, str]]:
    rows = db.execute(
        select(TeamMembership, Team)
        .join(Team, Team.id == TeamMembership.team_id)
        .where(TeamMembership.user_id == user_id)
        .order_by(Team.slug)
    ).all()
    return [
        {
            "team_id": str(membership.team_id),
            "team_name": team.name,
            "team_slug": team.slug,
            "role": membership.role,
        }
        for membership, team in rows
    ]


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    settings = get_settings()
    _apply_login_rate_limit(redis_client, request, payload.email)
    user = db.scalar(select(User).where(User.email_normalized == payload.email))
    password_hash = user.password_hash if user else dummy_password_hash()
    valid, needs_rehash = verify_password(password_hash, payload.password)
    if not user or not valid or user.status != "ACTIVE":
        raise ApiProblem(
            status=401,
            code="INVALID_CREDENTIALS",
            title="Sign-in failed",
            detail="The supplied credentials could not be authenticated.",
        )

    if needs_rehash:
        from shlb_api.security import hash_password

        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(UTC)

    session_id = new_session_id()
    csrf_token = new_csrf_token()
    now = unix_time()
    absolute_expires_at = now + settings.session_absolute_seconds
    redis_client.setex(
        session_key(session_id),
        settings.session_idle_seconds,
        encode_session(
            {
                "user_id": str(user.id),
                "auth_version": user.auth_version,
                "csrf_token": csrf_token,
                "created_at": now,
                "absolute_expires_at": absolute_expires_at,
            }
        ),
    )
    db.commit()
    response.set_cookie(
        key=settings.cookie_name,
        value=session_id,
        max_age=settings.session_absolute_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/",
        domain=settings.cookie_domain,
    )
    response.headers["Cache-Control"] = "no-store"
    return resource_envelope(
        request,
        {
            "user": {
                "id": str(user.id),
                "email": user.email_normalized,
                "status": user.status,
            },
            "scopes": _scope_rows(db, user.id),
            "csrf_token": csrf_token,
            "session": {
                "idle_seconds": settings.session_idle_seconds,
                "absolute_expires_at": datetime.fromtimestamp(
                    absolute_expires_at,
                    tz=UTC,
                ).isoformat().replace("+00:00", "Z"),
            },
        },
    )


@router.get("/me")
def me(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    return resource_envelope(
        request,
        {
            "user": {
                "id": str(auth.user.id),
                "email": auth.user.email_normalized,
                "status": auth.user.status,
            },
            "scopes": _scope_rows(db, auth.user.id),
            "csrf_token": auth.csrf_token,
        },
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    redis_client: Redis = Depends(get_redis),
):
    settings = get_settings()
    redis_client.delete(session_key(auth.session_id))
    response.delete_cookie(
        key=settings.cookie_name,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/",
        domain=settings.cookie_domain,
    )
    response.headers["Cache-Control"] = "no-store"
    return resource_envelope(request, {"signed_out": True})
