import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { DemoProvider } from "@/lib/demo/provider";
import { ControlPlaneProvider } from "@/lib/use-control-plane";

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return <ControlPlaneProvider><DemoProvider><AppShell>{children}</AppShell></DemoProvider></ControlPlaneProvider>;
}
