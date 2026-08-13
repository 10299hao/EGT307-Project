import { useEffect, useMemo, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  ArrowClockwise, Bell, Brain, Broadcast, CaretRight, Check, CheckCircle,
  CaretDoubleLeft, CaretDoubleRight, ClockCounterClockwise, Database, Funnel,
  GearSix, HardDrives, Lightning, List, ListChecks, MagnifyingGlass, Pulse,
  ShieldCheck, Siren, SquaresFour, Stack, Warning, X,
} from "@phosphor-icons/react";
import signalMap from "./signal-map.svg";
import {
  EMPTY_SERVICES, EMPTY_STATS, VIEW_COPY, formatTime, getJson, percent, titleCase,
} from "./portal";

gsap.registerPlugin(useGSAP);

// Sidebar pages are kept beside their icons because icons are React components.
const navigation = [
  { id: "overview", label: "Overview", icon: SquaresFour },
  { id: "incidents", label: "Incidents", icon: Siren },
  { id: "activity", label: "Activity", icon: ClockCounterClockwise },
  { id: "system", label: "System", icon: Stack },
];

// Small presentational components shared by multiple dashboard pages.
function SeverityBadge({ severity }) {
  return <span className={`severity-badge ${severity}`}><i />{severity}</span>;
}

function ServiceState({ label, state }) {
  const healthy = ["online", "configured", "connected", "demo data", "live streams"].includes(state);
  return <span className="service-state"><i className={healthy ? "healthy" : "neutral"} /><b>{label}</b><small>{state}</small></span>;
}

function Sidebar({ activeView, onNavigate, services, collapsed, mobileOpen, onToggle, onCloseMobile }) {
  return (
    <aside className={`dashboard-sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="sidebar-brand">
        <span className="brand-mark"><Pulse weight="bold" /></span>
        <span className="brand-copy"><b>LogSentinel</b><small>Incident Portal</small></span>
        <button className="sidebar-toggle" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed}>
          {collapsed ? <CaretDoubleRight /> : <CaretDoubleLeft />}
        </button>
        <button className="mobile-sidebar-close" onClick={onCloseMobile} aria-label="Close navigation"><X /></button>
      </div>

      <nav className="sidebar-nav" aria-label="Portal navigation">
        {navigation.map(({ id, label, icon: Icon }) => (
          <button key={id} className={activeView === id ? "active" : ""} onClick={() => onNavigate(id)} data-tooltip={label} aria-current={activeView === id ? "page" : undefined}>
            <Icon weight={activeView === id ? "fill" : "regular"} />
            <span>{label}</span>
            {id === "incidents" && <i className="nav-count">{services.openCount}</i>}
          </button>
        ))}
      </nav>

      <div className="sidebar-context" data-tooltip={`HDFS simulation: ${services.mode}`}>
        <span>Environment</span>
        <div><i /><p><b>HDFS simulation</b><small>{services.mode}</small></p></div>
      </div>
    </aside>
  );
}

function Topbar({ activeView, lastUpdated, loading, services, incidents, notificationOpen, accountOpen, onOpenMobile, onToggleNotifications, onToggleAccount, onRefresh, onSelectIncident, onNavigate }) {
  const [title, description] = VIEW_COPY[activeView];
  const isLive = services.mode === "live streams";
  const notifications = incidents.filter((incident) => !incident.acknowledged).slice(0, 4);
  return (
    <header className="dashboard-topbar">
      <button className="icon-button mobile-menu-button" onClick={onOpenMobile} aria-label="Open navigation"><List /></button>
      <div className="topbar-heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="topbar-actions">
        <span className={`live-indicator ${isLive ? "is-live" : "is-demo"}`}><i />{isLive ? "Redis live" : "Demo records"}</span>
        <button className="icon-button" onClick={onRefresh} aria-label="Refresh portal data" disabled={loading}>
          <ArrowClockwise className={loading ? "spinning" : ""} />
        </button>
        <div className="topbar-popover-wrap">
          <button className={`icon-button notification-button ${notificationOpen ? "active" : ""}`} onClick={onToggleNotifications} aria-label="Open incident notifications" aria-expanded={notificationOpen}><Bell />{notifications.length > 0 && <i />}</button>
          {notificationOpen && <div className="topbar-popover notification-popover">
            <div className="popover-head"><div><b>Needs review</b><small>{notifications.length} recent open incidents</small></div><button onClick={() => onNavigate("incidents")}>View queue</button></div>
            <div className="notification-list">
              {notifications.length ? notifications.map((incident) => <button key={incident.incident_id} onClick={() => onSelectIncident(incident)}><SeverityBadge severity={incident.severity} /><span><b>{incident.incident_id}</b><small>{incident.block_id}</small></span><CaretRight /></button>) : <p>There are no unacknowledged incidents.</p>}
            </div>
          </div>}
        </div>
        <div className="topbar-popover-wrap account-wrap">
          <button className={`account-trigger ${accountOpen ? "active" : ""}`} onClick={onToggleAccount} aria-label="Open operator information" aria-expanded={accountOpen}><span>M</span><b>Minghao</b></button>
          {accountOpen && <div className="topbar-popover account-popover">
            <div className="operator-summary"><span>M</span><div><b>Minghao</b><small>Portal operator</small></div></div>
            <dl><div><dt>Environment</dt><dd>HDFS simulation</dd></div><div><dt>Data source</dt><dd>{services.mode}</dd></div><div><dt>Portal version</dt><dd>1.0.0</dd></div></dl>
          </div>}
        </div>
      </div>
      <div className="update-line">
        {lastUpdated ? `Last updated ${lastUpdated.toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "Connecting to the portal API"}
      </div>
    </header>
  );
}

function DataModeNotice({ services }) {
  const isLive = services.mode === "live streams";
  return (
    <section className={`data-mode-notice ${isLive ? "is-live" : "is-demo"}`} aria-live="polite">
      <span><Database weight="duotone" /></span>
      <div>
        <b>{isLive ? "Showing integrated microservice data" : "Showing seeded demonstration records"}</b>
        <p>{isLive
          ? `Incidents arrive through ${services.incident_stream}; action requests are sent to Ethan through ${services.action_request_stream}.`
          : "These records are safe examples for developing the portal before the Analyzer and Executor are connected. They are not live model predictions."}</p>
      </div>
      <code>{services.data_source || "checking-source"}</code>
    </section>
  );
}

function MetricCard({ label, value, note, icon: Icon, tone }) {
  return (
    <article className={`metric-card ${tone || ""}`}>
      <div><span>{label}</span><Icon weight="duotone" /></div>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}

function IncidentTable({ incidents, compact = false, selectedId, onSelect }) {
  return (
    <div className={`incident-table ${compact ? "compact" : ""}`}>
      <div className="incident-table-head">
        <span>Incident</span><span>Detection</span><span>AI confidence</span><span>Action</span><span>Received</span><span />
      </div>
      <div className="incident-table-body">
        {incidents.length ? incidents.map((incident) => (
          <button key={incident.incident_id} className={`incident-row ${selectedId === incident.incident_id ? "selected" : ""}`} onClick={() => onSelect(incident)}>
            <span className="incident-identity"><SeverityBadge severity={incident.severity} /><b>{incident.incident_id}</b></span>
            <span className="incident-detection"><b>{titleCase(incident.category)}</b><small>{incident.block_id}</small></span>
            <span className="incident-confidence"><b>{percent(incident.anomaly_probability)}</b><i><em style={{ width: percent(incident.anomaly_probability) }} /></i></span>
            <span className={`action-status ${incident.action_result?.status || incident.action_request?.status || "pending"}`}>
              {incident.action_result?.status === "completed" ? <CheckCircle weight="fill" /> : <ClockCounterClockwise weight="fill" />}
              {incident.action_result?.status || (incident.action_request?.status === "sent" ? "sent" : "pending")}
            </span>
            <span className="incident-time">{formatTime(incident.created_at)}</span>
            <CaretRight className="row-caret" />
          </button>
        )) : (
          <div className="empty-state"><CheckCircle weight="duotone" /><h3>No incidents found</h3><p>Change the filters or wait for a new Analyzer message.</p></div>
        )}
      </div>
    </div>
  );
}

function ServicePanel({ services, onOpenSystem }) {
  const items = [
    ["Portal API", services.portal, Pulse],
    ["Incident database", services.database, Database],
    ["Redis Streams", services.redis, HardDrives],
    ["Log Collector", services.collector, Broadcast],
    ["Contract bridge", services.integration_bridge, Stack],
    ["AI Analyzer", services.analyzer, Brain],
    ["Automation Executor", services.executor, Lightning],
    ["Desktop alerts", services.local_notifications, Broadcast],
  ];
  return (
    <article className="panel service-panel">
      <div className="panel-title"><div><h2>Service health</h2><p>Current portal dependencies</p></div><span className="all-systems"><i />Portal ready</span></div>
      <div className="service-list">
        {items.map(([label, state, Icon]) => (
          <div key={label}><span className="service-icon"><Icon weight="duotone" /></span><p><b>{label}</b><small>{state}</small></p><i className={["online", "configured"].includes(state) ? "healthy" : "neutral"} /></div>
        ))}
      </div>
      {onOpenSystem && <button className="text-button" onClick={onOpenSystem}>Open system details <CaretRight /></button>}
    </article>
  );
}

function Overview({ incidents, stats, services, onSelect, onNavigate }) {
  const recent = incidents.slice(0, 4);
  return (
    <div className="view overview-view">
      <DataModeNotice services={services} />
      <section className="metric-grid">
        <MetricCard label="Open incidents" value={stats.open_incidents} note={`${stats.critical_open} critical awaiting review`} icon={Siren} tone="critical-card" />
        <MetricCard label="AI confidence" value={percent(stats.average_confidence)} note="Average anomaly confidence" icon={Brain} />
        <MetricCard label="Actions completed" value={stats.completed_actions} note="Approved dry-run actions" icon={ShieldCheck} tone="mint-card" />
        <MetricCard label="History stored" value={stats.total_incidents} note="Searchable incident records" icon={Database} />
      </section>

      <section className="overview-grid">
        <article className="panel recent-panel">
          <div className="panel-title"><div><h2>Recent incidents</h2><p>Latest anomalies received from the Analyzer</p></div><button className="text-button" onClick={() => onNavigate("incidents")}>View all <CaretRight /></button></div>
          <IncidentTable incidents={recent} compact onSelect={onSelect} />
        </article>
        <ServicePanel services={services} onOpenSystem={() => onNavigate("system")} />

        <article className="panel severity-panel">
          <div className="panel-title"><div><h2>Severity distribution</h2><p>Incidents currently in history</p></div><Funnel weight="duotone" /></div>
          <div className="severity-chart">
            {["critical", "high", "medium", "low"].map((level) => {
              const count = stats.by_severity[level] || 0;
              const width = Math.max(5, (count / Math.max(stats.total_incidents, 1)) * 100);
              return <div key={level}><span>{level}</span><i><em className={level} style={{ width: `${width}%` }} /></i><b>{count}</b></div>;
            })}
          </div>
        </article>

        <article className="panel response-panel">
          <div className="response-art" style={{ backgroundImage: `url(${signalMap})` }} />
          <div><span><Lightning weight="fill" />Executor request enabled</span><h2>Every response remains controlled.</h2><p>The portal sends a recommended action to Ethan's Executor but never runs the command itself.</p></div>
        </article>
      </section>
    </div>
  );
}

function IncidentFilters({ search, severity, status, setSearch, setSeverity, setStatus, onClear, hasFilters }) {
  return (
    <div className="filter-bar">
      <label className="search-field"><MagnifyingGlass /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search incident ID, block or category" /></label>
      <label><span>Severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All levels</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
      <label><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All incidents</option><option value="open">Open</option><option value="acknowledged">Acknowledged</option></select></label>
      <button className="clear-filter-button" onClick={onClear} disabled={!hasFilters}>Clear filters</button>
    </div>
  );
}

function IncidentsView({ incidents, selectedId, onSelect }) {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const filtered = useMemo(() => incidents.filter((incident) => {
    const hasSeverity = severity === "all" || incident.severity === severity;
    const hasStatus = status === "all" || (status === "open" ? !incident.acknowledged : incident.acknowledged);
    const text = `${incident.incident_id} ${incident.block_id} ${incident.category}`.toLowerCase();
    return hasSeverity && hasStatus && text.includes(search.toLowerCase());
  }), [incidents, search, severity, status]);
  const hasFilters = Boolean(search) || severity !== "all" || status !== "all";
  const clearFilters = () => { setSearch(""); setSeverity("all"); setStatus("all"); };

  return (
    <div className="view incidents-view">
      <div className="queue-summary"><span><b>{filtered.length}</b> incidents shown</span><span><i />Messages refresh every 10 seconds</span></div>
      <article className="panel incident-workbench">
        <IncidentFilters search={search} severity={severity} status={status} setSearch={setSearch} setSeverity={setSeverity} setStatus={setStatus} onClear={clearFilters} hasFilters={hasFilters} />
        <IncidentTable incidents={filtered} selectedId={selectedId} onSelect={onSelect} />
      </article>
    </div>
  );
}

function ActivityView({ incidents, onSelect }) {
  const activities = incidents.flatMap((incident) => {
    const records = [{ type: "detected", time: incident.created_at, incident, title: `${titleCase(incident.category)} detected`, detail: `${percent(incident.anomaly_probability)} anomaly confidence for ${incident.block_id}` }];
    if (incident.action_result) records.push({ type: "action", time: incident.action_result.created_at, incident, title: `${titleCase(incident.action_result.action)} selected`, detail: `${titleCase(incident.action_result.status)} in ${incident.action_result.mode.replace("_", "-")} mode` });
    if (incident.acknowledged_at) records.push({ type: "acknowledged", time: incident.acknowledged_at, incident, title: `Acknowledged by ${incident.acknowledged_by}`, detail: "Operator reviewed the evidence and automation result" });
    return records;
  }).sort((a, b) => new Date(b.time) - new Date(a.time));

  return (
    <div className="view activity-view">
      <article className="panel timeline-panel">
        <div className="panel-title"><div><h2>Incident timeline</h2><p>Combined Analyzer, Executor and operator activity</p></div><ListChecks weight="duotone" /></div>
        <div className="activity-timeline">
          {activities.map((item, index) => (
            <button key={`${item.incident.incident_id}-${item.type}-${index}`} onClick={() => onSelect(item.incident)}>
              <span className={`timeline-icon ${item.type}`}>{item.type === "detected" ? <Brain /> : item.type === "action" ? <Lightning /> : <Check />}</span>
              <span><b>{item.title}</b><small>{item.detail}</small></span>
              <time>{formatTime(item.time)}</time><CaretRight />
            </button>
          ))}
        </div>
      </article>
    </div>
  );
}

function SystemView({ services }) {
  const flow = [
    ["Log Collector", "Wei Jie", "Reads HDFS logs and publishes LogEvent", Broadcast],
    ["Log Analyzer", "Danish", "Predicts anomalies and publishes to IncidentStream", Brain],
    ["Incident Portal", "Minghao", "Stores Incident and opens operator case", SquaresFour],
    ["Automation Executor", "Ethan", "Consumes ActionStream and simulates the requested action", Lightning],
    ["Incident Portal", "Minghao", "Waits for an ActionResult using the same incident_id", CheckCircle],
  ];
  return (
    <div className="view system-view">
      <section className="system-grid">
        <ServicePanel services={services} />
        <article className="panel connection-panel">
          <div className="panel-title"><div><h2>Message configuration</h2><p>Values shared across the team</p></div><GearSix weight="duotone" /></div>
          <dl><div><dt>Data source</dt><dd>{services.data_source || "checking"}</dd></div><div><dt>Collector output</dt><dd>{services.collector_output_stream || "log-events"} / {services.collector_message_field || "data"}</dd></div><div><dt>Analyzer input</dt><dd>{services.analyzer_input_stream || "LogStream"} / {services.analyzer_message_field || "payload"}</dd></div><div><dt>Analyzer output</dt><dd>{services.incident_stream || "IncidentStream"}</dd></div><div><dt>Executor request</dt><dd>{services.action_request_stream || "ActionStream"} / {services.action_request_field || "command"}</dd></div><div><dt>Executor result</dt><dd>{services.action_result_stream || "action-results"} / payload</dd></div><div><dt>Portal adapter</dt><dd>{services.analyzer_contract_adapter || "danish-analyzer-v1"}</dd></div><div><dt>Upstream contract</dt><dd className={services.upstream_contract_match ? "contract-ok" : "contract-warning"}>{services.upstream_contract_match ? "Aligned" : "Collector and Analyzer need alignment"}</dd></div><div><dt>Join field</dt><dd>incident_id</dd></div></dl>
        </article>
        <article className="panel flow-panel">
          <div className="panel-title"><div><h2>Microservice flow</h2><p>How one HDFS anomaly reaches this dashboard</p></div><span className="flow-mode">{services.mode}</span></div>
          <div className="service-flow five-step-flow">
            {flow.map(([name, owner, detail, Icon], index) => <div key={`${name}-${index}`}><span><Icon weight="duotone" /></span><p><b>{name}</b><small>{owner}</small><em>{detail}</em></p>{index < flow.length - 1 && <CaretRight />}</div>)}
          </div>
        </article>
      </section>
    </div>
  );
}

function IncidentDrawer({ incident, onClose, onAcknowledge }) {
  const drawerRef = useRef(null);
  useGSAP(() => { gsap.fromTo(drawerRef.current, { x: "105%" }, { x: 0, duration: .48, ease: "power4.out" }); }, { scope: drawerRef });
  if (!incident) return null;
  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} aria-label="Close incident details" />
      <aside ref={drawerRef} className="incident-drawer" aria-label="Incident details">
        <div className="drawer-head"><div><SeverityBadge severity={incident.severity} /><h2>{incident.incident_id}</h2><p>{incident.block_id}</p></div><button className="icon-button" onClick={onClose} aria-label="Close drawer"><X /></button></div>
        <div className="drawer-content">
          <section className="confidence-card"><span>AI anomaly confidence</span><strong>{percent(incident.anomaly_probability)}</strong><i><em style={{ width: percent(incident.anomaly_probability) }} /></i><small>{incident.model_version}</small></section>
          <section className="drawer-section"><span>Detection</span><h3>{titleCase(incident.category)}</h3><p>The Analyzer found an unusual event sequence for this HDFS block.</p></section>
          <section className="drawer-section"><span>Supporting evidence</span>{incident.evidence?.length > 0 && <div className="evidence-list">{incident.evidence.map((event) => <div key={event.event_id}><b>{event.event_id}</b><span>{event.description}</span></div>)}</div>}{incident.evidence_summary && <div className="sequence-evidence"><b>Analyzer event sequence</b><code>{incident.evidence_summary}</code>{incident.total_events_analyzed != null && <small>{incident.total_events_analyzed} events analysed</small>}</div>}{!incident.evidence?.length && !incident.evidence_summary && <p>No evidence sequence was supplied by the Analyzer.</p>}</section>
          <section className="drawer-section action-section"><div className="section-line"><span>Executor response</span><i><ShieldCheck />Simulation only</i></div><h3>{titleCase(incident.action_result?.action || incident.recommended_action)}</h3>{incident.action_result?.command && <code>{incident.action_result.command}</code>}<p>{incident.action_result?.reason || (incident.action_request?.status === "sent" ? "Action request sent to Ethan's Executor. Waiting for his service to publish an ActionResult." : "Waiting to send the action request to the Automation Executor.")}</p></section>
          <section className="drawer-section audit-section"><span>Audit details</span><dl><div><dt>Detected</dt><dd>{formatTime(incident.created_at)}</dd></div><div><dt>Action status</dt><dd>{incident.action_result?.status || "Pending"}</dd></div><div><dt>Operator</dt><dd>{incident.acknowledged_by || "Not acknowledged"}</dd></div></dl></section>
        </div>
        <div className="drawer-footer"><button className="secondary-button" onClick={onClose}>Close</button><button className="primary-button" disabled={incident.acknowledged} onClick={() => onAcknowledge(incident.incident_id)}><Check />{incident.acknowledged ? `Acknowledged by ${incident.acknowledged_by}` : "Acknowledge incident"}</button></div>
      </aside>
    </>
  );
}

function App() {
  // App owns server data and global UI state; child components remain mostly presentational.
  const appRef = useRef(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("portal-sidebar-collapsed") === "true");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [activeView, setActiveView] = useState("overview");
  const [incidents, setIncidents] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);
  const [services, setServices] = useState(EMPTY_SERVICES);
  const [selected, setSelected] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadData = async () => {
    setLoading(true);
    try {
      // Load independent endpoints concurrently to keep refreshes quick.
      const [incidentData, statData, serviceData] = await Promise.all([
        getJson("/api/incidents"),
        getJson("/api/stats"),
        getJson("/api/service-status"),
      ]);
      setIncidents(incidentData.items);
      setStats(statData);
      setServices(serviceData);
      setLastUpdated(new Date());
      setError("");
    } catch {
      setError("The portal API is unavailable. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); const timer = window.setInterval(loadData, 10000); return () => window.clearInterval(timer); }, []);
  useEffect(() => { window.localStorage.setItem("portal-sidebar-collapsed", String(sidebarCollapsed)); }, [sidebarCollapsed]);
  useEffect(() => {
    const closePanels = (event) => {
      if (event.key !== "Escape") return;
      setMobileMenuOpen(false); setNotificationOpen(false); setAccountOpen(false); setSelected(null);
    };
    window.addEventListener("keydown", closePanels);
    return () => window.removeEventListener("keydown", closePanels);
  }, []);
  useGSAP(() => {
    gsap.fromTo(".dashboard-sidebar", { x: -28 }, { x: 0, duration: .7, ease: "power3.out", clearProps: "transform" });
    gsap.fromTo(".dashboard-topbar > *", { y: -15 }, { y: 0, stagger: .06, duration: .55, ease: "power3.out", clearProps: "transform" });
    gsap.fromTo(".metric-card", { y: 18 }, { y: 0, stagger: .06, duration: .5, ease: "power3.out", clearProps: "transform" });
  }, { scope: appRef });
  useGSAP(() => { gsap.fromTo(".view", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: .35, ease: "power2.out" }); }, { scope: appRef, dependencies: [activeView] });

  const selectIncident = async (incident) => {
    setNotificationOpen(false);
    setSelected(incident);
    try { setSelected(await getJson(`/api/incidents/${incident.incident_id}`)); } catch { /* keep the list record */ }
  };
  const acknowledge = async (id) => {
    try {
      const updated = await getJson(`/api/incidents/${id}/acknowledge`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operator: "Minghao" }) });
      setSelected(updated); setError(""); await loadData();
    } catch { setError("The incident could not be acknowledged. Please check the Portal API and try again."); }
  };

  const navigate = (view) => { setActiveView(view); setMobileMenuOpen(false); setNotificationOpen(false); setAccountOpen(false); };

  const serviceContext = { ...services, openCount: stats.open_incidents };
  return (
    <main ref={appRef} className={`dashboard-app ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      {mobileMenuOpen && <button className="mobile-sidebar-backdrop" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation" />}
      <Sidebar activeView={activeView} onNavigate={navigate} services={serviceContext} collapsed={sidebarCollapsed} mobileOpen={mobileMenuOpen} onToggle={() => setSidebarCollapsed((value) => !value)} onCloseMobile={() => setMobileMenuOpen(false)} />
      <section className="dashboard-workspace">
        <Topbar activeView={activeView} lastUpdated={lastUpdated} loading={loading} services={services} incidents={incidents} notificationOpen={notificationOpen} accountOpen={accountOpen} onOpenMobile={() => setMobileMenuOpen(true)} onToggleNotifications={() => { setNotificationOpen((value) => !value); setAccountOpen(false); }} onToggleAccount={() => { setAccountOpen((value) => !value); setNotificationOpen(false); }} onRefresh={loadData} onSelectIncident={selectIncident} onNavigate={navigate} />
        <div className="service-marquee"><div>{[0, 1].map((copy) => <span key={copy} aria-hidden={copy === 1}><ServiceState label="Portal" state={services.portal} /><ServiceState label="Database" state={services.database} /><ServiceState label="Redis" state={services.redis} /><ServiceState label="Executor" state={services.executor} /><ServiceState label="Mode" state={services.mode} /></span>)}</div></div>
        {error && <div className="error-banner"><Warning weight="fill" />{error}</div>}
        <div className="workspace-content">
          {activeView === "overview" && <Overview incidents={incidents} stats={stats} services={services} onSelect={selectIncident} onNavigate={navigate} />}
          {activeView === "incidents" && <IncidentsView incidents={incidents} selectedId={selected?.incident_id} onSelect={selectIncident} />}
          {activeView === "activity" && <ActivityView incidents={incidents} onSelect={selectIncident} />}
          {activeView === "system" && <SystemView services={services} />}
        </div>
      </section>
      {selected && <IncidentDrawer incident={selected} onClose={() => setSelected(null)} onAcknowledge={acknowledge} />}
    </main>
  );
}

export default App;
