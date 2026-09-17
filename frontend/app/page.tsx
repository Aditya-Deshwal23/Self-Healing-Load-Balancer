import type { Metadata } from "next";
import { LandingPage } from "@/components/public-pages";

export const metadata: Metadata = {
  title: "Evidence-bounded traffic reliability",
};

export default function HomePage() {
  return <LandingPage />;
}
