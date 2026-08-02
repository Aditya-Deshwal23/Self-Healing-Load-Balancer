from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from shlb_api.contracts import utc_now
from shlb_api.database import get_session_factory
from shlb_api.models import ControllerGeneration
from shlb_api.seed import IDS


with get_session_factory()() as db:
    row = db.scalar(select(ControllerGeneration).where(ControllerGeneration.environment_id == IDS["environment"]).order_by(ControllerGeneration.generation.desc()).limit(1))
    if row is None or row.status != "ACTIVE" or row.last_heartbeat_at < utc_now() - timedelta(seconds=10):
        raise SystemExit(1)
