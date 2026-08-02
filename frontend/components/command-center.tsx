"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  CircleDashed,
  Clock3,
  GitCompareArrows,
  RefreshCw,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { incident, incidentTimeline, operationalSummary, reintegration } from "@/lib/fixtures";
import { LiveTopology } from "@/components/topology";
import { RouteInstanceMatrix } from "@/components/matrix";
import { PageHeader, Panel, ProgressBar, StatusTag, Timeline } from "@/components/ui";

export function CommandCenter() {
  return (
    <div className="command-center page-stack">
      <PageHeader
        eyebrow="Current operating picture"
        title="Traffic is contained, but not yet confirmed safe."
        brief={<>Checkout on Backend B is isolated to one logical pool. Public, auth, and catalog remain eligible on the same physical instance. The affected symptom improved; preserved-capacity verification still needs <Link className="fact-link" href="/app/reintegration/reint-228">124 real requests</Link> before the action can be committed.</>}
        meta={<><span>Window 21:54–22:09 IST</span><span>18,442 requests</span><span>Evidence 88% complete</span><span>Last observed 2 s before snapshot</span></>}
        actions={<><Link className="button secondary" href="/app/incidents/inc-1042">Open incident</Link><Link className="button primary" href="/app/incidents/inc-1042/decision-trace">Decision Trace<ArrowRight size={15} /></Link></>}
      />

      <section className="operational-strip" aria-label="Operational status summary">
        {operationalSummary.map((item) => <div className={`operational-item ${item.state}`} key={item.label}><span>{item.label}</span><strong>{item.value}</strong><small>{item.detail}</small></div>)}
      </section>

      <div className="command-working-row">
        <Panel title="Active traffic topology" kicker="Observed request path" className="topology-panel" action={<Link className="inline-link" href="/app/traffic/topology">Full topology<ArrowRight size={14} /></Link>}>
          <LiveTopology compact />
        </Panel>

        <Panel title="Current decision" kicker="Evidence certificate cert_91c" className="decision-panel" action={<StatusTag tone="warning">VERIFYING</StatusTag>}>
          <div className="decision-class"><div><span>Operational class</span><strong>ROUTE_INSTANCE_FAILURE</strong></div><div className="decision-bounds"><span><strong>0.82</strong> confidence</span><span><strong>0.88</strong> completeness</span><span><strong>1</strong> conflict</span></div></div>
          <ol className="decision-chain" aria-label="Evidence to action decision chain">
            <li className="complete"><span><Check size={12} /></span><div><strong>Evidence</strong><small>6 bounded sources · 428 affected samples</small></div></li>
            <li className="complete"><span><GitCompareArrows size={12} /></span><div><strong>Scope</strong><small>Checkout × B; 3 sibling routes counter-support wider action</small></div></li>
            <li className="complete"><span><ShieldCheck size={12} /></span><div><strong>Safety</strong><small>7/7 deterministic constraints allowed</small></div></li>
            <li className="current"><span><RefreshCw size={12} /></span><div><strong>Action</strong><small>HAProxy drain observed · effect still verifying</small></div></li>
          </ol>
          <div className="decision-language">
            <div><span>Classifier suggested</span><strong>Route-instance pattern · shadow model 0.82</strong></div>
            <div><span>Safety engine allowed</span><strong>1 membership · policy revision 12</strong></div>
            <div><span>HAProxy observed</span><strong>drain · weight 0 · generation 184</strong></div>
            <div className="pending"><span>Verification confirmed</span><strong>Not yet · preservation collecting</strong></div>
          </div>
          <ProgressBar value={176} max={300} label="Preserved-cohort real samples" tone="warning" />
          <div className="decision-countdown"><Timer size={15} /><span><strong>00:48</strong> cooldown · 124 samples remaining</span><Link href="/app/incidents/inc-1042/decision-trace">Why this scope?<ChevronRight size={14} /></Link></div>
        </Panel>
      </div>

      <section className="panel matrix-command-panel" aria-label="Compact route by instance matrix">
        <RouteInstanceMatrix compact />
      </section>

      <div className="command-lower-grid">
        <Panel title="What changed" kicker="Incident timeline" action={<Link className="inline-link" href="/app/incidents/inc-1042">Incident details<ArrowRight size={14} /></Link>}>
          <Timeline items={incidentTimeline} />
        </Panel>

        <Panel title="What happens next" kicker="Verification and recovery" action={<StatusTag tone="warning"><Clock3 size={12} />Waiting for samples</StatusTag>}>
          <div className="next-action-summary"><div><span>Current action</span><strong><code>act-7719</code> · VERIFYING</strong><small>Requested and observed state match. Technical effect is not yet committed.</small></div><div><span>Reintegration</span><strong><code>{reintegration.id}</code> · requested 20 / observed 5</strong><small>Unmanaged weight drift blocks stage advancement.</small></div></div>
          <div className="dual-obligation-mini"><article className="passed"><Check size={15} /><div><span>Track A · affected relief</span><strong>Passed with 428 requests</strong></div></article><article className="collecting"><CircleDashed size={15} /><div><span>Track B · preservation</span><strong>176 / 300 real requests</strong></div></article><div className="gate"><ShieldCheck size={15} /><span>Commit gate</span><strong>OPEN</strong></div></div>
          <div className="panel-footer-links"><Link href="/app/actions/act-7719">Action diff<ArrowRight size={14} /></Link><Link href="/app/reintegration/reint-228">Reintegration run<ArrowRight size={14} /></Link></div>
        </Panel>

        <Panel title="Manual review" kicker="Operator queue" action={<StatusTag tone="danger">1 requires review</StatusTag>} className="review-queue-panel">
          <div className="review-queue-item"><AlertTriangle size={17} /><div><strong>Auth telemetry is stale on Backend C</strong><p>Evidence completeness is 52%. UNKNOWN cannot authorize a destructive action.</p><span><code>inc-1043</code> · last confirmed state ready / 100</span></div><Link href="/app/incidents/inc-1043">Review<ChevronRight size={15} /></Link></div>
          <div className="notice neutral"><CircleDashed size={15} /><span>No recommendation is presented as applied. Last confirmed HAProxy state is retained with its timestamp.</span></div>
        </Panel>
      </div>
    </div>
  );
}
