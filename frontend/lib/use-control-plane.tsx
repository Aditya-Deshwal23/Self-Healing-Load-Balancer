"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiRequest } from "@/lib/api/client";

type Scope = { team_id: string; team_name: string; team_slug: string; role: string };
export type SessionData = { user: { id: string; email: string; status: string }; scopes: Scope[]; csrf_token: string };
export type SystemStatus = {
  environment: { id: string; project_id: string; name: string; kind: "DEV" | "LAB" | "DEMO" | "PILOT"; mode: "OBSERVE_ONLY" | "RULES_ONLY" | "MANUAL" | "SAFE_MODE"; automation_frozen: boolean; controller_generation: number };
  control_plane: { api: string; postgresql: string; redis: string; sse: string; worker: string; haproxy_access: boolean; control_authority: string };
  freshness: { control_loop: string | null; telemetry: string; last_confirmed_state: string | null };
};
type Capabilities = {
  phase: string;
  features: { lab: boolean; rest_registry: boolean; server_side_sessions: boolean; sse: boolean; prometheus_evidence: boolean; haproxy_readback: boolean; routing_mutations: boolean; healing_actions: boolean; verification: boolean; reintegration: boolean };
  prototype_support: { implemented: string[]; planned: string[] };
};
type ConnectionState = "checking" | "live" | "demo" | "unavailable" | "unauthenticated";
type StreamState = "connecting" | "connected" | "reconnecting" | "offline";
type ControlPlaneContextValue = {
  state: ConnectionState;
  streamState: StreamState;
  session: SessionData | null;
  status: SystemStatus | null;
  capabilities: Capabilities | null;
  lastEventAt: string | null;
  error: string | null;
  logout: () => Promise<void>;
};

const ControlPlaneContext = createContext<ControlPlaneContextValue | null>(null);
const eventTypes = [
  "incident_detected", "classification_completed", "action_planned", "action_applied",
  "verification_updated", "reintegration_progress", "rollback_started", "incident_resolved",
  "safe_mode_changed", "drift_detected", "lab_fault_applied", "lab_fault_cleared", "resync_required",
];

export function ControlPlaneProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 1500, retry: 1, refetchOnWindowFocus: true } } }));
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
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setState("demo");
      return () => { active = false; };
    }
    async function connect() {
      try {
        const me = await apiRequest<SessionData>("/api/v1/auth/me");
        const [system, capability] = await Promise.all([
          apiRequest<SystemStatus>("/api/v1/system/status"),
          apiRequest<Capabilities>("/api/v1/system/capabilities"),
        ]);
        if (!active) return;
        setSession(me.data);
        setStatus(system.data);
        setCapabilities(capability.data);
        setState("live");
        setError(null);
        setStreamState("connecting");
        const query = new URLSearchParams({ project_id: system.data.environment.project_id, environment_id: system.data.environment.id });
        const source = new EventSource(`/api/v1/events?${query.toString()}`);
        sourceRef.current = source;
        source.onopen = () => { if (active) setStreamState("connected"); };
        const onEvent = () => {
          if (!active) return;
          setLastEventAt(new Date().toISOString());
          void queryClient.invalidateQueries({ queryKey: ["environment", system.data.environment.id] });
        };
        source.onmessage = onEvent;
        eventTypes.forEach((eventType) => source.addEventListener(eventType, onEvent));
        source.onerror = () => { if (active) setStreamState("reconnecting"); };
      } catch (reason) {
        if (!active) return;
        const statusCode = typeof reason === "object" && reason !== null && "status" in reason ? Number(reason.status) : 0;
        if (statusCode === 401) {
          setState("unauthenticated");
          const returnTo = `${window.location.pathname}${window.location.search}`;
          router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
        } else {
          setState("unavailable");
          setStreamState("offline");
          setError(reason instanceof Error ? reason.message : "Control API unavailable.");
        }
      }
    }
    void connect();
    return () => {
      active = false;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [queryClient, router]);

  const logout = useCallback(async () => {
    if (!session) return;
    await apiRequest("/api/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": session.csrf_token } });
    sourceRef.current?.close();
    queryClient.clear();
    setSession(null);
    setState("unauthenticated");
    router.replace("/login");
  }, [queryClient, router, session]);

  return (
    <QueryClientProvider client={queryClient}>
      <ControlPlaneContext.Provider value={{ state, streamState, session, status, capabilities, lastEventAt, error, logout }}>
        {children}
      </ControlPlaneContext.Provider>
    </QueryClientProvider>
  );
}

export function useControlPlane(): ControlPlaneContextValue {
  const value = useContext(ControlPlaneContext);
  if (!value) throw new Error("useControlPlane must be used inside ControlPlaneProvider");
  return value;
}
