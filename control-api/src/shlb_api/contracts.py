from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import Request


def utc_now() -> datetime:
    return datetime.now(UTC)


def isoformat(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def resource_envelope(request: Request, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "request_id": request.state.correlation_id,
            "generated_at": isoformat(),
        },
    }


def list_envelope(
    request: Request,
    data: list[dict[str, Any]],
    *,
    limit: int,
    next_cursor: str | None,
) -> dict[str, Any]:
    return {
        "data": data,
        "page": {"next_cursor": next_cursor, "limit": limit},
        "meta": {
            "request_id": request.state.correlation_id,
            "generated_at": isoformat(),
        },
    }


def encode_cursor(created_at: datetime, identifier: str) -> str:
    precise_created_at = (
        created_at.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    payload = json.dumps(
        {"created_at": precise_created_at, "id": identifier},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        created_at = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
        identifier = str(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is malformed") from exc
    return created_at, identifier
