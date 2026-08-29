# Architecture

## Scope

The implemented system is a local Docker Compose lab. Its data plane is separate from its control plane. NGINX is the only published edge service. HAProxy handles application traffic. The control worker alone has access to HAProxy's private Runtime socket and the private backend/observability networks.

## Overall Architecture

```mermaid
flowchart LR
    User[User or test client] --> NGINX[NGINX HTTPS edge]
    NGINX --> HAProxy[HAProxy]
    HAProxy --> A[Backend A]
    HAProxy --> B[Backend B]
    HAProxy --> C[Backend C]
    A --> Prometheus[Prometheus]
    B --> Prometheus
    C --> Prometheus
    HAProxy --> Prometheus
    Prometheus --> Worker[Single control worker]
    Worker --> Probe[Private direct probes]
    Probe --> A
    Probe --> B
    Probe --> C
    Worker --> Runtime[HAProxy Runtime socket]
    Runtime --> HAProxy
    Worker --> Postgres[(PostgreSQL)]
    Worker --> Redis[(Redis)]
    API[Control API] --> Postgres
    API --> Redis
    NGINX --> API
    API --> Console[Web console]
```

## Container Diagram

```mermaid
flowchart TB
    subgraph Host[Local host]
      Edge[edge-nginx :8080/:8443]
      subgraph Data[data_edge_net]
        H[traffic-haproxy]
        T[traffic-generator]
      end
      subgraph Private[Private networks]
        A[demo-backend-a]
        B[demo-backend-b]
        C[demo-backend-c]
        P[prometheus]
        W[control-worker]
        DB[(postgres)]
        R[(redis)]
        API[control-api]
      end
    end
    Edge --> H
    Edge --> API
    T --> H
    H --> A & B & C
    P --> H & A & B & C
    W --> P & A & B & C
    W --> H
    W --> DB & R
    API --> DB & R
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant NGINX
    participant HAProxy
    participant Backend as Healthy backend
    Client->>NGINX: HTTPS request to /checkout
    NGINX->>HAProxy: Forward application request
    HAProxy->>Backend: Select healthy server in be_checkout
    Backend-->>HAProxy: Application response
    HAProxy-->>NGINX: Response
    NGINX-->>Client: HTTPS response
```

## Monitoring Flow

```mermaid
flowchart LR
    Backends[Backend metrics] --> Prometheus
    HAStats[HAProxy metrics] --> Prometheus
    Traffic[Traffic generator] --> HAProxy[HAProxy]
    Prometheus --> Worker[Control worker]
    Probes[Direct probes] --> Worker
    Runtime[HAProxy Runtime readback] --> Worker
    Worker --> Evidence[Observation and evidence]
    Evidence --> Rules[Deterministic rule engine]
```

## Failure Recovery Flow

```mermaid
flowchart TD
    Failure[Checkout fails on backend B] --> Observe[Metrics, probes, and runtime readback]
    Observe --> Classify{Supported and sufficient evidence?}
    Classify -- No --> Review[Record or wait; no destructive action]
    Classify -- Yes --> Prepare[Persist action and desired state]
    Prepare --> Drain[Drain be_checkout/srv_inst_b]
    Drain --> Readback[Confirm HAProxy Runtime state]
    Readback --> Verify{Real requests healthy and peers preserved?}
    Verify -- No --> Rollback[Rollback or mark for review]
    Verify -- Yes --> Quarantined[Traffic stays on checkout A and C]
    Quarantined --> Clear[Fault cleared]
    Clear --> Stages[Reintegrate at 5%, 20%, 50%, 100%]
    Stages --> Healthy[Mark healthy after gates pass]
```

## Recovery Boundary

The demo application's `instance_down` fault makes the backend health endpoint fail. HAProxy then marks it unhealthy through its own checks. The control worker can also classify that supported case and drain the affected instance memberships. For the primary route-specific demo, the backend container remains running and only checkout on backend B fails. The recovery is a routing change, not a backend restart.
