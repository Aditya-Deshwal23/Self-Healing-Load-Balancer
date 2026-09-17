export type ConsoleRoute = {
  path: string;
  label: string;
  group: "OVERVIEW" | "TRAFFIC" | "INCIDENTS" | "ACTIONS" | "RECOVERY" | "LAB" | "SYSTEM" | "CONTEXT";
  icon: string;
  capability?: "lab";
  mobile?: boolean;
  primary?: boolean;
};

export const primaryNavGroups = ["OVERVIEW", "TRAFFIC", "INCIDENTS", "ACTIONS", "RECOVERY", "LAB", "SYSTEM"] as const;

export const consoleRoutes: ConsoleRoute[] = [
  { path: "/app", label: "Overview", group: "OVERVIEW", icon: "command", mobile: true, primary: true },
  { path: "/app/traffic/matrix", label: "Traffic", group: "TRAFFIC", icon: "matrix", primary: true },
  { path: "/app/traffic/topology", label: "Topology", group: "CONTEXT", icon: "topology" },
  { path: "/app/backends", label: "Backends", group: "CONTEXT", icon: "backends" },
  { path: "/app/traffic/analysis", label: "Analysis", group: "CONTEXT", icon: "traffic" },
  { path: "/app/incidents", label: "Incidents", group: "INCIDENTS", icon: "incidents", mobile: true, primary: true },
  { path: "/app/actions", label: "Actions", group: "ACTIONS", icon: "actions", primary: true },
  { path: "/app/reintegration", label: "Recovery", group: "RECOVERY", icon: "reintegrate", primary: true },
  { path: "/app/lab/faults", label: "Lab", group: "LAB", icon: "faults", capability: "lab", primary: true },
  { path: "/app/settings", label: "System", group: "SYSTEM", icon: "settings", primary: true },
  { path: "/app/policies", label: "Policies", group: "CONTEXT", icon: "policies" },
  { path: "/app/versions", label: "Version Health", group: "CONTEXT", icon: "versions" },
  { path: "/app/metrics", label: "Metrics", group: "CONTEXT", icon: "metrics" },
  { path: "/app/logs", label: "Logs", group: "CONTEXT", icon: "logs" },
  { path: "/app/lab/experiments", label: "Experiments", group: "CONTEXT", icon: "experiments", capability: "lab" },
  { path: "/app/lab/baselines", label: "Baseline Comparison", group: "CONTEXT", icon: "baselines", capability: "lab" },
];

export const staticConsoleSlugs = [
  ["traffic", "topology"],
  ["traffic", "matrix"],
  ["traffic", "analysis"],
  ["backends"],
  ["backends", "inst-a"],
  ["backends", "inst-b"],
  ["backends", "inst-c"],
  ["incidents"],
  ["incidents", "inc-1042"],
  ["incidents", "inc-1043"],
  ["incidents", "inc-1037"],
  ["incidents", "inc-1029"],
  ["incidents", "inc-1042", "decision-trace"],
  ["actions"],
  ["actions", "act-7719"],
  ["actions", "act-7720"],
  ["actions", "act-7688"],
  ["actions", "act-7651"],
  ["actions", "act-7610"],
  ["reintegration"],
  ["reintegration", "reint-228"],
  ["versions"],
  ["policies"],
  ["metrics"],
  ["logs"],
  ["lab", "faults"],
  ["lab", "experiments"],
  ["lab", "experiments", "exp-031"],
  ["lab", "baselines"],
  ["settings"],
];

export function titleForPath(pathname: string): string {
  const direct = consoleRoutes.find((route) => route.path === pathname);
  if (direct) return direct.label;
  if (pathname.includes("decision-trace")) return "Decision Trace";
  if (pathname.startsWith("/app/incidents/")) return "Incident Details";
  if (pathname.startsWith("/app/actions/")) return "Action Details";
  if (pathname.startsWith("/app/reintegration/")) return "Reintegration Run";
  if (pathname.startsWith("/app/backends/")) return "Backend Details";
  if (pathname.startsWith("/app/lab/experiments/")) return "Experiment Details";
  return "Console";
}
