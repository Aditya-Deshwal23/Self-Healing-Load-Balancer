from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.orm import Session

from shlb_api.contracts import isoformat
from shlb_api.database import get_db
from shlb_api.dependencies import AuthContext, get_auth_context, require_environment, require_project
from shlb_api.runtime import get_async_redis
from shlb_api.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["events"])


def _sse(*, event_id: str, event_type: str, payload: dict) -> str:
    encoded = json.dumps(payload, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event_type}\ndata: {encoded}\n\n"


@router.get("/events")
async def events(
    request: Request,
    project_id: uuid.UUID = Query(),
    environment_id: uuid.UUID | None = Query(default=None),
    types: str | None = Query(default=None, max_length=1000),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID", max_length=128),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    project = require_project(db, auth, project_id)
    if environment_id:
        environment, environment_project = require_environment(db, auth, environment_id)
        if environment_project.id != project.id:
            from shlb_api.problem import ApiProblem

            raise ApiProblem(
                status=404,
                code="NOT_FOUND",
                title="Environment not found",
                detail="No such environment exists in the selected project.",
            )
        del environment
    permitted_types = {
        value.strip()
        for value in (types or "").split(",")
        if value.strip()
    }
    redis_client: AsyncRedis = get_async_redis()
    stream_key = f"events:{project.id}"

    async def stream():
        cursor = "$"
        if last_event_id:
            mapped = await redis_client.get(
                f"eventcursor:{project.id}:{last_event_id}"
            )
            if mapped:
                cursor = mapped
            else:
                resync_id = str(uuid.uuid4())
                payload = {
                    "event_id": resync_id,
                    "event_type": "resync_required",
                    "event_version": 1,
                    "occurred_at": isoformat(),
                    "published_at": isoformat(),
                    "project_id": str(project.id),
                    "environment_id": str(environment_id) if environment_id else None,
                    "service_id": None,
                    "aggregate_type": "project",
                    "aggregate_id": str(project.id),
                    "aggregate_version": project.version,
                    "correlation_id": request.state.correlation_id,
                    "incident_id": None,
                    "action_id": None,
                    "data": {
                        "reason": "Last-Event-ID is outside retained cursor history.",
                        "required_action": "Refetch authorized REST resources.",
                    },
                }
                yield _sse(
                    event_id=resync_id,
                    event_type="resync_required",
                    payload=payload,
                )
        heartbeat = get_settings().event_heartbeat_seconds
        while True:
            if await request.is_disconnected():
                break
            try:
                records = await redis_client.xread(
                    {stream_key: cursor},
                    count=50,
                    block=heartbeat * 1000,
                )
            except asyncio.CancelledError:
                break
            if not records:
                yield f": heartbeat {isoformat()}\n\n"
                continue
            for _, entries in records:
                for stream_id, fields in entries:
                    cursor = stream_id
                    try:
                        payload = json.loads(fields["payload"])
                    except (KeyError, TypeError, json.JSONDecodeError):
                        continue
                    if environment_id and payload.get("environment_id") != str(environment_id):
                        continue
                    event_type = str(payload.get("event_type", "message"))
                    if permitted_types and event_type not in permitted_types:
                        continue
                    yield _sse(
                        event_id=str(payload["event_id"]),
                        event_type=event_type,
                        payload=payload,
                    )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
