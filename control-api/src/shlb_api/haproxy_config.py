from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from shlb_api.models import BackendInstance, RouteGroup, RouteMembership


_STATIC_HEADER = """global
  maxconn 4096
  stats socket /var/run/haproxy/admin.sock user haproxy group haproxy mode 0660 level admin expose-fd listeners
  log stdout format raw local0

resolvers docker
  nameserver dns1 127.0.0.11:53
  resolve_retries 3
  timeout resolve 1s
  timeout retry 1s
  hold valid 10s

defaults unnamed_defaults_1
  mode http
  log global
  option httplog
  option dontlognull
  option http-keep-alive
  timeout check 2s
  timeout connect 2s
  timeout client 30s
  timeout server 30s
"""

_STATIC_STATS = """frontend fe_stats from unnamed_defaults_1
  bind :8404
  stats enable
  stats uri /stats
  stats refresh 5s
  http-request use-service prometheus-exporter if { path /metrics }
  http-request return status 200 content-type text/plain string "ok\\n" if { path /healthz }
"""

_STATIC_UNMAPPED = """backend be_unmapped from unnamed_defaults_1
  http-request return status 404 content-type application/json string '{"error":"unmapped_route"}'
"""


def _route_name(route_key: str) -> str:
    if not route_key or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in route_key):
        raise ValueError(f"invalid route key for HAProxy config: {route_key!r}")
    return route_key


def _instance_hostname(instance: BackendInstance) -> str:
    suffix = instance.stable_name.rsplit("-", 1)[-1]
    if not suffix or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in suffix):
        raise ValueError(f"invalid backend instance name: {instance.stable_name!r}")
    return f"demo-backend-{suffix}"


def generate_haproxy_config(
    route_groups: Sequence[RouteGroup],
    backend_instances: Sequence[BackendInstance],
    route_memberships: Sequence[RouteMembership],
) -> str:
    """Render the deployment-time HAProxy config from registered topology rows."""
    routes = sorted(route_groups, key=lambda route: (route.priority, route.route_key))
    routes_by_id = {route.id: route for route in routes}
    instances_by_id = {instance.id: instance for instance in backend_instances}
    memberships_by_route: dict[object, list[RouteMembership]] = defaultdict(list)

    for membership in route_memberships:
        route = routes_by_id.get(membership.route_id)
        instance = instances_by_id.get(membership.instance_id)
        if route is None or instance is None:
            raise ValueError("route membership references topology outside the selected environment")
        expected_backend = f"be_{_route_name(route.route_key)}"
        if membership.haproxy_backend != expected_backend:
            raise ValueError(f"membership backend {membership.haproxy_backend!r} does not match {expected_backend!r}")
        memberships_by_route[route.id].append(membership)

    frontend_lines = ["frontend fe_application from unnamed_defaults_1", "  bind :8080"]
    for route in routes:
        route_key = _route_name(route.route_key)
        frontend_lines.extend(
            [
                f"  acl route_{route_key} path -i /{route_key}",
                f"  acl route_{route_key} path_beg -i /{route_key}/",
            ]
        )
    for route in routes:
        route_key = _route_name(route.route_key)
        frontend_lines.append(f"  use_backend be_{route_key} if route_{route_key}")
    frontend_lines.append("  default_backend be_unmapped")

    backend_blocks: list[str] = []
    for route in sorted(routes, key=lambda item: item.route_key):
        route_key = _route_name(route.route_key)
        lines = [
            f"backend be_{route_key} from unnamed_defaults_1",
            "  balance roundrobin",
            "  option httpchk GET /healthz",
            "  http-check expect status 200",
        ]
        memberships = sorted(memberships_by_route[route.id], key=lambda item: item.haproxy_server)
        for membership in memberships:
            instance = instances_by_id[membership.instance_id]
            lines.append(
                f"  server {membership.haproxy_server} {_instance_hostname(instance)}:{instance.port} "
                "check resolvers docker init-addr last,libc,none weight 100"
            )
        backend_blocks.append("\n".join(lines))

    sections = [
        _STATIC_HEADER.rstrip(),
        "\n".join(frontend_lines),
        _STATIC_STATS.rstrip(),
        "\n\n".join(backend_blocks),
        _STATIC_UNMAPPED.rstrip(),
    ]
    return "\n\n".join(sections) + "\n"
