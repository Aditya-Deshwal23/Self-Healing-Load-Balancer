#!/bin/sh
set -eu

alembic upgrade head
python -m shlb_api.seed
exec uvicorn shlb_api.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips="*"
