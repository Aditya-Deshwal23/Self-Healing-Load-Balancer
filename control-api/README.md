# Control API process role

This directory contains the Phase 2 FastAPI REST/SSE process. It belongs to the Python modular monolith but runs as an API-only role with PostgreSQL/Redis access and **no** HAProxy Runtime socket, Data Plane API credential, Docker socket, host execution path, or route to the actuation network.

Implemented foundations:

- Alembic migrations for users, teams, projects, environments, services, versions, physical backends, route groups, logical memberships, immutable policies, audit, outbox, and idempotency;
- deterministic seeding of the real Phase 1 topology: four route pools, three physical instances, and twelve logical memberships;
- opaque Redis sessions, Argon2 password verification, CSRF plus Origin validation, team-scoped RBAC, and scope-hiding `404` responses;
- standard resource/list envelopes, `application/problem+json`, correlation IDs, cursor pagination, ETags/`If-Match`, and idempotency keys;
- encrypted backend addresses at rest;
- append-only hash-chained audit records and PostgreSQL-outbox-to-Redis event publication;
- authenticated SSE with heartbeat, retained cursor mapping, and explicit `resync_required`;
- live/readiness endpoints and a capability contract that declares HAProxy authority absent.

The API never labels registry intent as observed traffic state. Membership reads return observed state as `UNKNOWN` until a future sole-writer reconciler performs HAProxy readback.

Run through the repository Compose stack:

```sh
./scripts/init_phase2_secrets.sh
docker compose up --build -d
./scripts/test_phase2_foundation.py
```
