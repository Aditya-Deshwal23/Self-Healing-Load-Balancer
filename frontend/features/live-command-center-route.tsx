"use client";

import { CommandCenter } from "@/components/command-center";
import { LiveCommandCenter } from "@/features/overview/live-command-center";
import { StateMessage } from "@/components/ui";
import { useControlPlane } from "@/lib/use-control-plane";

export function LiveCommandCenterRoute() {
  const control = useControlPlane();
  if (control.state === "demo") return <CommandCenter />;
  if (control.state === "checking" || control.state === "unauthenticated")
    return (
      <StateMessage state="loading" title="Connecting to the control plane…">
        Authenticating the session and opening the environment event stream.
      </StateMessage>
    );
  if (control.state === "unavailable")
    return (
      <StateMessage
        state="failure"
        title="The live control plane is unavailable."
      >
        {control.error ?? "No fixture fallback was used."}
      </StateMessage>
    );
  return <LiveCommandCenter />;
}
