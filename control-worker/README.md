# control-worker process role

Phase 4 will place the sole-writer reconciliation/actuation entry point here. It belongs to the same Python modular monolith as `control-api`, but only this process role may receive the HAProxy Runtime socket and Data Plane API authority.

No controller code is required for the Phase 1 manual isolation proof.

