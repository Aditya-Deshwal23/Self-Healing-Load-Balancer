FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 12001 shlb-api \
    && useradd --system --uid 12001 --gid shlb-api --home-dir /nonexistent --shell /usr/sbin/nologin shlb-api

COPY control-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement /app/requirements.txt

COPY control-api/alembic.ini /app/alembic.ini
COPY control-api/alembic /app/alembic
COPY control-api/src /app/src
COPY control-api/entrypoint.sh /app/entrypoint.sh

RUN chmod 0555 /app/entrypoint.sh \
    && chown -R shlb-api:shlb-api /app

USER shlb-api

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
