import "@fontsource-variable/source-sans-3";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Self Healing Load Balancer",
    template: "%s · Self Healing Load Balancer",
  },
  description:
    "An evidence-bounded traffic reliability console for minimum-scope HAProxy interventions.",
  applicationName: "Self Healing Load Balancer",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F2EFE8" },
    { media: "(prefers-color-scheme: dark)", color: "#111311" },
  ],
};

const themeBootstrap = `
(function () {
  try {
    var saved = localStorage.getItem('shlb-theme') || 'light';
    var resolved = saved === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : saved;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = saved;
  } catch (_) {
    document.documentElement.dataset.theme = 'light';
  }
})();`;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
