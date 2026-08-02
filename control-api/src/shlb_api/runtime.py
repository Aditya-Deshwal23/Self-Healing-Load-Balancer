from __future__ import annotations

from functools import lru_cache

import redis
import redis.asyncio as redis_async

from shlb_api.settings import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=2,
        health_check_interval=30,
    )


@lru_cache
def get_async_redis() -> redis_async.Redis:
    return redis_async.Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=20,
        health_check_interval=30,
    )
