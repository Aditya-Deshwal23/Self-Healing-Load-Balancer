import type { Metadata } from "next";
import { SetupPage } from "@/components/public-pages";

export const metadata: Metadata = { title: "Project setup" };

export default function Page() {
  return <SetupPage />;
}
