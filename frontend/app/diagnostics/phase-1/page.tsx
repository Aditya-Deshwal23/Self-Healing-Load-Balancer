import type { Metadata } from "next";
import Link from "next/link";
import { Activity, ArrowLeft, CheckCircle2, ExternalLink, Route, Server } from "lucide-react";

export const metadata: Metadata = { title: "Phase 1 diagnostics" };

const routes = ["/public", "/auth", "/catalog", "/checkout"];

export default function PhaseOneDiagnostics() {
  return (
    <main className="diagnostic-page" id="main-content">
      <div className="diagnostic-frame">
        <Link className="text-link with-icon" href="/">
          <ArrowLeft aria-hidden="true" size={16} /> Back to product
        </Link>
        <header className="diagnostic-heading">
          <div className="product-mark" aria-hidden="true"><Route size={20} /></div>
          <div>
            <span className="eyebrow">Internal diagnostic · Phase 1</span>
            <h1>Edge delivery and route isolation</h1>
          </div>
        </header>
        <p className="lede narrow">
          This route preserves the original diagnostic purpose without occupying the product root. Reaching it confirms that edge NGINX serves the static export; use System and the live Command Center to inspect the separate API, telemetry, worker and HAProxy readback.
        </p>

        <section className="diagnostic-grid" aria-label="Phase 1 boundaries">
          <article className="plain-panel">
            <CheckCircle2 aria-hidden="true" size={19} />
            <h2>Static edge</h2>
            <p>NGINX serves this application over the local TLS listener and owns the shallow <code>/healthz</code> check.</p>
          </article>
          <article className="plain-panel">
            <Activity aria-hidden="true" size={19} />
            <h2>Traffic path</h2>
            <p>Application requests bypass the control plane: NGINX forwards directly to HAProxy and its route-specific pools.</p>
          </article>
          <article className="plain-panel">
            <Server aria-hidden="true" size={19} />
            <h2>Control boundary</h2>
            <p>REST/SSE and the sole-writer worker exist separately. This page intentionally proves only the request path, not a controller decision.</p>
          </article>
        </section>

        <section className="diagnostic-routes" aria-labelledby="route-checks-title">
          <div>
            <span className="section-kicker">Black-box application routes</span>
            <h2 id="route-checks-title">Open a live backend response</h2>
            <p>Each path is matched by HAProxy and returns the selected physical instance, deployment version, and route.</p>
          </div>
          <div className="route-link-list">
            {routes.map((route) => (
              <a className="route-link" href={route} key={route}>
                <code>{route}</code><ExternalLink aria-hidden="true" size={14} />
              </a>
            ))}
          </div>
        </section>

        <div className="notice neutral" role="note">
          <strong>Expected boundary</strong>
          <span>A successful page render is not evidence that controller decisions or HAProxy mutations are available.</span>
        </div>
      </div>
    </main>
  );
}
