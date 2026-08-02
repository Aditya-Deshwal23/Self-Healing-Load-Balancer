import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");

const requiredFiles = [
  "app/page.tsx",
  "app/login/page.tsx",
  "app/setup/page.tsx",
  "app/diagnostics/phase-1/page.tsx",
  "app/app/page.tsx",
  "app/app/[...slug]/page.tsx",
  "components/app-shell.tsx",
  "components/matrix.tsx",
  "components/topology.tsx",
  "components/decision-trace.tsx",
];

for (const relativePath of requiredFiles) {
  assert.equal(existsSync(join(frontendRoot, relativePath)), true, `missing frontend contract file: ${relativePath}`);
}

assert.equal(existsSync(join(frontendRoot, "public/index.html")), false, "the Phase-1 placeholder must not own the root");

const routesSource = readFileSync(join(frontendRoot, "lib/routes.ts"), "utf8");
const requiredPaths = [
  "/app/traffic/topology",
  "/app/traffic/matrix",
  "/app/traffic/analysis",
  "/app/backends",
  "/app/incidents",
  "/app/actions",
  "/app/reintegration",
  "/app/versions",
  "/app/policies",
  "/app/metrics",
  "/app/logs",
  "/app/lab/faults",
  "/app/lab/experiments",
  "/app/lab/baselines",
  "/app/settings",
];

for (const path of requiredPaths) {
  assert.match(routesSource, new RegExp(path.replaceAll("/", "\\/")), `missing console route: ${path}`);
}

const screenContracts = [
  ["app/page.tsx", "<LandingPage"],
  ["app/login/page.tsx", "<LoginPage"],
  ["app/setup/page.tsx", "<SetupPage"],
  ["app/app/page.tsx", "<CommandCenter"],
  ["components/console-route-page.tsx", "<TopologyPage"],
  ["components/console-route-page.tsx", "<MatrixPage"],
  ["components/console-route-page.tsx", "<BackendInventoryPage"],
  ["components/console-route-page.tsx", "<BackendDetailsPage"],
  ["components/console-route-page.tsx", "<TrafficAnalysisPage"],
  ["components/console-route-page.tsx", "<IncidentListPage"],
  ["components/console-route-page.tsx", "<IncidentDetailsPage"],
  ["components/console-route-page.tsx", "<DecisionTrace"],
  ["components/console-route-page.tsx", "<HealingActionsPage"],
  ["components/console-route-page.tsx", "<ReintegrationListPage"],
  ["components/console-route-page.tsx", "<VersionHealthPage"],
  ["components/console-route-page.tsx", "<PoliciesPage"],
  ["components/console-route-page.tsx", "<MetricsPage"],
  ["components/console-route-page.tsx", "<LogsPage"],
  ["components/console-route-page.tsx", "<FaultLabPage"],
  ["components/console-route-page.tsx", "<ExperimentsPage"],
  ["components/console-route-page.tsx", "<BaselineComparisonPage"],
  ["components/console-route-page.tsx", "<SettingsPage"],
];

for (const [relativePath, marker] of screenContracts) {
  const screenSource = readFileSync(join(frontendRoot, relativePath), "utf8");
  assert.match(screenSource, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `missing screen contract: ${marker}`);
}

const typesSource = readFileSync(join(frontendRoot, "lib/types.ts"), "utf8");
for (const failureClass of [
  "HEALTHY",
  "INSTANCE_DOWN",
  "INSTANCE_DEGRADED",
  "ROUTE_INSTANCE_FAILURE",
  "SHARED_ROUTE_FAILURE",
  "TRAFFIC_OVERLOAD",
  "VERSION_SPECIFIC_FAILURE",
  "UNKNOWN",
]) {
  assert.match(typesSource, new RegExp(`"${failureClass}"`), `missing operational class: ${failureClass}`);
}

const fixturesSource = readFileSync(join(frontendRoot, "lib/fixtures.ts"), "utf8");
assert.match(fixturesSource, /cell\("checkout", "inst-b"[\s\S]*?state: "quarantined"/, "checkout × Backend B fixture must be route-locally quarantined");
for (const sibling of ["public", "auth", "catalog"]) {
  assert.match(fixturesSource, new RegExp(`cell\\("${sibling}", "inst-b"`), `missing preserved Backend B sibling: ${sibling}`);
}
assert.match(fixturesSource, /observed: \{ admin: "ready", weight: 5 \}/, "fixture must exercise desired/observed drift");
assert.match(fixturesSource, /state: "no-membership"/, "fixture must distinguish no membership");
assert.match(fixturesSource, /evidence: "stale"/, "fixture must exercise stale evidence");

const shellSource = readFileSync(join(frontendRoot, "components/app-shell.tsx"), "utf8");
assert.match(shellSource, /route\.capability === "lab" && demoMeta\.labCapability/, "Research Lab must use capability logic");
assert.match(shellSource, /useSmallViewport\(\)/, "small-screen navigation must be behaviorally bounded");
assert.match(shellSource, /safe-mode-strip/, "SAFE_MODE must have a persistent shell strip");
assert.match(shellSource, /showModal\(\)/, "command palette must use native modal focus behavior");

const matrixSource = readFileSync(join(frontendRoot, "components/matrix.tsx"), "utf8");
assert.match(matrixSource, /tabIndex=\{active \? 0 : -1\}/, "matrix must use a roving keyboard tab stop");
assert.match(matrixSource, /dialog\.showModal\(\)/, "matrix comparison sheet must trap and restore focus");

const cssSource = readFileSync(join(frontendRoot, "app/globals.css"), "utf8");
for (const token of ["#F2EFE8", "#FBF9F4", "#9A4F2D", "#287449", "#A63C32", "#111311", "#D07A50"]) {
  assert.match(cssSource, new RegExp(token, "i"), `missing frozen visual token: ${token}`);
}
for (const mediaContract of ["max-width: 1439px", "max-width: 1023px", "max-width: 767px", "prefers-reduced-motion: reduce", "forced-colors: active"]) {
  assert.match(cssSource, new RegExp(mediaContract.replace(/[()]/g, "\\$&")), `missing responsive/accessibility contract: ${mediaContract}`);
}

const nginxSource = readFileSync(join(repositoryRoot, "nginx/nginx.conf"), "utf8");
assert.match(nginxSource, /location = \/api\/v1\/events[\s\S]*?proxy_buffering off;/, "SSE buffering must remain disabled");
assert.match(nginxSource, /location ~ \^\/\(public\|auth\|catalog\|checkout\)/, "application routes must continue to target HAProxy");
assert.match(nginxSource, /proxy_pass http:\/\/traffic-haproxy:8080;/, "NGINX must preserve the direct HAProxy request path");

console.log(`Verified ${screenContracts.length} product screens and safety-critical frontend contracts.`);
