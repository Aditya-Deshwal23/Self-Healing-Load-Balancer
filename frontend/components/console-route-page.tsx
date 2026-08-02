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

export function ConsoleRoutePage({ slug }: { slug: string[] }) {
  const path = slug.join("/");

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
