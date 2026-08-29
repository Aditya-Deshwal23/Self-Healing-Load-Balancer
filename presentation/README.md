# Self-Healing Load Balancer

## Overview

This project is a local Docker Compose prototype that demonstrates a bounded self-healing load-balancing flow. It is designed around a specific case: one backend instance fails only for one application route. The controller detects the failure from real requests, Prometheus metrics, direct probes, and HAProxy Runtime state. It then removes only the affected route-to-instance membership and verifies that traffic continues through the healthy backends.

## Problem Statement

A load-balanced application can appear partly healthy while one route on one backend is failing. Sending all traffic away from that backend can remove healthy capacity unnecessarily. Restarting services without evidence can also make the situation worse or hide the real cause.

## Goal

Show an end-to-end recovery path that detects a supported failure, applies the smallest routing change, verifies the result, and gradually restores the route after the fault is cleared.

## Current Implementation

- Docker Compose runs the local lab, services, networks, secrets, and health checks.
- NGINX is the HTTPS edge reverse proxy; HAProxy balances four routes across three backend instances.
- Prometheus collects HAProxy and backend metrics; the worker also uses direct backend probes and HAProxy Runtime readback.
- A deterministic rule engine classifies supported conditions and a single control worker applies evidence-gated HAProxy route changes.
- PostgreSQL stores incidents, evidence, actions, verification results, and recovery stages; Redis supports worker coordination and event delivery.
- The web console shows live traffic, incidents, actions, recovery, and system state through REST and server-sent events.

## Current Limits

The controller does not restart backend containers. Docker Compose can restart a stopped container according to its service restart policy, while the controller's implemented recovery action is traffic quarantine and staged reintegration. Logs are emitted as JSON through Docker logging; Elasticsearch, Logstash, and Kibana are not part of this prototype.

## Future Work

Future work is limited to the items in [future_scope.md](future_scope.md). It is not part of the current demonstration.
