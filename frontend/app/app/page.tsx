import type { Metadata } from "next";
import { LiveCommandCenterRoute } from "@/features/live-command-center-route";

export const metadata: Metadata = { title: "Command Center" };

export default function Page() {
  return <LiveCommandCenterRoute />;
}
