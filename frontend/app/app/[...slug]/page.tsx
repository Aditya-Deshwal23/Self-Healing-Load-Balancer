import { Suspense } from "react";
import type { Metadata } from "next";
import { ConsoleRoutePage } from "@/components/console-route-page";
import { staticConsoleSlugs, titleForPath } from "@/lib/routes";

export const dynamicParams = false;

export function generateStaticParams() {
  return staticConsoleSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }): Promise<Metadata> {
  const { slug } = await params;
  return { title: titleForPath(`/app/${slug.join("/")}`) };
}

export default async function Page({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  return (
    <Suspense fallback={<div className="page-stack">Loading console…</div>}>
      <ConsoleRoutePage slug={slug} />
    </Suspense>
  );
}
