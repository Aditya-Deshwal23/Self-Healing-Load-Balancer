# Future Scope

None of the items below are implemented in the current prototype.

## Machine Learning Prediction

Use historical metrics to identify patterns that may precede a failure. Any model would need clear evaluation data and a safe fallback to deterministic controls.

## Predictive Scaling

Estimate upcoming demand and prepare capacity before a known load increase. This requires reliable workload data and an actual scaling target.

## Kubernetes

Deploy the services as Kubernetes workloads and replace local Compose-specific operations with Kubernetes-native health and lifecycle controls.

## Cloud Deployment

Run the system in a cloud environment with production networking, secrets handling, monitoring, and operational controls.

## Multi-Node Clusters

Extend the current single-node lab into a multi-node deployment with failure handling across nodes.

## Advanced Monitoring

Add richer alerting, longer retention, correlation, and operational views beyond the current Prometheus metrics and container logs.

## Horizontal Autoscaling

Add controlled creation and removal of backend capacity based on agreed policy and verified demand signals.

## Distributed Rule Engine

Move from one sole-writer worker to a distributed decision and coordination design while preserving action safety and auditability.
