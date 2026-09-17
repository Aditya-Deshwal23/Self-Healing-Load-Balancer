"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowRightLeft,
  Beaker,
  BookOpen,
  Boxes,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  CircleUserRound,
  Command,
  FlaskConical,
  GitCompareArrows,
  Grid3X3,
  History,
  Menu,
  Moon,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Route,
  Search,
  Server,
  Settings,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
  TerminalSquare,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import {
  consoleRoutes,
  primaryNavGroups,
  titleForPath,
  type ConsoleRoute,
} from "@/lib/routes";
import { useDemoSnapshot } from "@/lib/demo/provider";
import { useControlPlane } from "@/lib/use-control-plane";
import { useSmallViewport } from "@/lib/use-small-viewport";
import { useOperationalSummary } from "@/lib/api/operations";

const iconMap: Record<string, LucideIcon> = {
  command: Command,
  topology: Network,
  matrix: Grid3X3,
  traffic: Activity,
  backends: Server,
  incidents: AlertTriangle,
  actions: ArrowRightLeft,
  reintegrate: History,
  versions: Boxes,
  metrics: ChartNoAxesCombined,
  logs: TerminalSquare,
  faults: FlaskConical,
  experiments: Beaker,
  baselines: GitCompareArrows,
  policies: SlidersHorizontal,
  settings: Settings,
};

type ThemePreference = "light" | "dark" | "system";

function setThemePreference(preference: ThemePreference) {
  const resolved =
    preference === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : preference;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preference;
  localStorage.setItem("shlb-theme", preference);
}

function CommandPalette({
  open,
  onClose,
  navigationRoutes,
  incidentOnly = false,
  includeDemoEntities = false,
}: {
  open: boolean;
  onClose: () => void;
  navigationRoutes: ConsoleRoute[];
  incidentOnly?: boolean;
  includeDemoEntities?: boolean;
}) {
  const router = useRouter();
  const { incident, instances, routes } = useDemoSnapshot();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const options = useMemo(() => {
    const fullEntityOptions = [
      ...routes.map((route) => ({
        label: route.label,
        detail: `${route.criticality} route · ${route.requestsPerSecond} req/s`,
        path: `/app/traffic/matrix?route=${route.id}`,
        group: "Routes",
      })),
      ...instances.map((instance) => ({
        label: instance.label,
        detail: `${instance.version} · ${instance.utilization}% physical utilization`,
        path: `/app/backends/${instance.id}`,
        group: "Backends",
      })),
      {
        label: incident.id,
        detail: `${incident.classification} · ${incident.status}`,
        path: `/app/incidents/${incident.id}`,
        group: "Incidents",
      },
    ];
    const demoEntityOptions = includeDemoEntities ? fullEntityOptions : [];
    const entityOptions = incidentOnly
      ? demoEntityOptions.filter((item) => item.group === "Incidents")
      : demoEntityOptions;
    const navigation = navigationRoutes.map((route) => ({
      label: route.label,
      detail: route.group,
      path: route.path,
      group: "Navigation",
    }));
    return [...navigation, ...entityOptions]
      .filter((item) =>
        `${item.label} ${item.detail}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      )
      .slice(0, 12);
  }, [
    includeDemoEntities,
    incident,
    incidentOnly,
    instances,
    navigationRoutes,
    query,
    routes,
  ]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (open && dialog) {
      triggerRef.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setActive(0);
      if (!dialog.open) dialog.showModal();
      window.setTimeout(() => inputRef.current?.focus(), 0);
    } else if (!open && dialog?.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    setActive((value) => Math.min(value, Math.max(options.length - 1, 0)));
  }, [options.length]);

  if (!open) return null;

  function closePalette() {
    if (dialogRef.current?.open) dialogRef.current.close();
    onClose();
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  }

  function select(path: string) {
    closePalette();
    router.push(path);
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => Math.min(value + 1, options.length - 1));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    }
    if (event.key === "Enter" && options[active]) {
      event.preventDefault();
      select(options[active].path);
    }
    if (event.key === "Escape") closePalette();
  }

  return (
    <dialog
      className="command-dialog"
      ref={dialogRef}
      onCancel={(event) => {
        event.preventDefault();
        closePalette();
      }}
      aria-labelledby="command-title"
    >
      <div className="command-search">
        <Search aria-hidden="true" size={18} />
        <label className="sr-only" htmlFor="command-query" id="command-title">
          Search commands and entities
        </label>
        <input
          ref={inputRef}
          id="command-query"
          role="combobox"
          aria-expanded="true"
          aria-controls="command-results"
          aria-activedescendant={
            options[active] ? `command-option-${active}` : undefined
          }
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Go to a route, backend, incident, or view…"
        />
        <kbd>esc</kbd>
        <button
          className="icon-button"
          type="button"
          onClick={closePalette}
          aria-label="Close command palette"
        >
          <X size={17} />
        </button>
      </div>
      <div
        className="command-results"
        id="command-results"
        role="listbox"
        aria-label="Command results"
      >
        {options.length ? (
          options.map((option, index) => (
            <button
              id={`command-option-${index}`}
              type="button"
              role="option"
              aria-selected={active === index}
              className={active === index ? "active" : ""}
              key={`${option.group}-${option.label}`}
              onMouseEnter={() => setActive(index)}
              onClick={() => select(option.path)}
            >
              <span>
                <strong>{option.label}</strong>
                <small>{option.detail}</small>
              </span>
              <span className="command-group">{option.group}</span>
            </button>
          ))
        ) : (
          <div className="command-empty">
            <Search size={20} />
            <p>No matching entity in this snapshot.</p>
          </div>
        )}
      </div>
      <footer className="command-footer">
        <span>
          <kbd>↑</kbd>
          <kbd>↓</kbd> navigate
        </span>
        <span>
          <kbd>↵</kbd> open
        </span>
        <span>Routing commands always open an impact review.</span>
      </footer>
    </dialog>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const control = useControlPlane();
  const operationalSummary = useOperationalSummary();
  const { demoMeta, environments } = useDemoSnapshot();
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [environmentId, setEnvironmentId] = useState<string>("lab-local");
  const [theme, setTheme] = useState<ThemePreference>("light");
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const smallViewport = useSmallViewport();
  const fixtureEnvironment =
    environments.find((environment) => environment.id === environmentId) ??
    environments[0];
  const currentEnvironment =
    control.state === "live" && control.status
      ? {
          id: control.status.environment.id,
          label: control.status.environment.name,
          kind: control.status.environment.kind,
          mode: control.status.environment.mode,
          safeMode: control.status.environment.mode === "SAFE_MODE",
          reason:
            "Automatic Runtime mutations are paused until an authorized operator clears the control condition.",
          startedAt: "start time unavailable",
          suppressedActions: 0,
          lastKnownGood: "not established",
        }
      : fixtureEnvironment;
  const environmentOptions =
    control.state === "live" && control.status
      ? [currentEnvironment]
      : environments;
  const pageTitle = titleForPath(pathname);

  const availableRoutes = useMemo(
    () =>
      consoleRoutes.filter(
        (route) =>
          route.primary &&
          (!smallViewport || route.mobile) &&
          (!route.capability ||
            (route.capability === "lab" &&
              demoMeta.labCapability &&
              control.state !== "live" &&
              currentEnvironment.kind === "LAB") ||
            (route.capability === "lab" &&
              control.state === "live" &&
              control.capabilities?.features.lab &&
              currentEnvironment.kind === "LAB")),
      ),
    [
      control.capabilities?.features,
      control.state,
      currentEnvironment.kind,
      demoMeta.labCapability,
      smallViewport,
    ],
  );

  useEffect(() => {
    if (control.state === "live" && control.status) {
      setEnvironmentId(control.status.environment.id);
    }
  }, [control.state, control.status]);

  useEffect(() => {
    const saved =
      (localStorage.getItem("shlb-theme") as ThemePreference | null) ?? "light";
    setTheme(saved);
  }, []);

  useEffect(() => {
    function onGlobalKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((value) => !value);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setThemeMenuOpen(false);
        setUserMenuOpen(false);
      }
    }
    window.addEventListener("keydown", onGlobalKeyDown);
    return () => window.removeEventListener("keydown", onGlobalKeyDown);
  }, []);

  function chooseTheme(next: ThemePreference) {
    setTheme(next);
    setThemePreference(next);
    setThemeMenuOpen(false);
  }

  return (
    <div className={`app-shell ${railCollapsed ? "rail-collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside
        className={`app-rail ${mobileNavOpen ? "mobile-open" : ""}`}
        aria-label="Primary navigation"
      >
        <div className="rail-brand">
          <Link
            className="brand"
            href="/app"
            aria-label="Self Healing Load Balancer command center"
          >
            <span className="product-mark" aria-hidden="true">
              <Route size={18} />
            </span>
            {!railCollapsed && <span>SHLB Console</span>}
          </Link>
          <button
            className="icon-button desktop-rail-toggle"
            type="button"
            onClick={() => setRailCollapsed((value) => !value)}
            aria-label={
              railCollapsed ? "Expand navigation" : "Collapse navigation"
            }
          >
            {railCollapsed ? (
              <PanelLeftOpen size={17} />
            ) : (
              <PanelLeftClose size={17} />
            )}
          </button>
          <button
            className="icon-button mobile-close"
            type="button"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>
        <nav className="rail-nav">
          {primaryNavGroups.map((group) => {
            const groupRoutes = availableRoutes.filter(
              (route) => route.group === group,
            );
            if (!groupRoutes.length) return null;
            return (
              <section
                key={group}
                aria-labelledby={`nav-${group.replace(/\s/g, "-").toLowerCase()}`}
              >
                {!railCollapsed && (
                  <h2 id={`nav-${group.replace(/\s/g, "-").toLowerCase()}`}>
                    {group}
                  </h2>
                )}
                {groupRoutes.map((route) => {
                  const Icon = iconMap[route.icon] ?? Route;
                  const active =
                    pathname === route.path ||
                    (route.path !== "/app" &&
                      pathname.startsWith(`${route.path}/`));
                  return (
                    <Link
                      href={route.path}
                      className={active ? "active" : ""}
                      aria-current={active ? "page" : undefined}
                      title={railCollapsed ? route.label : undefined}
                      key={route.path}
                      onClick={() => setMobileNavOpen(false)}
                    >
                      <Icon aria-hidden="true" size={17} />
                      {!railCollapsed && <span>{route.label}</span>}
                      {!railCollapsed &&
                        route.label === "Incidents" &&
                        (operationalSummary.data?.active_incidents.length ??
                          0) > 0 && (
                          <span
                            className="nav-count"
                            aria-label={`${operationalSummary.data?.active_incidents.length} active incidents`}
                          >
                            {operationalSummary.data?.active_incidents.length}
                          </span>
                        )}
                    </Link>
                  );
                })}
              </section>
            );
          })}
        </nav>
        <div className="rail-foot">
          {!railCollapsed ? (
            <>
              <span
                className={`status-tag ${control.state === "live" ? "success" : "neutral"}`}
              >
                {control.state === "live"
                  ? "RULES-ONLY LIVE"
                  : control.state === "checking"
                    ? "CHECKING SESSION"
                    : "SIMULATED DATA"}
              </span>
              <p>
                {control.state === "live"
                  ? "Real evidence, durable actions, HAProxy readback, verification, and staged recovery."
                  : (control.error ??
                    "Bounded fixtures; no HAProxy authority.")}
              </p>
              <Link href="/diagnostics/phase-1">
                System boundaries <ChevronRight size={14} />
              </Link>
            </>
          ) : (
            <span
              className={`rail-demo-dot ${control.state === "live" ? "live" : ""}`}
              title={
                control.state === "live"
                  ? "Rules-only control plane connected"
                  : "Simulated data"
              }
            />
          )}
        </div>
      </aside>

      <div className="shell-main">
        <header className="global-header">
          <button
            className="icon-button mobile-menu"
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={19} />
          </button>
          <div className="breadcrumb" aria-label="Breadcrumb">
            <span>{currentEnvironment.label}</span>
            <ChevronRight size={13} aria-hidden="true" />
            <strong>{pageTitle}</strong>
          </div>
          <div className="header-controls">
            <label className="environment-switcher">
              <span className="sr-only">Project and environment</span>
              <Server aria-hidden="true" size={15} />
              <select
                value={currentEnvironment.id}
                onChange={(event) => setEnvironmentId(event.target.value)}
                disabled={
                  control.state === "live" && environmentOptions.length === 1
                }
              >
                {environmentOptions.map((environment) => (
                  <option value={environment.id} key={environment.id}>
                    {environment.label}
                  </option>
                ))}
              </select>
              <ChevronDown aria-hidden="true" size={13} />
            </label>
            <span
              className={`mode-indicator ${currentEnvironment.safeMode ? "danger" : ""}`}
            >
              <ShieldCheck size={14} aria-hidden="true" />
              {currentEnvironment.mode}
            </span>
            <span
              className="freshness-indicator"
              title={
                control.state === "live"
                  ? "The browser is authenticated; telemetry and Runtime freshness appear in the Command Center."
                  : "This view uses a bounded fixture snapshot."
              }
            >
              <span
                className={`connection-shape ${control.streamState === "connected" ? "" : "offline"}`}
                aria-hidden="true"
              />
              {control.state === "live"
                ? `Telemetry live · SSE ${control.streamState}`
                : control.state === "checking"
                  ? "Session · checking"
                  : "Simulated · offline"}
            </span>
            <button
              className="command-trigger"
              type="button"
              onClick={() => setPaletteOpen(true)}
            >
              <Search size={15} aria-hidden="true" />
              <span>Search or command</span>
              <kbd>⌘K</kbd>
            </button>
            <div className="theme-control">
              <button
                className="icon-button"
                type="button"
                onClick={() => {
                  setThemeMenuOpen((value) => !value);
                  setUserMenuOpen(false);
                }}
                aria-haspopup="menu"
                aria-expanded={themeMenuOpen}
                aria-label={`Theme: ${theme}`}
              >
                {theme === "dark" ? (
                  <Moon size={17} />
                ) : theme === "light" ? (
                  <Sun size={17} />
                ) : (
                  <Sun size={17} />
                )}
              </button>
              {themeMenuOpen && (
                <div
                  className="menu-popover theme-menu"
                  role="menu"
                  aria-label="Theme preference"
                >
                  {(["light", "dark", "system"] as const).map((item) => (
                    <button
                      type="button"
                      role="menuitemradio"
                      aria-checked={theme === item}
                      onClick={() => chooseTheme(item)}
                      key={item}
                    >
                      {item === "light" ? (
                        <Sun size={15} />
                      ) : item === "dark" ? (
                        <Moon size={15} />
                      ) : (
                        <Settings size={15} />
                      )}
                      <span>{item[0].toUpperCase() + item.slice(1)}</span>
                      {theme === item && <Check size={14} />}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Link
              className="icon-button"
              href="/#method"
              aria-label="Help and technical method"
            >
              <CircleHelp size={17} />
            </Link>
            <div className="user-control">
              <button
                className="user-button"
                type="button"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                onClick={() => {
                  setUserMenuOpen((value) => !value);
                  setThemeMenuOpen(false);
                }}
                disabled={!control.session}
              >
                <CircleUserRound size={18} />
                <span>
                  {control.session?.scopes[0]?.role.replace("_", " ") ??
                    "Viewer"}
                </span>
                <ChevronDown size={13} />
              </button>
              {userMenuOpen && control.session && (
                <div
                  className="menu-popover user-menu"
                  role="menu"
                  aria-label="User menu"
                >
                  <div className="user-menu-identity">
                    <strong>{control.session.user.email}</strong>
                    <span>
                      {control.session.scopes[0]?.team_name ?? "No team scope"}
                    </span>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setUserMenuOpen(false);
                      void control.logout();
                    }}
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {currentEnvironment.safeMode && (
          <div className="safe-mode-strip" role="alert">
            <ShieldAlert aria-hidden="true" size={18} />
            <div>
              <strong>SAFE_MODE — {currentEnvironment.reason}</strong>
              <span>
                Started {currentEnvironment.startedAt} ·{" "}
                {currentEnvironment.suppressedActions} actions suppressed · last
                known good {currentEnvironment.lastKnownGood}
              </span>
            </div>
            <Link href="/app/settings#safe-mode">
              Authorized recovery <ChevronRight size={15} />
            </Link>
          </div>
        )}

        {control.state === "demo" && (
          <div className="fixture-strip" role="note">
            <BookOpen size={14} aria-hidden="true" />
            <span>
              <strong>Simulated data.</strong> This explicit{" "}
              <code>?demo=1</code> view uses bounded fixtures and cannot claim a
              HAProxy mutation.
            </span>
            <span className="mono">{demoMeta.displayTime}</span>
          </div>
        )}
        <div className="mobile-safety-strip" role="note">
          <ShieldAlert size={14} aria-hidden="true" />
          <span>
            Read and acknowledge surface only. Routing, policy, and fault
            controls are unavailable at this width.
          </span>
        </div>
        <main className="console-content" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
      {mobileNavOpen && (
        <button
          className="mobile-nav-scrim"
          type="button"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close navigation overlay"
        />
      )}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        navigationRoutes={availableRoutes}
        incidentOnly={smallViewport}
        includeDemoEntities={control.state === "demo"}
      />
    </div>
  );
}
