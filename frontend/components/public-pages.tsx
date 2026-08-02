"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Eye,
  EyeOff,
  Gauge,
  GitCompareArrows,
  KeyRound,
  LockKeyhole,
  Network,
  Route,
  Server,
  ShieldCheck,
} from "lucide-react";

const implementedFailureClasses = [
  "HEALTHY",
  "INSTANCE_DOWN",
  "ROUTE_INSTANCE_FAILURE",
  "SHARED_ROUTE_FAILURE",
  "UNKNOWN",
];

function PublicHeader() {
  return (
    <header className="public-header">
      <Link
        className="brand"
        href="/"
        aria-label="Self Healing Load Balancer home"
      >
        <span className="product-mark" aria-hidden="true">
          <Route size={18} />
        </span>
        <span>Self Healing Load Balancer</span>
      </Link>
      <nav aria-label="Public navigation">
        <Link href="/diagnostics/phase-1">Diagnostics</Link>
        <Link href="/#method">Technical method</Link>
        <Link className="button secondary compact" href="/login">
          Sign in
        </Link>
      </nav>
    </header>
  );
}

const smallMatrix = [
  ["/public", "Ready", "Ready", "Ready"],
  ["/auth", "Ready", "Ready", "Ready"],
  ["/catalog", "Ready", "Ready", "Ready"],
  ["/checkout", "Ready", "Failing", "Ready"],
];

export function LandingPage() {
  return (
    <div className="public-site">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <PublicHeader />
      <main id="main-content">
        <section className="landing-hero">
          <div className="hero-copy">
            <span className="eyebrow">
              Evidence-bounded traffic reliability
            </span>
            <h1>Change the smallest safe part of the traffic path.</h1>
            <p className="lede">
              When one route fails on one backend, preserve the routes that
              still work. Every intervention is bounded by evidence, capacity,
              retry safety, HAProxy readback, and two-part verification.
            </p>
            <div className="button-row">
              <Link className="button primary" href="/login">
                Open local console <ArrowRight aria-hidden="true" size={16} />
              </Link>
              <a className="button secondary" href="#method">
                Read technical method <BookOpen aria-hidden="true" size={16} />
              </a>
            </div>
            <p className="microcopy">
              Local rules-only prototype · real HAProxy readback · sole-writer
              authority
            </p>
          </div>
          <div
            className="request-path-card"
            aria-labelledby="request-path-title"
          >
            <div className="panel-heading">
              <div>
                <span className="section-kicker">Normal request path</span>
                <h2 id="request-path-title">Control stays out of traffic</h2>
              </div>
              <span className="status-tag neutral">
                LKG survives control loss
              </span>
            </div>
            <div
              className="request-path"
              role="list"
              aria-label="Client request path"
            >
              {[
                "Client",
                "NGINX",
                "HAProxy",
                "/checkout pool",
                "Backend B",
                "Dependency",
              ].map((item, index) => (
                <div className="request-path-step" role="listitem" key={item}>
                  <span className="path-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <strong>{item}</strong>
                  {index < 5 && (
                    <span className="path-connector" aria-hidden="true" />
                  )}
                </div>
              ))}
            </div>
            <div className="control-boundary">
              <ShieldCheck aria-hidden="true" size={17} />
              <span>
                <strong>Out of path:</strong> controller observes, plans,
                applies, reads back, and verifies.
              </span>
            </div>
          </div>
        </section>

        <section
          className="landing-section example-section"
          aria-labelledby="example-title"
        >
          <div className="section-intro">
            <span className="section-kicker">Concrete isolation</span>
            <h2 id="example-title">
              Checkout can fail without making Backend B globally unhealthy.
            </h2>
            <p>
              One physical instance appears in several logical HAProxy pools.
              Membership state is independent; physical capacity is counted
              once.
            </p>
          </div>
          <div className="example-layout">
            <div className="example-narrative">
              <div className="fact-row">
                <span className="fact-number">18.2%</span>
                <span>checkout errors on B before quarantine</span>
              </div>
              <div className="fact-row">
                <span className="fact-number">3</span>
                <span>healthy sibling routes intentionally preserved</span>
              </div>
              <div className="fact-row">
                <span className="fact-number">1</span>
                <span>logical membership changed</span>
              </div>
              <div className="notice warm">
                <CircleAlert size={17} aria-hidden="true" />
                <span>
                  These are illustrative fixture values, not a live system
                  claim.
                </span>
              </div>
            </div>
            <div
              className="before-after"
              aria-label="Route matrix before and after checkout quarantine"
            >
              {(["Before", "After"] as const).map((phase) => (
                <div className="mini-matrix" key={phase}>
                  <div className="mini-matrix-title">
                    <span>{phase}</span>
                    <code>route × instance</code>
                  </div>
                  <div className="mini-row mini-head">
                    <span>Route</span>
                    <span>A</span>
                    <span>B</span>
                    <span>C</span>
                  </div>
                  {smallMatrix.map(([route, a, b, c]) => (
                    <div className="mini-row" key={`${phase}-${route}`}>
                      <code>{route}</code>
                      {[
                        a,
                        phase === "After" && route === "/checkout"
                          ? "Drain"
                          : b,
                        c,
                      ].map((state, index) => (
                        <span
                          className={`mini-cell ${state.toLowerCase()}`}
                          key={`${route}-${index}`}
                        >
                          <span aria-hidden="true">
                            {state === "Ready"
                              ? "✓"
                              : state === "Drain"
                                ? "—"
                                : "!"}
                          </span>
                          <span className="sr-only">{state}</span>
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className="landing-section method-section"
          id="method"
          aria-labelledby="method-title"
        >
          <div className="section-intro">
            <span className="section-kicker">EBMSH transaction</span>
            <h2 id="method-title">
              Evidence becomes permission only through deterministic gates.
            </h2>
          </div>
          <ol className="method-steps">
            {[
              [
                Activity,
                "Evidence",
                "Fresh, bounded proxy, metric, state, and probe facts.",
              ],
              [
                GitCompareArrows,
                "Scope",
                "Counter-evidence rejects broader route, instance, and version targets.",
              ],
              [
                ShieldCheck,
                "Safety",
                "Physical reserve, retry, conflicts, rollback, and generation must pass.",
              ],
              [
                Route,
                "Action",
                "One typed HAProxy target is requested and separately read back.",
              ],
              [
                Gauge,
                "Verification",
                "Affected relief and preserved healthy capacity must both pass.",
              ],
            ].map(([Icon, title, copy], index) => {
              const StepIcon = Icon as typeof Activity;
              return (
                <li key={String(title)}>
                  <span className="method-number">{index + 1}</span>
                  <StepIcon aria-hidden="true" size={19} />
                  <h3>{String(title)}</h3>
                  <p>{String(copy)}</p>
                </li>
              );
            })}
          </ol>
          <div
            className="class-band"
            aria-label="Supported operational classes"
          >
            {implementedFailureClasses.map((item) => (
              <code key={item}>{item}</code>
            ))}
          </div>
        </section>

        <section
          className="landing-section research-section"
          aria-labelledby="research-title"
        >
          <div className="section-intro">
            <span className="section-kicker">Research comparison</span>
            <h2 id="research-title">
              Measure preserved healthy capacity, not automation theatre.
            </h2>
            <p>
              The planned evaluation uses matched, independently labelled fault
              trials. Successful requests remain a non-inferiority guardrail.
            </p>
          </div>
          <div className="baseline-table-wrap">
            <table className="baseline-table">
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Scope behavior</th>
                  <th>Measured comparison</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>Plain Round Robin</th>
                  <td>No incident intervention</td>
                  <td rowSpan={4}>
                    Healthy route capacity preserved · successful-request
                    fraction · retry amplification · false actions · recovery
                    time
                  </td>
                </tr>
                <tr>
                  <th>HAProxy health checks</th>
                  <td>Instance health baseline</td>
                </tr>
                <tr>
                  <th>Static backend-wide</th>
                  <td>Threshold-based whole-backend removal</td>
                </tr>
                <tr>
                  <th>EBMSH proposed</th>
                  <td>Evidence-supported minimum scope</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section
          className="landing-section architecture-section"
          aria-labelledby="architecture-title"
        >
          <div className="section-intro">
            <span className="section-kicker">Self-hosted architecture</span>
            <h2 id="architecture-title">
              Standard components, strict authority boundaries.
            </h2>
          </div>
          <div className="architecture-grid">
            <article>
              <Network aria-hidden="true" />
              <h3>Data plane</h3>
              <p>
                NGINX fronts HAProxy. Logical route pools map to shared physical
                backend instances.
              </p>
              <code>NGINX · HAProxy</code>
            </article>
            <article>
              <Server aria-hidden="true" />
              <h3>Control</h3>
              <p>
                FastAPI exposes authenticated REST/SSE. A separate sole-writer
                worker owns Runtime actuation and readback.
              </p>
              <code>FastAPI · PostgreSQL · Redis</code>
            </article>
            <article>
              <Activity aria-hidden="true" />
              <h3>Evidence</h3>
              <p>
                Prometheus request outcomes and private direct probes support
                deterministic classification and verification. Missing evidence
                remains visible.
              </p>
              <code>Prometheus · direct probes</code>
            </article>
          </div>
        </section>

        <section
          className="landing-section limits-section"
          aria-labelledby="limits-title"
        >
          <div>
            <span className="section-kicker">Declared limits</span>
            <h2 id="limits-title">What this product does not claim.</h2>
          </div>
          <ul className="limit-list">
            <li>
              It does not repair application source code or restart arbitrary
              customer containers.
            </li>
            <li>It does not heal a failed NGINX or HAProxy host.</li>
            <li>
              It does not treat confidence, silence, or no traffic as proof of
              health.
            </li>
            <li>
              It does not let a model or report generator bypass retry or safety
              rules.
            </li>
          </ul>
        </section>

        <section className="landing-cta">
          <div>
            <span className="section-kicker">Local laboratory</span>
            <h2>Inspect the bounded decision, not a marketing score.</h2>
          </div>
          <div className="button-row">
            <Link className="button primary" href="/login">
              Open console <ArrowRight size={16} />
            </Link>
            <Link className="button secondary" href="/diagnostics/phase-1">
              Phase 1 diagnostics
            </Link>
          </div>
        </section>
      </main>
      <footer className="public-footer">
        <span>Self Healing Load Balancer</span>
        <span>
          Evidence-Bounded Minimum-Scope Healing · preliminary engineering
          research
        </span>
      </footer>
    </div>
  );
}

export function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("researcher@shlb.local");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        let detail = "The supplied credentials could not be authenticated.";
        try {
          const problem = (await response.json()) as { detail?: string };
          detail = problem.detail ?? detail;
        } catch {
          // Keep the bounded, account-neutral fallback.
        }
        throw new Error(detail);
      }
      const returnTo = new URLSearchParams(window.location.search).get(
        "returnTo",
      );
      const destination = returnTo?.startsWith("/app") ? returnTo : "/app";
      router.replace(destination);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The control API is unavailable.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <PublicHeader />
      <main id="main-content" className="auth-main">
        <section className="auth-context">
          <span className="eyebrow">Local control-plane access</span>
          <h1>Sign in to an environment you are authorized to operate.</h1>
          <p>
            Sessions are intended to be server-side, project-scoped, and
            auditable. The browser never receives HAProxy Runtime or Data Plane
            credentials.
          </p>
          <ul className="check-list">
            <li>
              <LockKeyhole size={16} aria-hidden="true" /> Secure HttpOnly
              session contract
            </li>
            <li>
              <ShieldCheck size={16} aria-hidden="true" /> Role and environment
              authorization
            </li>
            <li>
              <KeyRound size={16} aria-hidden="true" /> No default production
              credential
            </li>
          </ul>
        </section>
        <section className="auth-card" aria-labelledby="login-title">
          <div>
            <span className="section-kicker">Console access</span>
            <h2 id="login-title">Sign in</h2>
            <p>Use your local project account.</p>
          </div>
          <form onSubmit={onSubmit} noValidate>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                className="icon-button"
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            <button
              className="button primary full"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
          {error && (
            <div className="notice warning" role="alert">
              <CircleAlert size={17} aria-hidden="true" />
              <span>
                <strong>Sign-in failed.</strong> {error}
              </span>
            </div>
          )}
          <div className="auth-demo-link">
            <span>Need a read-only product tour?</span>
            <Link href="/app?demo=1">
              Open labelled demo <ArrowRight size={15} />
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}

const setupSteps = [
  "Project",
  "Environment",
  "Connectivity",
  "Topology",
  "Safety review",
];

export function SetupPage() {
  const [step, setStep] = useState(0);
  const [labEnabled, setLabEnabled] = useState(false);
  const [projectName, setProjectName] = useState("Local reliability lab");
  const progress = Math.round(((step + 1) / setupSteps.length) * 100);
  const currentContent = useMemo(() => {
    switch (step) {
      case 0:
        return (
          <>
            <label htmlFor="project-name">Project name</label>
            <input
              id="project-name"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
            />
            <label htmlFor="project-slug">Project slug</label>
            <input id="project-slug" defaultValue="local-reliability-lab" />
            <p className="field-help">
              Project identity scopes every future query, event, action, and
              audit record.
            </p>
          </>
        );
      case 1:
        return (
          <>
            <label htmlFor="environment-name">Environment name</label>
            <input id="environment-name" defaultValue="Local traffic lab" />
            <label htmlFor="environment-kind">Environment kind</label>
            <select id="environment-kind" defaultValue="LAB">
              <option>DEV</option>
              <option>LAB</option>
              <option>DEMO</option>
              <option>PILOT</option>
            </select>
            <label htmlFor="control-mode">Initial control mode</label>
            <select id="control-mode" defaultValue="OBSERVE_ONLY">
              <option>OBSERVE_ONLY</option>
              <option>RULES_ONLY</option>
              <option>MANUAL</option>
            </select>
            <label className="check-control">
              <input
                type="checkbox"
                checked={labEnabled}
                onChange={(event) => setLabEnabled(event.target.checked)}
              />
              Enable isolated Research Lab capability
            </label>
          </>
        );
      case 2:
        return (
          <>
            <label htmlFor="allowed-cidr">Backend control boundary</label>
            <input
              id="allowed-cidr"
              defaultValue="private backend_net · internal Docker DNS only"
              disabled
            />
            <label htmlFor="haproxy-endpoint">HAProxy Runtime authority</label>
            <input
              id="haproxy-endpoint"
              defaultValue="worker-only Unix socket · preconfigured"
              disabled
            />
            <label htmlFor="credential-ref">Structural Data Plane API</label>
            <input
              id="credential-ref"
              defaultValue="not deployed in this prototype"
              disabled
            />
            <div className="notice neutral">
              <ShieldCheck size={17} />
              <span>
                The API and browser receive no Runtime socket, backend network,
                or structural HAProxy authority. Only the sole-writer worker can
                perform predeclared absolute mutations.
              </span>
            </div>
          </>
        );
      case 3:
        return (
          <>
            <div className="setup-topology">
              <div>
                <strong>NGINX</strong>
                <small>edge</small>
              </div>
              <span>→</span>
              <div>
                <strong>HAProxy</strong>
                <small>data plane</small>
              </div>
              <span>→</span>
              <div>
                <strong>4 pools</strong>
                <small>route groups</small>
              </div>
              <span>→</span>
              <div>
                <strong>3 instances</strong>
                <small>300 capacity units</small>
              </div>
            </div>
            <div className="validation-list">
              <p>
                <Check size={16} />
                Route groups have deterministic priority
              </p>
              <p>
                <Check size={16} />
                12 logical memberships share 3 physical capacities
              </p>
              <p>
                <Check size={16} />
                No ambiguous route match detected
              </p>
            </div>
          </>
        );
      default:
        return (
          <>
            <div className="review-list">
              <div>
                <span>Project</span>
                <strong>{projectName}</strong>
              </div>
              <div>
                <span>Initial mode</span>
                <strong>OBSERVE_ONLY</strong>
              </div>
              <div>
                <span>Physical reserve floor</span>
                <strong>50%</strong>
              </div>
              <div>
                <span>Cross-instance retry</span>
                <strong>At most 1 · hard policy</strong>
              </div>
              <div>
                <span>Research Lab</span>
                <strong>
                  {labEnabled ? "Enabled for LAB only" : "Disabled"}
                </strong>
              </div>
            </div>
            <div className="notice warning">
              <CircleAlert size={17} />
              <span>
                <strong>Guided enrollment is a design preview.</strong> Use{" "}
                <code>./local-up</code> for the seeded working LAB; this page
                does not create Runtime authority or mutate the active
                environment.
              </span>
            </div>
          </>
        );
    }
  }, [labEnabled, projectName, step]);

  return (
    <div className="setup-page">
      <PublicHeader />
      <main id="main-content" className="setup-main">
        <aside className="setup-sidebar">
          <span className="eyebrow">Project setup</span>
          <h1>Define trust before control.</h1>
          <p>
            Register a finite topology, physical capacity, and hard safety
            policy before any automation can be considered.
          </p>
          <ol>
            {setupSteps.map((label, index) => (
              <li
                className={
                  index === step ? "current" : index < step ? "complete" : ""
                }
                key={label}
              >
                <span>{index < step ? <Check size={14} /> : index + 1}</span>
                {label}
              </li>
            ))}
          </ol>
        </aside>
        <section className="setup-card" aria-labelledby="setup-step-title">
          <div className="setup-card-header">
            <div>
              <span className="section-kicker">
                Step {step + 1} of {setupSteps.length}
              </span>
              <h2 id="setup-step-title">{setupSteps[step]}</h2>
            </div>
            <span className="mono">{progress}%</span>
          </div>
          <div
            className="progress-track"
            aria-label={`${progress}% complete`}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span style={{ width: `${progress}%` }} />
          </div>
          <div className="setup-fields">{currentContent}</div>
          <div className="setup-actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => setStep((value) => Math.max(0, value - 1))}
              disabled={step === 0}
            >
              <ChevronLeft size={16} />
              Back
            </button>
            {step < setupSteps.length - 1 ? (
              <button
                className="button primary"
                type="button"
                onClick={() =>
                  setStep((value) => Math.min(setupSteps.length - 1, value + 1))
                }
              >
                Continue
                <ChevronRight size={16} />
              </button>
            ) : (
              <Link className="button primary" href="/app">
                Review demo console
                <ArrowRight size={16} />
              </Link>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
