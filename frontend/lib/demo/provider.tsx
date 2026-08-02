"use client";

import { createContext, useContext, type ReactNode } from "react";
import {
  action,
  actionQueue,
  classDescriptions,
  demoMeta,
  environments,
  errorSeries,
  experimentBaselines,
  experimentScenarios,
  incident,
  incidentTimeline,
  incidents,
  instances,
  logRows,
  matrixCells,
  operationalSummary,
  reintegration,
  reintegrationStages,
  routes,
  scopeCandidates,
  traceStages,
  trafficSeries,
} from "@/lib/fixtures";

const demoSnapshot = {
  action,
  actionQueue,
  classDescriptions,
  demoMeta,
  environments,
  errorSeries,
  experimentBaselines,
  experimentScenarios,
  incident,
  incidentTimeline,
  incidents,
  instances,
  logRows,
  matrixCells,
  operationalSummary,
  reintegration,
  reintegrationStages,
  routes,
  scopeCandidates,
  traceStages,
  trafficSeries,
} as const;

export type DemoSnapshot = typeof demoSnapshot;

const DemoContext = createContext<DemoSnapshot | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  return <DemoContext.Provider value={demoSnapshot}>{children}</DemoContext.Provider>;
}

export function useDemoSnapshot(): DemoSnapshot {
  const snapshot = useContext(DemoContext);
  if (!snapshot) throw new Error("useDemoSnapshot must be used inside DemoProvider");
  return snapshot;
}
