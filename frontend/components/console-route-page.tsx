"use client";

import { useEffect, useState } from "react";
import { DecisionTrace } from "@/components/decision-trace";
import {
  ActionDetailsPage,
  HealingActionsPage,
  IncidentDetailsPage,
  IncidentListPage,
  ReintegrationDetailsPage,
  ReintegrationListPage,
} from "@/components/response-pages";
import {
  BackendDetailsPage,
  BackendInventoryPage,
  MatrixPage,
  TopologyPage,
  TrafficAnalysisPage,
} from "@/components/traffic-pages";
import { PoliciesPage, SettingsPage, VersionHealthPage } from "@/components/configuration-pages";
import { LogsPage, MetricsPage } from "@/components/evidence-pages";
import {
  BaselineComparisonPage,
  ExperimentDetailsPage,
  ExperimentsPage,
  FaultLabPage,
} from "@/components/lab-pages";
import { LiveActions } from "@/features/actions/live-actions";
import { LiveIncidents } from "@/features/incidents/live-incidents";
import { LiveFaultLab } from "@/features/lab/live-fault-lab";
import { LiveRecovery } from "@/features/recovery/live-recovery";
import { LiveSystem } from "@/features/system/live-system";
import { LiveRouteMatrix } from "@/features/traffic/live-matrix";
import { PageHeader, StateMessage } from "@/components/ui";
import { useControlPlane } from "@/lib/use-control-plane";

function useLocationParameters() {
  const [parameters, setParameters] = useState<URLSearchParams | null>(null);
  useEffect(() => setParameters(new URLSearchParams(window.location.search)), []);
  return parameters;
}

function UnsupportedLivePage({ title }: { title: string }) {
  return <div className="page-stack"><PageHeader eyebrow="Prototype capability" title={title} brief="This contextual Phase-2 route is preserved for contract compatibility, but it is not a working capability in the rules-only prototype." /><StateMessage state="unknown" title="Planned, not simulated">Use the seven primary destinations for real LAB state. Add <code>?demo=1</code> only when you intentionally want the bounded design snapshot.</StateMessage></div>;
}

export function ConsoleRoutePage({ slug }: { slug: string[] }) {
  const control = useControlPlane();
  const parameters = useLocationParameters();
  const path = slug.join("/");

  if (control.state === "checking" || control.state === "unauthenticated") return <StateMessage state="loading" title="Connecting to the control plane…">Loading the authenticated environment.</StateMessage>;
  if (control.state === "unavailable") return <StateMessage state="failure" title="The live control plane is unavailable.">{control.error ?? "No fixture fallback was used."}</StateMessage>;

  if (control.state === "live") {
    if (path === "traffic/matrix") return <div className="page-stack"><PageHeader eyebrow="Traffic" title="Route × instance matrix" brief="Each cell compares durable desired state with HAProxy Runtime readback and a bounded Prometheus evidence window." /><section className="panel matrix-command-panel"><LiveRouteMatrix /></section></div>;
    if (path === "incidents") return <LiveIncidents incidentId={parameters?.get("incident") ?? undefined} traceOnly={parameters?.get("trace") === "1"} />;
    if (slug[0] === "incidents" && slug[1] && slug[2] === "decision-trace") return <LiveIncidents incidentId={slug[1]} traceOnly />;
    if (path === "actions") return <LiveActions actionId={parameters?.get("action") ?? undefined} />;
    if (path === "reintegration") return <LiveRecovery runId={parameters?.get("run") ?? undefined} />;
    if (path === "lab/faults") return <LiveFaultLab />;
    if (path === "settings") return <LiveSystem />;
    return <UnsupportedLivePage title={path.split("/").map((item) => item[0]?.toUpperCase() + item.slice(1)).join(" / ")} />;
  }

  if (slug[0] === "backends" && slug.length === 2) return <BackendDetailsPage backendId={slug[1]} />;
  if (slug[0] === "incidents" && slug.length === 2) return <IncidentDetailsPage incidentId={slug[1]} />;
  if (slug[0] === "actions" && slug.length === 2) return <ActionDetailsPage actionId={slug[1]} />;

  switch (path) {
    case "traffic/topology":
      return <TopologyPage />;
    case "traffic/matrix":
      return <MatrixPage />;
    case "traffic/analysis":
      return <TrafficAnalysisPage />;
    case "backends":
      return <BackendInventoryPage />;
    case "incidents":
      return <IncidentListPage />;
    case "incidents/inc-1042/decision-trace":
      return <DecisionTrace />;
    case "actions":
      return <HealingActionsPage />;
    case "reintegration":
      return <ReintegrationListPage />;
    case "reintegration/reint-228":
      return <ReintegrationDetailsPage />;
    case "versions":
      return <VersionHealthPage />;
    case "policies":
      return <PoliciesPage />;
    case "metrics":
      return <MetricsPage />;
    case "logs":
      return <LogsPage />;
    case "lab/faults":
      return <FaultLabPage />;
    case "lab/experiments":
      return <ExperimentsPage />;
    case "lab/experiments/exp-031":
      return <ExperimentDetailsPage />;
    case "lab/baselines":
      return <BaselineComparisonPage />;
    case "settings":
      return <SettingsPage />;
    default:
      return <IncidentListPage />;
  }
}
