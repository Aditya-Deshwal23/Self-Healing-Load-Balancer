"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type Scope = {
  team_id: string;
  team_name: string;
  team_slug: string;
  role: string;
};

type SessionData = {
  user: { id: string; email: string; status: string };
  scopes: Scope[];
  csrf_token: string;
};

export type SystemStatus = {
  environment: {
    id: string;
    project_id: string;
    name: string;
    kind: "DEV" | "LAB" | "DEMO" | "PILOT";
    mode: "OBSERVE_ONLY" | "RULES_ONLY" | "MANUAL" | "SAFE_MODE";
    automation_frozen: boolean;
    controller_generation: number;
  };
  control_plane: {
    api: string;
    postgresql: string;
    redis: string;
    sse: string;
    worker: string;
    haproxy_access: boolean;
    control_authority: string;
  };
  freshness: {
    control_loop: string;
    telemetry: string;
    last_confirmed_state: string | null;
  };
};

type Capabilities = {
  phase: number;
  features: {
    lab: boolean;
    rest_registry: boolean;
    server_side_sessions: boolean;
    sse: boolean;
    haproxy_readback: boolean;
    routing_mutations: boolean;
    healing_actions: boolean;
  };
};

type Envelope<T> = { data: T };
type ConnectionState = "checking" | "live" | "demo" | "unavailable" | "unauthenticated";
type StreamState = "connecting" | "connected" | "reconnecting" | "offline";

async function readProblem(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string };
    return body.detail ?? `Request failed with status ${response.status}.`;
  } catch {
    return `Request failed with status ${response.status}.`;
  }
}

export function useControlPlane() {
  const router = useRouter();
  const [state, setState] = useState<ConnectionState>("checking");
  const [streamState, setStreamState] = useState<StreamState>("offline");
  const [session, setSession] = useState<SessionData | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let active = true;
    const explicitDemo = new URLSearchParams(window.location.search).get("demo") === "1";
    if (explicitDemo) {
      setState("demo");
      return () => {
        active = false;
      };
    }

    async function connect() {
      try {
        const meResponse = await fetch("/api/v1/auth/me", {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (meResponse.status === 401) {
          if (!active) return;
          setState("unauthenticated");
          const returnTo = `${window.location.pathname}${window.location.search}`;
          router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
          return;
        }
        if (!meResponse.ok) throw new Error(await readProblem(meResponse));
        const me = await meResponse.json() as Envelope<SessionData>;
        const [statusResponse, capabilityResponse] = await Promise.all([
          fetch("/api/v1/system/status", {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            cache: "no-store",
          }),
          fetch("/api/v1/system/capabilities", {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            cache: "no-store",
          }),
        ]);
        if (!statusResponse.ok) throw new Error(await readProblem(statusResponse));
        if (!capabilityResponse.ok) throw new Error(await readProblem(capabilityResponse));
        const statusBody = await statusResponse.json() as Envelope<SystemStatus>;
        const capabilityBody = await capabilityResponse.json() as Envelope<Capabilities>;
        if (!active) return;
        setSession(me.data);
        setStatus(statusBody.data);
        setCapabilities(capabilityBody.data);
        setState("live");
        setError(null);

        setStreamState("connecting");
        const query = new URLSearchParams({
          project_id: statusBody.data.environment.project_id,
          environment_id: statusBody.data.environment.id,
        });
        const source = new EventSource(`/api/v1/events?${query.toString()}`);
        sourceRef.current = source;
        source.onopen = () => {
          if (active) setStreamState("connected");
        };
        source.onmessage = () => {
          if (active) setLastEventAt(new Date().toISOString());
        };
        const eventTypes = [
          "registry.snapshot.created",
          "project.created",
          "project.updated",
          "environment.created",
          "environment.updated",
          "service.created",
          "backend.created",
          "backend.updated",
          "version.created",
          "route.created",
          "route.updated",
          "membership.created",
          "membership.updated",
          "routing_policy.created",
          "retry_policy.created",
          "resync_required",
        ];
        eventTypes.forEach((eventType) => {
          source.addEventListener(eventType, () => {
            if (active) setLastEventAt(new Date().toISOString());
          });
        });
        source.onerror = () => {
          if (active) setStreamState("reconnecting");
        };
      } catch (reason) {
        if (!active) return;
        setState("unavailable");
        setStreamState("offline");
        setError(reason instanceof Error ? reason.message : "Control API unavailable.");
      }
    }

    void connect();
    return () => {
      active = false;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [router]);

  const logout = useCallback(async () => {
    if (!session) return;
    const response = await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
    });
    if (!response.ok) throw new Error(await readProblem(response));
    sourceRef.current?.close();
    setSession(null);
    setState("unauthenticated");
    router.replace("/login");
  }, [router, session]);

  return {
    state,
    streamState,
    session,
    status,
    capabilities,
    lastEventAt,
    error,
    logout,
  };
}
