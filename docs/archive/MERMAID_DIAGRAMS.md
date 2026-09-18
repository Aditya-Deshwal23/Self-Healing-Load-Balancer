Archived: out of scope for the current single-environment lab prototype and the Phase 1 rule-only implementation (see CONTEXT/project-overview.md and CONTEXT/architecture.md). Kept for historical reference only.

# SHLB Research Diagrams

## SHLB autonomous healing lifecycle

```mermaid
sequenceDiagram
  participant Node as Backend node
  participant Metrics as Prometheus
  participant Logs as Logstash/Elasticsearch
  participant Worker as SHLB worker
  participant Ledger as PostgreSQL ledger
  participant Socket as HAProxy admin.sock
  participant Proxy as HAProxy data plane
  Node->>Metrics: latency/error/queue metrics
  Node->>Logs: semantic application and proxy logs
  Metrics-->>Worker: bounded evidence window
  Logs-->>Worker: correlated anomaly evidence
  Worker->>Worker: triangulate and classify scope
  Worker->>Ledger: PREPARED action + blast-radius certificate
  Worker->>Socket: set server state drain / weight
  Socket-->>Worker: runtime acknowledgement
  Worker->>Socket: show stat readback
  Socket-->>Worker: observed state
  Worker->>Ledger: verify, rollback, or NEEDS_REVIEW
  Proxy-->>Node: preserve active connections, reroute new traffic
```

## SHLB topology

```mermaid
flowchart TB
  subgraph PUBLIC["Public Network"]
    User["External clients"]
    DNS["Customer DNS / CNAME"]
  end
  subgraph EDGE["Edge and Data Plane Network"]
    Nginx["Nginx TLS edge"]
    HAProxy["HAProxy data plane"]
    CustomerOrigins["Customer BYOO origins"]
    DemoPool["Isolated demo-backend pool"]
    Socket[("/var/run/haproxy/admin.sock")]
  end
  subgraph FAST["Fast-Path IPC Boundary"]
    Worker["Python control-worker"]
    EWMA["In-memory EWMA + hysteresis"]
    Reserve["33% reserve guard"]
  end
  subgraph CONTROL["Control Plane Network"]
    API["FastAPI control API"]
    Ledger[("PostgreSQL action ledger")]
    SSE["SSE event broker"]
  end
  subgraph SLOW["Slow-Path Telemetry Network"]
    Prom["Prometheus"]
    Logstash["Logstash"]
    ES[("Elasticsearch")]
    Kibana["Kibana"]
  end
  subgraph AI["AI Diagnostic Plane"]
    Trigger["UNRECOVERABLE_STATE"]
    RAG["Minimal RAG provider adapter\nGoogle GenAI SDK or direct HTTP"]
    LLM["External LLM provider"]
    RCA["Markdown RCA report"]
  end
  subgraph UI["Frontend / Presentation Plane"]
    Frontend["React command center"]
    Sandbox["Presentation Sandbox"]
  end

  User -->|"HTTPS"| DNS
  DNS -->|"CNAME"| Nginx
  Nginx -->|"HTTP"| HAProxy
  HAProxy -->|"Weighted HTTP"| CustomerOrigins
  HAProxy -->|"Weighted HTTP"| DemoPool
  Nginx -.->|"Syslog"| Logstash
  HAProxy -.->|"Syslog"| Logstash
  Prom -.->|"Scrape"| HAProxy
  Prom -.->|"Scrape"| DemoPool
  Logstash -->|"Structured events"| ES
  Kibana -->|"Forensic queries"| ES

  Worker -->|"Poll: show stat / info"| Socket
  Socket -->|"Runtime samples"| EWMA
  EWMA --> Reserve
  Reserve -->|"Attenuation recommendation"| Worker
  Worker -->|"set server weight/state"| Socket
  Worker -->|"Durable action state"| Ledger
  Worker -.->|"Slow-path forensic context"| ES

  API -->|"SSE"| SSE
  SSE -->|"Live events"| Frontend
  Frontend -->|"Chaos / origin API"| API
  Sandbox -->|"Demo fault commands"| API
  API -->|"Scoped fault"| Worker

  Worker -->|"Capacity exhausted"| Trigger
  Trigger --> RAG
  RAG -->|"Redacted metrics + log signatures"| LLM
  LLM -->|"Validated Markdown"| RCA
  RCA -->|"rca_report SSE event"| SSE
  RCA -.->|"Advisory only"| Frontend
```
