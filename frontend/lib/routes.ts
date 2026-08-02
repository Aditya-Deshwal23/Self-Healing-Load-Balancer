export type ConsoleRoute = {
  path: string;
  label: string;
  group: "COMMAND" | "TRAFFIC" | "RESPONSE" | "EVIDENCE" | "RESEARCH LAB" | "CONFIGURATION";
  icon: string;
  capability?: "lab";
  mobile?: boolean;
};

export const consoleRoutes: ConsoleRoute[] = [
  { path: "/app", label: "Command Center", group: "COMMAND", icon: "command", mobile: true },
  { path: "/app/traffic/topology", label: "Live Topology", group: "TRAFFIC", icon: "topology" },
  { path: "/app/traffic/matrix", label: "Route Matrix", group: "TRAFFIC", icon: "matrix" },
  { path: "/app/traffic/analysis", label: "Traffic Analysis", group: "TRAFFIC", icon: "traffic" },
  { path: "/app/backends", label: "Backends", group: "TRAFFIC", icon: "backends" },
  { path: "/app/incidents", label: "Incidents", group: "RESPONSE", icon: "incidents", mobile: true },
  { path: "/app/actions", label: "Healing Actions", group: "RESPONSE", icon: "actions" },
  { path: "/app/reintegration", label: "Reintegration", group: "RESPONSE", icon: "reintegrate" },
  { path: "/app/versions", label: "Version Health", group: "RESPONSE", icon: "versions" },
  { path: "/app/metrics", label: "Metrics", group: "EVIDENCE", icon: "metrics" },
  { path: "/app/logs", label: "Logs", group: "EVIDENCE", icon: "logs" },
  { path: "/app/lab/faults", label: "Fault Lab", group: "RESEARCH LAB", icon: "faults", capability: "lab" },
  { path: "/app/lab/experiments", label: "Experiments", group: "RESEARCH LAB", icon: "experiments", capability: "lab" },
  { path: "/app/lab/baselines", label: "Baseline Comparison", group: "RESEARCH LAB", icon: "baselines", capability: "lab" },
  { path: "/app/policies", label: "Routing Policies", group: "CONFIGURATION", icon: "policies" },
  { path: "/app/settings", label: "Settings", group: "CONFIGURATION", icon: "settings" },
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
