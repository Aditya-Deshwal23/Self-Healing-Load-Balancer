"use client";

import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleDashed,
  CircleHelp,
  Clock3,
  DatabaseZap,
  Minus,
  RefreshCw,
  ShieldAlert,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "neutral" | "muted" | "info";

const toneIcons: Record<Tone, LucideIcon> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  neutral: CircleDashed,
  muted: Minus,
  info: CircleHelp,
};

export function StatusTag({ children, tone = "neutral", icon = true, className = "" }: { children: ReactNode; tone?: Tone; icon?: boolean; className?: string }) {
  const Icon = toneIcons[tone];
  return <span className={`status-tag ${tone} ${className}`}>{icon && <Icon size={12} aria-hidden="true" />}<span>{children}</span></span>;
}

export function LiveConnectionStatus({
  state,
  lastEventAt,
}: {
  state: "connecting" | "connected" | "reconnecting" | "offline";
  lastEventAt?: string | null;
}) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const update = () => setNow(Date.now());
    update();
    const interval = window.setInterval(update, 1000);
    return () => window.clearInterval(interval);
  }, []);
  const ageSeconds = lastEventAt
    ? now
      ? Math.max(0, Math.floor((now - new Date(lastEventAt).getTime()) / 1000))
      : null
    : null;
  const stale = ageSeconds !== null && ageSeconds > 30;
  const tone: Tone =
    state === "connected" && !stale
      ? "success"
      : state === "reconnecting" || stale
        ? "warning"
        : state === "offline"
          ? "danger"
          : "neutral";
  const label =
    state === "connected" && !stale
      ? "Live"
      : stale
        ? "Stale"
        : state === "reconnecting"
          ? "Reconnecting"
          : state === "offline"
            ? "Offline"
            : "Connecting";
  const detail =
    ageSeconds === null
      ? "No events received"
      : ageSeconds < 2
        ? "Updated just now"
        : `Updated ${ageSeconds}s ago`;
  return (
    <span
      aria-label={`Control-plane stream ${label.toLowerCase()}. ${detail}.`}
      title={detail}
    >
      <StatusTag tone={tone}>{label}</StatusTag>
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  brief,
  meta,
  actions,
}: {
  eyebrow: string;
  title: string;
  brief: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <div className="situation-brief">{brief}</div>
        {meta && <div className="page-meta">{meta}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  kicker,
  action,
  children,
  className = "",
  id,
}: {
  title: string;
  kicker?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section className={`panel ${className}`} aria-labelledby={headingId} id={id}>
      <div className="panel-heading">
        <div>{kicker && <span className="section-kicker">{kicker}</span>}<h2 id={headingId}>{title}</h2></div>
        {action && <div className="panel-action">{action}</div>}
      </div>
      {children}
    </section>
  );
}

export function Metric({ label, value, detail, tone = "neutral" }: { label: string; value: string; detail?: string; tone?: Tone }) {
  return <div className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

export function ProgressBar({ value, max = 100, label, tone = "neutral" }: { value: number; max?: number; label: string; tone?: Tone }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={`progress-block ${tone}`}>
      <div><span>{label}</span><span className="mono">{value}/{max}</span></div>
      <div className="progress-track" role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}><span style={{ width: `${percentage}%` }} /></div>
    </div>
  );
}

export function StateMessage({ state, title, children, action }: { state: "loading" | "empty" | "stale" | "failure" | "unknown"; title: string; children: ReactNode; action?: ReactNode }) {
  const map: Record<typeof state, LucideIcon> = { loading: RefreshCw, empty: DatabaseZap, stale: Clock3, failure: AlertCircle, unknown: CircleDashed };
  const Icon = map[state];
  return <div className={`state-message ${state}`}><Icon size={21} aria-hidden="true" className={state === "loading" ? "spin-once" : ""} /><div><strong>{title}</strong><p>{children}</p></div>{action}</div>;
}

export function KeyValueGrid({ items }: { items: Array<{ label: string; value: ReactNode; mono?: boolean }> }) {
  return <dl className="key-value-grid">{items.map((item) => <div key={item.label}><dt>{item.label}</dt><dd className={item.mono ? "mono" : undefined}>{item.value}</dd></div>)}</dl>;
}

export function Timeline({ items }: { items: Array<{ at: string; label: string; detail: string; state?: string }> }) {
  return <ol className="event-timeline">{items.map((item, index) => <li className={item.state ?? "neutral"} key={`${item.at}-${index}`}><span className="timeline-dot" aria-hidden="true" /><time>{item.at}</time><div><strong>{item.label}</strong><p>{item.detail}</p></div></li>)}</ol>;
}

export function StateTriptych({
  previous,
  requested,
  observed,
}: {
  previous: { admin: string; weight: number; generation: number };
  requested: { admin: string; weight: number; generation: number };
  observed: { admin: string; weight: number; generation: number };
}) {
  const matches = requested.admin === observed.admin && requested.weight === observed.weight;
  return (
    <div className="state-triptych" aria-label="Previous, requested, and observed routing state">
      <article><span>Previous</span><strong>{previous.admin}</strong><code>weight {previous.weight}</code><small>generation {previous.generation}</small></article>
      <ArrowRight aria-hidden="true" size={18} />
      <article className="requested"><span>Requested</span><strong>{requested.admin}</strong><code>weight {requested.weight}</code><small>generation {requested.generation}</small></article>
      <ArrowRight aria-hidden="true" size={18} />
      <article className={matches ? "observed match" : "observed mismatch"}><span>Observed</span><strong>{observed.admin}</strong><code>weight {observed.weight}</code><small>{matches ? <><Check size={12} />Runtime readback matched</> : "HAProxy differs"}</small></article>
    </div>
  );
}

export function BlastRadiusMap({ mode = "observed" }: { mode?: "before" | "proposed" | "observed" }) {
  const checkoutState = mode === "before" ? "ready · 100" : mode === "proposed" ? "drain requested" : "drain observed";
  return (
    <div className="blast-radius">
      <div className="blast-instance"><ServerMini /><div><strong>Backend B</strong><span>physical capacity 100 · counted once</span></div></div>
      <div className="blast-lines" aria-hidden="true"><i /><i /><i /><i /></div>
      <div className="blast-memberships">
        {["/public", "/auth", "/catalog"].map((route) => <div className="blast-membership preserved" key={route}><code>{route}</code><strong>ready · 100</strong><span><Check size={12} />UNCHANGED</span></div>)}
        <div className="blast-membership changed"><code>/checkout</code><strong>{checkoutState}</strong><span>{mode === "before" ? "BASELINE" : "CHANGES · 1 MEMBERSHIP"}</span></div>
      </div>
      <p className="blast-summary">This scope changes <strong>1 of 4</strong> route memberships. Public, auth, and catalog remain eligible on Backend B. Checkout retains two peer instances and 67% route capacity.</p>
      <details className="accessible-alternative"><summary>Table alternative</summary><table><thead><tr><th>Membership</th><th>Before</th><th>{mode === "observed" ? "Observed" : "Proposed"}</th><th>Impact</th></tr></thead><tbody><tr><th>/public × B</th><td>ready 100</td><td>ready 100</td><td>Preserved</td></tr><tr><th>/auth × B</th><td>ready 100</td><td>ready 100</td><td>Preserved</td></tr><tr><th>/catalog × B</th><td>ready 100</td><td>ready 100</td><td>Preserved</td></tr><tr><th>/checkout × B</th><td>ready 100</td><td>{checkoutState}</td><td>Changed</td></tr></tbody></table></details>
    </div>
  );
}

function ServerMini() {
  return <span className="server-mini" aria-hidden="true"><i /><i /><i /></span>;
}

export function ReviewDialog({
  open,
  onClose,
  title,
  intent,
  actionLabel,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  intent: string;
  actionLabel: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<Element | null>(null);
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"before" | "proposed" | "observed">("proposed");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (open && dialog) {
      triggerRef.current = document.activeElement;
      if (!dialog.open) dialog.showModal();
    } else if (!open && dialog?.open) {
      dialog.close();
    }
  }, [open]);

  if (!open) return null;

  function close() {
    if (dialogRef.current?.open) dialogRef.current.close();
    onClose();
    window.setTimeout(() => (triggerRef.current as HTMLElement | null)?.focus(), 0);
  }

  return (
    <dialog className="review-dialog" ref={dialogRef} onCancel={(event) => { event.preventDefault(); close(); }} aria-labelledby="review-title">
      <div className="review-dialog-header"><div><span className="section-kicker">Immutable impact review · demo only</span><h2 id="review-title">{title}</h2><p>{intent}</p></div><button className="icon-button" type="button" onClick={close} aria-label="Close impact review"><X size={18} /></button></div>
      <div className="review-dialog-body">
        <div className="segmented-control" aria-label="Impact state">
          {(["before", "proposed", "observed"] as const).map((item) => <button type="button" aria-pressed={mode === item} className={mode === item ? "active" : ""} onClick={() => setMode(item)} key={item}>{item[0].toUpperCase() + item.slice(1)}</button>)}
        </div>
        <BlastRadiusMap mode={mode} />
        <div className="review-constraints">
          <div><CheckCircle2 size={16} /><span><strong>Capacity</strong>Checkout retains 2 eligible peers · 67% route capacity</span></div>
          <div><CheckCircle2 size={16} /><span><strong>Retry</strong>Ambiguous POST cross-instance retry remains suppressed</span></div>
          <div><CheckCircle2 size={16} /><span><strong>Rollback</strong>Exact observed snapshot is available</span></div>
          <div><ShieldAlert size={16} /><span><strong>Authorization</strong>Operator reason required; broader scope would require Approver</span></div>
        </div>
        <label htmlFor="review-reason">Reason</label>
        <textarea id="review-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the operational intent and evidence reference." rows={3} />
        <div className="notice warning"><AlertTriangle size={17} /><span><strong>No command will be sent.</strong> Phase 2 persists registry intent only; the sole-writer controller, HAProxy readback, and action lifecycle are not deployed.</span></div>
      </div>
      <footer className="review-dialog-footer"><button className="button secondary" type="button" onClick={close}>Cancel</button><button className="button danger" type="button" disabled title="Control API unavailable">{actionLabel}</button></footer>
    </dialog>
  );
}

export function InlineLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link className="inline-link" href={href}>{children}<ArrowRight size={14} /></Link>;
}
