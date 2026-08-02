# Self Healing Load Balancer

Self Healing Load Balancer is a local traffic-reliability control-plane laboratory and operator console. Its Phase 1 data plane proves that one physical backend can participate in several logical HAProxy route pools and that Runtime operations can target one route membership without changing its siblings. Phase 2 adds the authenticated domain, persistence, API, audit, and event foundations without giving the API any traffic-control authority.

The research mechanism remains Evidence-Bounded Minimum-Scope Healing (EBMSH). HAProxy health checks and Runtime weight/state operations are enabling mechanisms, not the claimed innovation.

## Repository layout

```text
.
├── FRONTEND_UX_DESIGN.md          # Operator-console design contract; precedes UI code
├── control-api/                   # FastAPI REST/SSE role; PostgreSQL/Redis, no actuator access
│   ├── alembic/                   # Forward/reverse domain migrations
│   ├── src/shlb_api/              # Identity, registry, RBAC, audit, idempotency, SSE
│   └── tests/                     # Contract and PostgreSQL constraint checks
├── control-worker/                # Future sole-writer worker process role
│   └── src/
├── demo-backend/                  # Deterministic black-box laboratory target image
├── docs/design/                   # Frozen 21-part architecture dossier
├── frontend/                      # Next.js/TypeScript operator console (static export)
│   ├── app/                       # Public and authenticated route trees
│   ├── components/                # Console shell and operational views
│   └── lib/                       # Typed contracts, fixtures, and route inventory
├── haproxy/
│   ├── Dockerfile                 # HAProxy 3.2 LTS image plus Runtime test client
│   ├── dataplaneapi.yml           # Data Plane API bound only to control_net
│   └── haproxy.cfg                # Four route pools × three physical instances
├── nginx/
│   ├── Dockerfile                 # Builds the console, then creates the TLS edge image
│   ├── nginx.conf                 # UI, /api, and application routing
│   └── 40-generate-lab-cert.sh    # Ephemeral self-signed lab certificate
├── scripts/
│   ├── init_phase2_secrets.sh     # Idempotent local secret bootstrap; prints no values
│   ├── test_phase1_isolation.py   # Read/write/readback/restore Runtime test
│   └── test_phase2_foundation.py  # Auth/RBAC/API/SSE/persistence/isolation test
└── docker-compose.yml             # Isolated edge, backend, control, and data networks
```

`control-api` and `control-worker` are two process roles of one Python modular monolith, not independent domain microservices. Only the API role exists in Phase 2. The future sole-writer worker remains absent.

## Run the Phase 2 foundation

```sh
./scripts/init_phase2_secrets.sh
docker compose up --build -d
./scripts/test_phase2_foundation.py
python3 scripts/test_phase1_isolation.py
```

The edge is available at `https://localhost:8443`. The generated certificate is self-signed and intended only for this isolated local lab. HTTP on port `8080` redirects to TLS.

The root serves the product landing page. Sign-in is at `/login`; the authenticated operator console is at `/app`. The bootstrap account is `admin@shlb.local`, with its generated local password stored in `.secrets/bootstrap_password`. The labelled fixture tour remains available at `/app?demo=1`. The original static-delivery diagnostic purpose is preserved at `/diagnostics/phase-1`.

The versioned OpenAPI document is available at `https://localhost:8443/api/v1/openapi.json`, with interactive local documentation at `/api/v1/docs`.

Sample black-box requests:

```sh
curl --insecure https://localhost:8443/public
curl --insecure https://localhost:8443/auth
curl --insecure https://localhost:8443/catalog
curl --insecure https://localhost:8443/checkout
```

The test changes only `be_checkout/srv_inst_b`, confirms the three other B memberships are byte-for-byte unchanged across the stable Runtime control fields, and restores the original weight in a `finally` path.

## Frontend development

```sh
cd frontend
npm install
npm run verify
npm run dev
```

The console is light-first, supports light/dark/system themes, and statically exports all public and console routes. Phase 2 connects server-side sessions, environment/capability status, and SSE connection state. Traffic telemetry, incident/action lifecycles, HAProxy observed state, and healing remain explicit typed fixtures. Write controls cannot claim or perform a routing change.

## Phase 2 boundaries

- No target-side SDK, JavaScript, tracking tag, or application modification is required or modeled.
- Data Plane API is reachable only on the internal `control_net`; it is not published to the host.
- The Runtime Unix socket is not published over TCP.
- PostgreSQL and Redis are private to `control_data_net` and have no host-published ports.
- The API joins `edge_net` and `control_data_net`, but not `control_net` or `backend_net`.
- The API has no HAProxy credential, Runtime socket, Docker socket, host execution path, or routing mutation endpoint.
- Stored registry intent is returned as desired state. Observed HAProxy state is explicitly `UNKNOWN`.
- Sessions are opaque Redis records delivered through Secure, HttpOnly, SameSite=Strict cookies; mutating requests also require a session-bound CSRF token and allowed Origin.
- Project scope denial is intentionally returned as `404`; creates are idempotent; mutable entities require `If-Match`; audit records are append-only and events use a PostgreSQL outbox before Redis/SSE publication.
- The validated traffic pair is HAProxy `3.2.21` with its bundled Data Plane API `3.2.13`. Base images are pinned by implementation-time tag and resolved multi-architecture digest.

## Verification

```sh
docker compose run --rm --no-deps \
  -v "$PWD/control-api/tests:/app/tests:ro" \
  --entrypoint pytest control-api -q -p no:cacheprovider /app/tests
docker compose exec -T control-api alembic check
./scripts/test_phase2_foundation.py
python3 scripts/test_phase1_isolation.py
cd frontend && npm run verify
```
