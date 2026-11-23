import {
  activitySeed,
  campuses,
  equipmentSeed,
  incidentSeed,
  navigation,
  pipelineSteps,
  rentalSeed,
  readLocal,
  roleProfiles,
  series,
  writeLocal,
} from "./data.js";

const icons = {
  overview: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  equipment: '<path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5z"/><path d="m4.5 7.8 7.5 4.4 7.5-4.4M12 12.2V21"/>',
  rentals: '<path d="M4 5h16M4 10h10M4 15h8M4 20h6"/><path d="m17 14 3 3-3 3"/>',
  returns: '<path d="M20 7H8a4 4 0 0 0 0 8h2"/><path d="m5 4-3 3 3 3M12 19h8"/>',
  incidents: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.5v.1"/>',
  activity: '<path d="M4 12h3l2-6 4 12 2-6h5"/>',
  pipeline: '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10M6.5 8 11 16M17.5 8 13 16"/>',
  simulation: '<path d="M4 18V6M4 18h16"/><path d="m7 15 3-5 3 3 4-7 2 3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.7 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.7-1l-1.7.7-1.4-2.4 1.4-1.1A7 7 0 0 1 7 13l-1.8-.4v-2.8L7 9.4a7 7 0 0 1 .7-1.7L6.3 6.6l1.4-2.4 1.7.7a8 8 0 0 1 1.7-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.7 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 .7 1.7l1.8.4v2.8l-1.8.4a7 7 0 0 1-.7 1.7Z"/>',
};

const state = {
  role: readLocal("campusequip-role", "admin"),
  page: "overview",
  dataMode: "connecting",
  liveData: null,
  apiError: "",
  items: readLocal("campusequip-items", equipmentSeed),
  rentals: readLocal("campusequip-rentals", rentalSeed),
  incidents: readLocal("campusequip-incidents", incidentSeed),
  events: readLocal("campusequip-events", []),
  filter: "",
  statusFilter: "All statuses",
  categoryFilter: "All categories",
  pageNumber: 1,
  sortBy: "id",
  sortDirection: 1,
  incidentFilter: "All",
  simulationRate: 100,
  simulationRunning: false,
  simulationGenerated: 0,
  simulationProcessed: 0,
  simulationTimer: null,
};

const sampleData = {
  items: JSON.parse(JSON.stringify(state.items)),
  rentals: JSON.parse(JSON.stringify(state.rentals)),
  incidents: JSON.parse(JSON.stringify(state.incidents)),
  events: JSON.parse(JSON.stringify(state.events)),
};

const content = document.querySelector("#page-content");
const nav = document.querySelector("#primary-nav");
const roleSelect = document.querySelector("#role-select");
const toastRegion = document.querySelector("#toast-region");
const dialog = document.querySelector("#operation-dialog");
const dialogContent = document.querySelector("#dialog-content");
const pageNames = Object.fromEntries(navigation.map((entry) => [entry.id, entry.label]));

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));
const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.overview}</svg>`;
const profile = () => roleProfiles[state.role];

function setDataMode(mode) {
  if (mode === "live" && state.liveData) {
    state.dataMode = "live";
    state.items = state.liveData.equipment;
    state.rentals = state.liveData.contracts;
    state.incidents = state.liveData.incidents || [];
    state.events = state.liveData.activity || [];
  } else {
    state.dataMode = "sample";
    if (state.liveData) state.apiError = "";
    state.items = JSON.parse(JSON.stringify(sampleData.items));
    state.rentals = JSON.parse(JSON.stringify(sampleData.rentals));
    state.incidents = JSON.parse(JSON.stringify(sampleData.incidents));
    state.events = JSON.parse(JSON.stringify(sampleData.events));
  }
  render();
}

async function loadLiveData() {
  const refreshButton = document.querySelector("#refresh-data");
  if (refreshButton) refreshButton.disabled = true;
  state.dataMode = state.liveData ? state.dataMode : "connecting";
  renderConnectionStatus();
  try {
    const response = await fetch("/api/prototype/snapshot", { cache: "no-store" });
    const snapshot = await response.json();
    if (!response.ok || snapshot.ok !== true) {
      throw new Error(snapshot.erreur || `API request failed (${response.status})`);
    }
    state.liveData = snapshot;
    state.apiError = "";
    setDataMode("live");
  } catch (error) {
    state.apiError = error instanceof Error ? error.message : "API request failed";
    if (!state.liveData) state.dataMode = "sample";
    render();
  } finally {
    const button = document.querySelector("#refresh-data");
    if (button) button.disabled = false;
  }
}

function renderConnectionStatus() {
  const status = document.querySelector("#connection-status");
  const boundary = document.querySelector("#data-boundary");
  const banner = document.querySelector(".prototype-banner span:nth-child(2)");
  if (!status || !boundary || !banner) return;
  const connected = state.dataMode === "live";
  const connecting = state.dataMode === "connecting";
  status.classList.toggle("connected", connected);
  status.classList.toggle("disconnected", !connected && !connecting);
  status.innerHTML = `<i></i> ${connecting ? "CONNECTING" : connected ? "LIVE · LIMITED WRITE" : "SAMPLE DATA"}`;
  if (connected) {
    const unavailable = Object.entries(state.liveData.services || {})
      .filter(([, service]) => service.status !== "connected")
      .map(([name]) => name);
    banner.textContent = unavailable.length
      ? `Live records · return events can be added. Unavailable sources: ${unavailable.join(", ")}. Contracts do not track physical stock or due dates.`
      : "Connected to CampusEquip · record return events from Returns; other live views are read-only. Contracts do not track physical stock or due dates.";
    boundary.textContent = "LIVE PROJECT DATA · LIMITED WRITE";
  } else if (connecting) {
    banner.textContent = "Connecting to project data. Sample records are shown until the API responds.";
    boundary.textContent = "CONNECTING TO PROJECT DATA";
  } else {
    banner.textContent = state.apiError
      ? `API unavailable; showing illustrative sample data. ${state.apiError}`
      : "Sample mode selected. Records and actions are illustrative and stay in this browser.";
    boundary.textContent = state.apiError ? "SAMPLE DATA · API UNAVAILABLE" : "SAMPLE DATA · DEMO MODE";
  }
  const mini = document.querySelector(".pipeline-mini small");
  if (mini) mini.textContent = connected ? "Live status · limited write" : "Illustrative · not connected";
}

function saveState() {
  if (state.dataMode === "live") return;
  sampleData.items = JSON.parse(JSON.stringify(state.items));
  sampleData.rentals = JSON.parse(JSON.stringify(state.rentals));
  sampleData.incidents = JSON.parse(JSON.stringify(state.incidents));
  sampleData.events = JSON.parse(JSON.stringify(state.events));
  writeLocal("campusequip-items", state.items);
  writeLocal("campusequip-rentals", state.rentals);
  writeLocal("campusequip-incidents", state.incidents);
  writeLocal("campusequip-events", state.events);
}

function toast(message, title = "Prototype action") {
  const node = document.createElement("div");
  node.className = "toast";
  node.innerHTML = `<strong>${esc(title)}</strong><br>${esc(message)}`;
  toastRegion.append(node);
  window.setTimeout(() => node.remove(), 3900);
}

function setPage(page) {
  const visible = navigation.filter((entry) => !entry.adminOnly || state.role === "admin");
  state.page = visible.some((entry) => entry.id === page) ? page : "overview";
  state.filter = "";
  state.pageNumber = 1;
  document.querySelector("#breadcrumb-current").textContent = pageNames[state.page] || "Overview";
  document.querySelector(".sidebar").classList.remove("open");
  render();
}

function renderNavigation() {
  let html = "";
  for (const [index, item] of navigation.entries()) {
    if (item.adminOnly && state.role !== "admin") continue;
    if (index === 6 && state.role === "admin") html += '<div class="nav-section-label">DATA OPERATIONS</div>';
    html += `<button class="nav-item ${state.page === item.id ? "active" : ""}" type="button" data-page="${item.id}" aria-current="${state.page === item.id ? "page" : "false"}">
      <span class="nav-icon">${icon(item.icon)}</span><span class="nav-label">${item.label}</span>
      ${item.count && item.id !== "incidents" ? `<span class="nav-count">${item.count}</span>` : ""}
      ${item.id === "incidents" ? `<span class="nav-count">${state.incidents.filter((incident) => incident.state !== "Resolved").length}</span>` : ""}
    </button>`;
  }
  nav.innerHTML = html;
}

function render() {
  if (!roleProfiles[state.role]) state.role = "admin";
  if ((state.page === "pipeline" || state.page === "simulation") && state.role !== "admin") state.page = "overview";
  renderConnectionStatus();
  renderNavigation();
  roleSelect.value = state.role;
  document.querySelector("#profile-name").textContent = profile().name;
  document.querySelector("#profile-title").textContent = profile().title;
  document.querySelector("#profile-avatar").textContent = profile().initials;
  document.querySelector("#breadcrumb-current").textContent = pageNames[state.page] || "Overview";
  const pages = {
    overview: renderOverview,
    equipment: renderEquipment,
    rentals: renderRentals,
    returns: renderReturns,
    incidents: renderIncidents,
    activity: renderActivity,
    pipeline: renderPipeline,
    simulation: renderSimulation,
    settings: renderSettings,
  };
  content.innerHTML = (pages[state.page] || renderOverview)();
  bindPageControls();
}

function pageHeading({ eyebrow, title, description, aside = "", action = "" }) {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>
    ${action || (aside ? `<div class="heading-aside">${aside}</div>` : "")}</div>`;
}

function heroIllustration() {
  return `<div class="hero-art" aria-label="Architectural line illustration of a campus workshop">
    <span class="hero-index">FIELD NOTE NO. 014 / 2026</span><span class="hero-coordinate">34°01′ N &nbsp; 6°50′ W</span>
    <div class="hero-grid"></div>
    <svg class="hero-architecture" viewBox="0 0 330 230" role="img" aria-label="Abstract campus architecture and equipment shelves">
      <g fill="none" stroke="#575b51" stroke-width="1.15">
        <path d="M30 205V105L157 34l130 71v100M30 105h257M56 205v-85l100-56 104 56v85M75 205v-71h42v71m24 0v-71h42v71m23 0v-71h26v71"/>
        <path d="M30 126h257M30 148h257M30 171h257M157 34v80M57 120l100 15 99-15"/>
        <path d="m50 91 107-59 111 60M67 102 157 52l92 51M235 205v-41h32v41"/>
        <path d="M44 115v90m232-90v90M81 148h27m39 0h19m37 0h25M91 171h16m53 0h15m46 0h19"/>
      </g>
      <g fill="#a64f37">
        <circle cx="96" cy="162" r="2.2"/><circle cx="226" cy="138" r="2.2"/><circle cx="157" cy="47" r="2.2"/>
      </g>
      <g fill="none" stroke="#a64f37" stroke-width=".8" stroke-dasharray="3 4">
        <path d="M96 162 157 47 226 138"/><circle cx="157" cy="115" r="76"/>
      </g>
      <g fill="#575b51" font-family="monospace" font-size="7">
        <text x="36" y="218">NORTH WORKSHOP / RABAT</text><text x="226" y="63">01—03</text>
      </g>
    </svg>
    <span class="hero-caption">SPACE / EQUIPMENT / PEOPLE</span>
  </div>`;
}

function lineChart() {
  const width = 620;
  const height = 135;
  const max = Math.max(...series);
  const points = series.map((value, index) => {
    const x = 26 + index * ((width - 48) / (series.length - 1));
    const y = height - 19 - (value / (max * 1.1)) * (height - 38);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const last = points.split(" ").at(-1).split(",");
  const area = `${points} ${width - 22},${height - 19} 26,${height - 19}`;
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Illustrative equipment rental activity over 24 hours">
    <defs><linearGradient id="activity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#a64f37" stop-opacity=".19"/><stop offset="1" stop-color="#a64f37" stop-opacity="0"/></linearGradient></defs>
    <path d="M26 20H${width - 22}M26 61H${width - 22}M26 102H${width - 22}" stroke="#e5dfd4" stroke-width="1"/>
    <polygon points="${area}" fill="url(#activity-fill)"/><polyline points="${points}" fill="none" stroke="#a64f37" stroke-width="2"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="#a64f37" stroke="#fbf9f4" stroke-width="2"/>
    <text class="chart-axis" x="0" y="23">80</text><text class="chart-axis" x="0" y="64">40</text><text class="chart-axis" x="8" y="105">0</text>
    <text class="chart-axis" x="26" y="131">06:00</text><text class="chart-axis" x="210" y="131">12:00</text><text class="chart-axis" x="398" y="131">18:00</text><text class="chart-axis" x="570" y="131">NOW</text>
  </svg></div>`;
}

function campusRows() {
  return campuses.map((campus) => `<div class="campus-row">
    <div><div class="campus-name">${esc(campus.name)}</div><div class="campus-sub">${campus.units} units · ${campus.active} active loans</div></div>
    <div class="utilization"><div class="util-bar"><i style="width:${campus.utilization}%"></i></div>${campus.utilization}%</div>
    <span class="delta ${campus.delta.startsWith("−") ? "negative" : ""}">${campus.delta}</span>
  </div>`).join("");
}

function metric(label, value, note, direction = "") {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-foot"><span class="${direction}">${direction === "up" ? "↗" : direction === "down" ? "↘" : "·"}</span>${note}</div></div>`;
}

function eventRows(limit = 4) {
  const recent = [...state.events].reverse().slice(0, limit);
  if (!recent.length) {
    return `<div class="empty-state"><strong>Nothing in the local queue</strong>New prototype actions will appear here. No events have been sent to the real pipeline.</div>`;
  }
  return recent.map((event, index) => `<div class="queue-row">
    <span class="queue-index">${String(index + 1).padStart(2, "0")}</span>
    <div><strong>${esc(event.title)}</strong><small>${esc(event.detail)} · ${esc(event.time)}</small></div>
    <span class="pill ${event.status === "Accepted · local" ? "good" : "neutral"}">${esc(event.status)}</span>
  </div>`).join("");
}

function campusComparison() {
  return `<div class="campus-list">${campusRows()}</div>`;
}

function quickAction(label, detail, action, glyph) {
  return `<button class="quick-action" type="button" data-action="${action}"><span class="action-icon">${glyph}</span><strong>${label}</strong><small>${detail}</small></button>`;
}

function renderOverview() {
  if (state.dataMode === "live") return renderLiveOverview();
  const p = profile();
  if (state.role === "admin") {
    return `${`<div class="overview-hero"><div class="overview-copy"><div class="eyebrow">NETWORK OPERATIONS / 07 NOV 2026</div>
      <h1>${p.greeting}</h1><p>${p.intro}</p><div class="overview-actions">
      <button class="button" type="button" data-page="simulation">Open simulation lab <span aria-hidden="true">↗</span></button>
      <button class="button secondary" type="button" data-page="pipeline">Inspect data pipeline</button></div></div>${heroIllustration()}</div>`}
      <div class="metric-strip">
        ${metric("Campuses", "03", "North · Atlantic · South")}
        ${metric("Equipment units", "1,138", "Across 3 operating campuses", "up")}
        ${metric("Active rentals", "162", "14 due before 17:00")}
        ${metric("Open incidents", "16", "3 require attention", "down")}
      </div>
      <div class="overview-grid">
        <section class="panel chart-panel"><div class="panel-title"><div><div class="small-label">OPERATIONAL ACTIVITY · DEMO SERIES</div><h3>Equipment in circulation</h3></div><span class="pill neutral">ILLUSTRATIVE</span></div>
          <div class="chart-meta"><span><i class="legend-dot"></i>Active rentals</span><span>Last 24 hours</span><span>Sample, not measured</span></div>${lineChart()}</section>
        <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">CAMPUS COMPARISON</div><h3>Utilisation, by campus</h3></div><button class="text-button" type="button" data-page="equipment">View stock →</button></div>${campusComparison()}</section>
      </div>
      <div class="section-heading"><div><h2>One considered data path</h2><p>Every operation belongs to the existing pipeline; this prototype does not connect to it.</p></div><span class="mono-note">01 IN · 08 CHECKPOINTS</span></div>
      <div class="pipeline-ribbon">${pipelineSteps.slice(0, 6).map((step) => `<div class="pipeline-stage"><small>${step.number}</small><strong>${step.name}</strong><span>${step.detail}</span></div>`).join("")}</div>
      <div class="section-heading"><div><h2>On the desk</h2><p>Sample records for orientation only.</p></div><button class="text-button" type="button" data-page="activity">Full activity log →</button></div>
      <div class="overview-lower"><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">RECENT ACTIVITY</div><h3>Latest movements</h3></div><span class="pill neutral">SAMPLE</span></div><div class="queue-list">${activitySeed.slice(0, 3).map((entry, index) => `<div class="queue-row"><span class="queue-index">${String(index + 1).padStart(2, "0")}</span><div><strong>${entry.title}</strong><small>${entry.detail} · ${entry.time}</small></div><span class="pill ${entry.status === "Attention" ? "warn" : "neutral"}">${entry.status}</span></div>`).join("")}</div></section>
      <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">SHORTCUTS</div><h3>Move work forward</h3></div></div><div class="quick-actions">${quickAction("Equipment register", "1,138 units", "equipment", "＋")}${quickAction("Pipeline monitor", "Demo telemetry", "pipeline", "↗")}</div></section></div>`;
  }
  if (state.role === "manager") {
    const localItems = state.items.filter((item) => item.campus.includes("Rabat"));
    return `<div class="overview-hero"><div class="overview-copy"><div class="eyebrow">${p.campus.toUpperCase()} / LOCAL OPERATIONS</div><h1>${p.greeting}</h1><p>${p.intro}</p><div class="overview-actions"><button class="button" type="button" data-action="new-rental">Register a rental <span aria-hidden="true">↗</span></button><button class="button secondary" type="button" data-page="incidents">Review incidents</button></div></div>${heroIllustration()}</div>
      <div class="metric-strip">${metric("Local inventory", String(localItems.length).padStart(2, "0"), "Illustrative catalogue")}${metric("Active rentals", "23", "4 due today")}${metric("Available now", "08", "Ready at the desk", "up")}${metric("Needs attention", "03", "1 overdue · 2 checks", "down")}</div>
      <div class="overview-grid"><section class="panel chart-panel"><div class="panel-title"><div><div class="small-label">RABAT · SAMPLE ACTIVITY</div><h3>Borrowing rhythm</h3></div><span class="pill neutral">DEMO SERIES</span></div><div class="chart-meta"><span><i class="legend-dot"></i>Active loans</span><span>Past 24 hours</span></div>${lineChart()}</section>
      <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">AVAILABILITY SNAPSHOT</div><h3>Where stock sits</h3></div><span class="mono-note">${localItems.length} tracked</span></div><div class="availability-list">${["Media", "Audio", "Computing", "Laboratory"].map((category, index) => { const count = localItems.filter((item) => item.category === category).length; const available = localItems.filter((item) => item.category === category && item.status === "Available").length; const percentage = count ? Math.round((available / count) * 100) : 0; return `<div class="availability-row"><span>${category}</span><strong>${available} / ${count}</strong><div class="availability-track"><i style="width:${percentage}%"></i></div></div>`; }).join("")}</div></section></div>
      <div class="section-heading"><div><h2>Priority list</h2><p>Returns and incidents needing a human next step.</p></div><button class="text-button" type="button" data-page="rentals">All rentals →</button></div>
      <div class="overview-lower"><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">FOLLOW UP</div><h3>Before end of day</h3></div><span class="pill warn">2 DUE</span></div><div class="queue-list"><div class="queue-row"><span class="queue-index">01</span><div><strong>Field recorder · AUD-0088</strong><small>Mehdi Alaoui · due today, 14:30</small></div><span class="pill warn">Due today</span></div><div class="queue-row"><span class="queue-index">02</span><div><strong>Thermal camera · LAB-0062</strong><small>Omar Fassi · 2 days overdue</small></div><span class="pill bad">Overdue</span></div></div></section>
      <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">QUICK ACTIONS</div><h3>At your desk</h3></div></div><div class="quick-actions">${quickAction("Register a rental", "Issue available equipment", "new-rental", "＋")}${quickAction("Log an incident", "Create a condition report", "new-incident", "!")}${quickAction("Browse equipment", "Search this catalogue", "equipment", "⌕")}</div></section></div>`;
  }
  return `<div class="overview-hero"><div class="overview-copy"><div class="eyebrow">EQUIPMENT DESK / RABAT</div><h1>${p.greeting}</h1><p>${p.intro} Start a handover, check a return or find the right piece of kit.</p><div class="overview-actions"><button class="button terra" type="button" data-action="new-rental">＋ &nbsp;New rental</button><button class="button secondary" type="button" data-action="new-return">Register a return</button></div></div>${heroIllustration()}</div>
    <div class="metric-strip">${metric("Due at this desk", "04", "Next return · 14:30", "up")}${metric("Available equipment", "08", "Across 4 categories")}${metric("Returns today", "06", "2 still expected")}${metric("Open issues", "02", "1 needs review", "down")}</div>
    <div class="overview-lower"><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">TODAY / HANDOVER QUEUE</div><h3>Keep the day moving</h3></div><button class="text-button" type="button" data-page="rentals">All rentals →</button></div>
      <div class="queue-list"><div class="queue-row"><span class="queue-index">14:30</span><div><strong>Field recorder · AUD-0088</strong><small>Mehdi Alaoui · return due</small></div><span class="pill warn">Due today</span></div><div class="queue-row"><span class="queue-index">16:00</span><div><strong>Digital microscope · LAB-0037</strong><small>Nour Bennis · return due</small></div><span class="pill good">On time</span></div><div class="queue-row"><span class="queue-index">17:00</span><div><strong>Cinema camera · CAM-0142</strong><small>Salma Idrissi · reserved</small></div><span class="pill neutral">Upcoming</span></div></div>
      </section><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">QUICK ACTIONS</div><h3>Start with a clear record</h3></div></div><div class="quick-actions">${quickAction("Issue equipment", "Rental handover", "new-rental", "＋")}${quickAction("Record a return", "Inspect condition", "new-return", "↩")}${quickAction("Report a problem", "Open an incident", "new-incident", "!")}</div></section></div>
    <div class="section-heading"><div><h2>Recently handled</h2><p>Illustrative records; actions remain local to this prototype.</p></div><button class="text-button" type="button" data-page="activity">Activity history →</button></div><section class="panel panel-pad"><div class="queue-list">${eventRows(3)}</div></section>`;
}

function renderLiveOverview() {
  const data = state.liveData;
  const summary = data.summary;
  const activity = data.activity || [];
  const campusesLive = data.campuses || [];
  const eventCount = data.event_count;
  const recent = activity.slice(0, 4);
  const maximum = Math.max(...data.daily.map((entry) => entry.contracts), 1);
  return `${pageHeading({
    eyebrow: `${profile().campus.toUpperCase()} / LIVE READ-ONLY VIEW`,
    title: profile().greeting,
    description: "Real project records, read through the CampusEquip API. Role switching is for preview only and does not enforce access permissions.",
    aside: '<span class="pill good">LIVE DATA · READ ONLY</span>',
  })}
    <div class="metric-strip">
      ${metric("Campuses", summary.campuses.toLocaleString(), "PostgreSQL reference data")}
      ${metric("Equipment types", summary.equipment_types.toLocaleString(), "Not physical stock units")}
      ${metric("Stored contracts", summary.contracts.toLocaleString(), `${summary.accepted_contracts.toLocaleString()} paid or closed`)}
      ${metric("Event history", eventCount === null ? "Unavailable" : eventCount.toLocaleString(), "MongoDB records")}
    </div>
    <div class="overview-grid">
      <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">CAMPUS COMPARISON · LIVE</div><h3>Contracts by campus</h3></div><span class="pill neutral">POSTGRESQL</span></div>
        <div class="queue-list">${campusesLive.length ? campusesLive.map((campus, index) => `<div class="queue-row"><span class="queue-index">${String(index + 1).padStart(2, "0")}</span><div><strong>${esc(campus.name)}</strong><small>${campus.contracts.toLocaleString()} contracts · ${campus.historical_quantity.toLocaleString()} recorded rental quantity</small></div><span class="pill neutral">${campus.accepted_contracts.toLocaleString()} accepted</span></div>`).join("") : '<div class="empty-state"><strong>No campus records</strong>The live catalog is empty.</div>'}</div>
      </section>
      <section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">CONTRACT ACTIVITY · LIVE</div><h3>Latest recorded dates</h3></div><span class="pill neutral">NO FORECAST</span></div>
        <div class="availability-list">${data.daily.length ? data.daily.slice(-7).map((day) => `<div class="availability-row"><span>${esc(day.label)}</span><strong>${day.contracts}</strong><div class="availability-track"><i style="width:${Math.max(3, day.contracts / maximum * 100)}%"></i></div></div>`).join("") : '<div class="empty-state"><strong>No dated contracts</strong>There is no activity to chart.</div>'}</div>
      </section>
    </div>
    <div class="section-heading"><div><h2>Latest event records</h2><p>Read from MongoDB; these are pipeline events, not inferred stock movements.</p></div><button class="text-button" type="button" data-page="activity">Open activity →</button></div>
    <section class="panel panel-pad"><div class="queue-list">${recent.length ? recent.map((entry, index) => `<div class="queue-row"><span class="queue-index">${String(index + 1).padStart(2, "0")}</span><div><strong>${esc(entry.title)}</strong><small>${esc(entry.detail)} · ${esc(entry.time)}</small></div><span class="pill neutral">${esc(entry.type)}</span></div>`).join("") : `<div class="empty-state"><strong>${eventCount === null ? "MongoDB is unavailable" : "No event records yet"}</strong>${eventCount === null ? "Event history cannot be read right now." : "The live event history is empty."}</div>`}</div></section>
    <div class="section-heading"><div><h2>Data sources</h2><p>Live status, with no writes from this interface.</p></div><button class="text-button" type="button" id="refresh-live-data">Refresh now ↻</button></div>
    <div class="pipeline-overview">${Object.entries(data.services).map(([name, service]) => `<div class="pipeline-stat"><div class="small-label">${esc(name.toUpperCase())}</div><strong>${service.status === "connected" ? "Connected" : "Unavailable"}</strong><small>${service.status === "connected" ? "Read-only query" : "Source not responding"}</small></div>`).join("")}</div>`;
}

function renderLiveEquipment() {
  const query = state.filter.trim().toLowerCase();
  const matching = state.items.filter((item) =>
    `${item.id} ${item.name} ${item.category} ${item.campus}`.toLowerCase().includes(query)
    && (state.categoryFilter === "All categories" || item.category === state.categoryFilter))
    .sort((a, b) => String(a[state.sortBy] ?? "").localeCompare(String(b[state.sortBy] ?? "")) * state.sortDirection);
  const perPage = 10;
  const pages = Math.max(1, Math.ceil(matching.length / perPage));
  state.pageNumber = Math.min(state.pageNumber, pages);
  const current = matching.slice((state.pageNumber - 1) * perPage, state.pageNumber * perPage);
  const rows = current.map((item) => `<tr><td><span class="table-code">${esc(item.id)}</span></td>
    <td><span class="table-primary">${esc(item.name)}</span><span class="table-secondary">${esc(item.tag)}</span></td>
    <td>${esc(item.category)}</td><td>${esc(item.campus)}</td><td>${item.quantity.toLocaleString()}</td>
    <td>${item.contracts.toLocaleString()}</td><td><span class="pill neutral">Type only</span></td></tr>`).join("");
  const categories = [...new Set(state.items.map((item) => item.category))].sort();
  return `${pageHeading({ eyebrow: "POSTGRESQL / LIVE CATALOGUE", title: "Equipment, as recorded.", description: "These are catalogue types and historical rental quantities. The project schema does not track physical units, location, availability or condition." })}
    <div class="metric-strip">${metric("Equipment types", state.items.length.toLocaleString(), "PostgreSQL catalogue")}${metric("Historical quantity", state.items.reduce((sum, item) => sum + item.quantity, 0).toLocaleString(), "Across all contract lines")}${metric("Categories", categories.length.toLocaleString(), "Current reference data")}${metric("Physical availability", "Not tracked", "No unit-level inventory")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input id="equipment-search" type="search" value="${esc(state.filter)}" placeholder="Search type, category or campus" aria-label="Search equipment"></label>
      <select class="filter-select" id="category-filter" aria-label="Filter by category"><option>All categories</option>${categories.map((category) => `<option ${state.categoryFilter === category ? "selected" : ""}>${esc(category)}</option>`).join("")}</select>
      <span class="pill neutral">${matching.length} LIVE TYPES</span></div>
    <div class="table-wrap"><table class="data-table"><thead><tr>${[["id", "Catalogue ID"], ["name", "Equipment type"], ["category", "Category"], ["campus", "Recorded campuses"]].map(([key, label]) => `<th><button type="button" data-sort="${key}">${label} ${state.sortBy === key ? (state.sortDirection > 0 ? "↑" : "↓") : ""}</button></th>`).join("")}<th>Historical quantity</th><th>Contracts</th><th>Availability</th></tr></thead><tbody>${rows || '<tr><td colspan="7"><div class="empty-state"><strong>No matching equipment types</strong>Try another search or category.</div></td></tr>'}</tbody></table></div>
    <div class="table-footer"><span>Showing ${matching.length ? (state.pageNumber - 1) * perPage + 1 : 0}–${Math.min(state.pageNumber * perPage, matching.length)} of ${matching.length} catalogue types</span><div class="pagination"><button class="page-button" type="button" data-list-page="${state.pageNumber - 1}" ${state.pageNumber <= 1 ? "disabled" : ""}>‹</button>${visiblePageNumbers(pages, state.pageNumber).map((page) => `<button class="page-button ${state.pageNumber === page ? "active" : ""}" type="button" data-list-page="${page}">${page}</button>`).join("")}<button class="page-button" type="button" data-list-page="${state.pageNumber + 1}" ${state.pageNumber >= pages ? "disabled" : ""}>›</button></div></div>`;
}

function visiblePageNumbers(pages, current) {
  const start = Math.max(1, Math.min(current - 2, pages - 4));
  const end = Math.min(pages, start + 4);
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

function renderLiveRentals() {
  const accepted = state.liveData.summary.accepted_contracts;
  const statuses = [...new Set(state.rentals.map((rental) => rental.status))].sort();
  return `${pageHeading({ eyebrow: "POSTGRESQL / LIVE CONTRACTS", title: "Contracts, by record.", description: "The transactional database stores rental contracts and statuses. It does not contain expected return dates or current physical check-out state." })}
    <div class="metric-strip">${metric("Stored contracts", state.liveData.summary.contracts.toLocaleString(), "All database statuses")}${metric("Paid / closed", accepted.toLocaleString(), "Accepted in analysis")}${metric("Draft / cancelled", (state.liveData.summary.contracts - accepted).toLocaleString(), "Not treated as accepted")}${metric("Live rows shown", state.rentals.length.toLocaleString(), "Latest 200 contracts")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input type="search" id="rental-search" placeholder="Search client, equipment or contract" aria-label="Search contracts"></label><select class="filter-select" id="rental-filter"><option>All contracts</option>${statuses.map((status) => `<option>${esc(status)}</option>`).join("")}</select><span class="pill neutral">LIVE · READ ONLY</span></div>
    <div id="rental-table">${rentalsTable()}</div>
    <div class="notice"><strong>Source definition</strong> Rental rows are existing PostgreSQL contracts; they are not real-time checkout records.</div>`;
}

function renderLiveReturns() {
  const returns = state.events.filter((entry) => entry.type === "return");
  const contracts = state.rentals;
  return `${pageHeading({ eyebrow: "MONGODB / EVENT HISTORY", title: "Returns, when recorded.", description: "The project has no due-date or physical return register. This view lists only pipeline events explicitly recorded as returns." })}
    <div class="metric-strip">${metric("Recorded return events", returns.length.toLocaleString(), "Among latest 50 events")}${metric("Event history", state.liveData.event_count === null ? "Unavailable" : state.liveData.event_count.toLocaleString(), "MongoDB total")}${metric("Return inspections", "Not tracked", "No inspection schema")}${metric("Expected returns", "Not tracked", "No due-date field")}</div>
    <section class="panel form-panel"><div class="panel-title"><div><div class="small-label">AXES 3-4 / LIVE INGESTION</div><h3>Record a return event</h3><p>This creates an immutable MongoDB event through the validated pipeline. It does not change the PostgreSQL contract.</p></div><span class="pill good">LIVE PIPELINE</span></div><div class="rule"></div>
      <form id="live-return-form" class="form-grid">
        <div class="form-field"><label for="live-return-contract">Contract <span>*</span></label><select class="form-control" id="live-return-contract" name="contractId" required><option value="">Choose a real contract</option>${contracts.map((contract) => `<option value="${esc(contract.reference)}">${esc(contract.reference)} · ${esc(contract.borrower)} · ${esc(contract.status)}</option>`).join("")}</select></div>
        <div class="form-field"><label for="live-return-condition">Condition reported <span>*</span></label><select class="form-control" id="live-return-condition" name="condition" required><option value="">Select condition</option><option>Excellent</option><option>Good</option><option>Fair</option><option>Needs repair</option></select></div>
        <div class="form-field full"><label for="live-return-notes">Event notes</label><textarea class="form-control" id="live-return-notes" name="notes" maxlength="500" placeholder="Optional demo note (500 characters maximum)"></textarea></div>
        <div class="form-field full"><div class="form-actions"><small>Creates a hash-verified event lot, validates it, stores it in MongoDB, and refreshes the Redis projection.</small><button class="button terra" type="submit">Send through pipeline →</button></div></div>
      </form></section>
    <section class="panel panel-pad"><div class="queue-list">${returns.length ? returns.map((entry) => `<div class="queue-row"><span class="queue-index">${esc(entry.time)}</span><div><strong>${esc(entry.title)}</strong><small>${esc(entry.detail)}</small></div><span class="pill neutral">${esc(entry.status)}</span></div>`).join("") : '<div class="empty-state"><strong>No recent return events</strong>MongoDB has no return event in the latest event records.</div>'}</div></section>
    <div class="notice"><strong>Data boundary</strong>The event records that a return was reported. It does not update contract status, item availability, or inventory because those operations are not modeled in this project.</div>`;
}

function renderLiveIncidents() {
  const incidents = state.incidents;
  return `${pageHeading({ eyebrow: "MONGODB / LATEST OPERATIONAL STATE", title: "Incidents, as events.", description: "These are the latest incident or failure events by contract. Severity, assignee and resolution workflow are not stored in the event schema." })}
    <div class="metric-strip">${metric("Current incident states", incidents.length.toLocaleString(), "Latest state per contract")}${metric("Redis projection", state.liveData.incident_projection === null ? "Unavailable" : state.liveData.incident_projection.toLocaleString(), "Sorted incident view")}${metric("Severity", "Not tracked", "No severity field")}${metric("Assignments", "Not tracked", "No owner field")}</div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Event ID</th><th>Device</th><th>Event type</th><th>Contract</th><th>Observed</th><th>Severity</th></tr></thead><tbody>${incidents.length ? incidents.map((incident) => `<tr><td><span class="table-code">${esc(incident.reference || "—")}</span></td><td>${esc(incident.itemId || "—")}</td><td>${esc(incident.state)}</td><td>${esc(incident.detail.split(" · ")[0].replace(/^Contract /, ""))}</td><td>${esc(incident.time)}</td><td><span class="pill neutral">Not recorded</span></td></tr>`).join("") : '<tr><td colspan="6"><div class="empty-state"><strong>No current incident states</strong>MongoDB has no incident or failure event to show.</div></td></tr>'}</tbody></table></div>
    <div class="notice terracotta"><strong>Read-only connection</strong> Incident actions are unavailable in live mode; this project stores event history, not an incident workflow.</div>`;
}

function renderLiveActivity() {
  const types = [...new Set(state.events.map((entry) => entry.type))].sort();
  return `${pageHeading({ eyebrow: "MONGODB / LIVE EVENT HISTORY", title: "A record of what moved.", description: "Recent events read from MongoDB. Event history is authoritative for processed events; no browser-local actions are mixed into this list." })}
    <div class="metric-strip">${metric("Stored events", state.liveData.event_count === null ? "Unavailable" : state.liveData.event_count.toLocaleString(), "MongoDB total")}${metric("Recent rows", state.events.length.toLocaleString(), "Latest 50 records")}${metric("Rejected records", state.liveData.pipeline?.rejections === undefined ? "Unavailable" : state.liveData.pipeline.rejections.toLocaleString(), "MongoDB rejection journal")}${metric("Refresh", "Manual", "Use Refresh in the header")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input id="activity-search" type="search" placeholder="Search event, device or contract" aria-label="Search activity"></label><select id="activity-filter" class="filter-select"><option>All activity</option>${types.map((type) => `<option>${esc(type)}</option>`).join("")}</select><span class="pill neutral">MONGODB · READ ONLY</span></div>
    <div id="activity-table">${activityTable(state.events)}</div>`;
}

function renderLivePipeline() {
  const { pipeline, timescale } = state.liveData;
  const number = (value) => value === null || value === undefined ? "Unavailable" : Number(value).toLocaleString();
  const metrics = pipeline ? [
    ["Events stored", number(pipeline.events), "MongoDB events collection"],
    ["Validated", number(pipeline.validated), "Journalled batch records"],
    ["Accepted", number(pipeline.accepted), "Batch totals"],
    ["Rejected", number(pipeline.rejected), "Batch totals"],
    ["Duplicates", number(pipeline.copies), "Exact replays"],
    ["Conflicts", number(pipeline.conflicts), "Identity conflicts"],
    ["Quarantine records", number(pipeline.rejections), "MongoDB rejection journal"],
    ["Position samples", number(timescale?.positions), "TimescaleDB observations"],
    ["Task attempts", number(timescale?.tentatives), "TimescaleDB observations"],
    ["Task failures", number(timescale?.echecs), "Recorded Airflow attempts"],
    ["Mean task duration", timescale?.duree_moyenne_ms == null ? "Unavailable" : `${timescale.duree_moyenne_ms} ms`, "Measured task attempts"],
  ] : [];
  return `${pageHeading({ eyebrow: "LIVE DATA / READ-ONLY OBSERVABILITY", title: "The pipeline, by its records.", description: "Measured database and Airflow task-attempt records only. No simulated throughput, backlog or latency is presented as live telemetry." })}
    <div class="pipeline-overview">${metrics.map(([label, value, note]) => `<div class="pipeline-stat"><div class="small-label">${label}</div><strong>${value}</strong><small>${note}</small></div>`).join("") || '<div class="notice"><strong>MongoDB unavailable</strong> Pipeline batch metrics cannot be read.</div>'}</div>
    <div class="section-heading"><div><h2>Service connectivity</h2><p>All requests use read-only queries.</p></div><span class="pill neutral">SNAPSHOT ${esc(state.liveData.captured_at)}</span></div>
    <div class="overview-grid">${Object.entries(state.liveData.services).map(([name, service]) => `<section class="panel panel-pad"><div class="small-label">${esc(name.toUpperCase())}</div><h3 style="margin:9px 0 5px;font:500 19px var(--display)">${service.status === "connected" ? "Connected" : "Unavailable"}</h3><p style="margin:0;color:var(--ink-soft);font-size:10px;line-height:1.6">${service.status === "connected" ? "Source responded to a read-only query." : "This data source is currently unavailable."}</p></section>`).join("")}</div>
    <div class="section-heading"><div><h2>Recent processed batches</h2><p>Source: MongoDB ingestion journal.</p></div></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Campaign</th><th>Batch</th><th>Status</th><th>Validated</th><th>Accepted</th><th>Rejected</th><th>Started</th></tr></thead><tbody>${pipeline?.recent_batches?.length ? pipeline.recent_batches.map((batch) => `<tr><td>${esc(batch.campaign_id)}</td><td>${esc(batch.batch_no)}</td><td>${esc(batch.status)}</td><td>${number(batch.validated)}</td><td>${number(batch.accepted)}</td><td>${number(batch.rejected)}</td><td>${esc(batch.started_at || "—")}</td></tr>`).join("") : '<tr><td colspan="7"><div class="empty-state"><strong>No batch journal records</strong>The MongoDB batch collection is empty.</div></td></tr>'}</tbody></table></div>
    <div class="pipeline-flow">${pipelineSteps.map((step) => `<article class="flow-step"><span class="flow-step-id">${step.number} / CHECKPOINT</span><h3>${step.name}</h3><p>${step.detail}</p><span class="flow-store">${step.store}</span></article>`).join("")}</div>`;
}

function equipmentRows() {
  const query = state.filter.trim().toLowerCase();
  const matching = state.items.filter((item) => {
    const text = `${item.id} ${item.name} ${item.category} ${item.campus} ${item.location} ${item.tag}`.toLowerCase();
    return text.includes(query) && (state.statusFilter === "All statuses" || item.status === state.statusFilter)
      && (state.categoryFilter === "All categories" || item.category === state.categoryFilter);
  }).sort((a, b) => String(a[state.sortBy]).localeCompare(String(b[state.sortBy])) * state.sortDirection);
  const perPage = 7;
  const pages = Math.max(1, Math.ceil(matching.length / perPage));
  state.pageNumber = Math.min(state.pageNumber, pages);
  const current = matching.slice((state.pageNumber - 1) * perPage, state.pageNumber * perPage);
  const body = current.length ? current.map((item) => `<tr>
    <td><span class="table-code">${esc(item.id)}</span></td>
    <td><span class="table-primary">${esc(item.name)}</span><span class="table-secondary">${esc(item.tag)}</span></td>
    <td>${esc(item.category)}</td><td>${esc(item.campus)}</td>
    <td><span class="pill ${item.status === "Available" ? "good" : item.status === "Overdue" ? "bad" : item.status === "Service" ? "warn" : "neutral"}">${esc(item.status)}</span></td>
    <td>${esc(item.condition)}</td><td><button class="table-action" type="button" data-item="${esc(item.id)}">Details ↗</button></td></tr>`).join("")
    : '<tr><td colspan="7"><div class="empty-state"><strong>No equipment found</strong>Try a different search or filter.</div></td></tr>';
  return { body, count: matching.length, pages };
}

function renderEquipment() {
  if (state.dataMode === "live") return renderLiveEquipment();
  const { body, count, pages } = equipmentRows();
  return `${pageHeading({ eyebrow: `${profile().campus} / ASSET REGISTER`, title: "Equipment, accounted for.", description: "Search the shared sample catalogue by item, campus or location. Status and condition are kept distinct." })}
    <div class="metric-strip">${metric("Items in catalogue", state.items.length.toString().padStart(2, "0"), "Local sample dataset")}${metric("Available", state.items.filter((item) => item.status === "Available").length.toString().padStart(2, "0"), "Ready to issue")}${metric("On loan", state.items.filter((item) => item.status === "On loan").length.toString().padStart(2, "0"), "Across all sample sites")}${metric("Needs attention", state.items.filter((item) => ["Overdue", "Service"].includes(item.status)).length.toString().padStart(2, "0"), "Overdue or service", "down")}</div>
    <div class="toolbar"><label class="search-field"><span aria-hidden="true">⌕</span><input id="equipment-search" type="search" value="${esc(state.filter)}" placeholder="Search name, ID, category or campus" aria-label="Search equipment"></label>
      <select class="filter-select" id="status-filter" aria-label="Filter by status">${["All statuses", "Available", "On loan", "Overdue", "Service"].map((v) => `<option ${state.statusFilter === v ? "selected" : ""}>${v}</option>`).join("")}</select>
      <select class="filter-select" id="category-filter" aria-label="Filter by category">${["All categories", "Media", "Audio", "Computing", "Laboratory"].map((v) => `<option ${state.categoryFilter === v ? "selected" : ""}>${v}</option>`).join("")}</select>
      <span class="pill neutral">${count} RESULTS · SAMPLE</span></div>
    <div class="table-wrap"><table class="data-table"><thead><tr>
      ${[["id", "Asset ID"], ["name", "Equipment"], ["category", "Category"], ["campus", "Campus"]].map(([key, label]) => `<th><button type="button" data-sort="${key}">${label} ${state.sortBy === key ? (state.sortDirection > 0 ? "↑" : "↓") : ""}</button></th>`).join("")}
      <th>Status</th><th>Condition</th><th></th></tr></thead><tbody>${body}</tbody></table></div>
    <div class="table-footer"><span>Showing ${count ? (state.pageNumber - 1) * 7 + 1 : 0}–${Math.min(state.pageNumber * 7, count)} of ${count} illustrative assets</span><div class="pagination"><button class="page-button" type="button" data-list-page="${state.pageNumber - 1}" ${state.pageNumber <= 1 ? "disabled" : ""}>‹</button>${Array.from({ length: pages }, (_, i) => `<button class="page-button ${state.pageNumber === i + 1 ? "active" : ""}" type="button" data-list-page="${i + 1}">${i + 1}</button>`).join("")}<button class="page-button" type="button" data-list-page="${state.pageNumber + 1}" ${state.pageNumber >= pages ? "disabled" : ""}>›</button></div></div>`;
}

function rentalsTable(rentals = state.rentals) {
  if (!rentals.length) return '<div class="empty-state"><strong>No matching rentals</strong>Try another search or register a new rental.</div>';
  if (state.dataMode === "live") {
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Contract</th><th>Client</th><th>Equipment type(s)</th><th>Campus</th><th>Start date</th><th>Contract status</th></tr></thead><tbody>
      ${rentals.map((rental) => `<tr><td><span class="table-code">${esc(rental.reference)}</span></td><td><span class="table-primary">${esc(rental.borrower)}</span></td><td>${esc(rental.item)}<span class="table-secondary">${esc(rental.itemId)}</span></td><td>${esc(rental.campus)}</td><td>${esc(rental.start_date)}</td><td><span class="pill neutral">${esc(rental.status)}</span></td></tr>`).join("")}
      </tbody></table></div>`;
  }
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Reference</th><th>Borrower</th><th>Equipment</th><th>Campus</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>
    ${rentals.map((rental) => `<tr><td><span class="table-code">${esc(rental.reference)}</span></td><td><span class="table-primary">${esc(rental.borrower)}</span></td><td>${esc(rental.item)}<span class="table-secondary">${esc(rental.itemId)}</span></td><td>${esc(rental.campus)}</td><td>${esc(rental.due)}</td><td><span class="pill ${rental.status === "Overdue" ? "bad" : rental.status === "Due today" ? "warn" : rental.status === "On time" ? "good" : "neutral"}">${esc(rental.status)}</span></td><td><button class="table-action" type="button" data-action="new-return" data-prefill="${esc(rental.itemId)}">Return ↗</button></td></tr>`).join("")}
    </tbody></table></div>`;
}

function renderRentals() {
  if (state.dataMode === "live") return renderLiveRentals();
  const overdue = state.rentals.filter((rental) => rental.status === "Overdue").length;
  return `${pageHeading({ eyebrow: "LOAN REGISTER / SAMPLE RECORDS", title: "Rentals, with a clear due date.", description: "A practical view of equipment in circulation. Registering a rental below creates a local prototype event only.", action: '<button class="button terra" type="button" data-action="new-rental">＋ &nbsp;New rental</button>' })}
    <div class="metric-strip">${metric("Active loans", String(state.rentals.filter((r) => !["Returned", "Reserved"].includes(r.status)).length).padStart(2, "0"), "All sample campuses")}${metric("Due today", "04", "Across the desk")}${metric("Overdue", String(overdue).padStart(2, "0"), "Follow up with borrower", "down")}${metric("Reservations", "01", "Next issue · 17:00")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input type="search" id="rental-search" placeholder="Search borrower, item or reference" aria-label="Search rentals"></label><select class="filter-select" id="rental-filter"><option>All rentals</option><option>On time</option><option>Due today</option><option>Overdue</option><option>Reserved</option></select><span class="pill neutral">SAMPLE RECORDS</span></div>
    <div id="rental-table">${rentalsTable()}</div>
    <div class="section-heading"><div><h2>Before the handover</h2><p>Keep the operational record complete; ingestion is not simulated as a real database write.</p></div></div>
    <div class="pipeline-ribbon">${["Identify borrower", "Check availability", "Record due date", "Create event", "Validate fields", "Queue for pipeline"].map((step, index) => `<div class="pipeline-stage"><small>0${index + 1}</small><strong>${step}</strong><span>${index === 5 ? "Prototype queue only" : "Required checkpoint"}</span></div>`).join("")}</div>`;
}

function renderReturns() {
  if (state.dataMode === "live") return renderLiveReturns();
  const due = state.rentals.filter((rental) => ["Due today", "Overdue", "On time"].includes(rental.status));
  return `${pageHeading({ eyebrow: "DESK OPERATIONS / RETURN INSPECTION", title: "Bring equipment home.", description: "Match an item to its rental, inspect its condition and record what happens next." })}
    <div class="split-layout"><section class="panel form-panel"><div class="panel-title"><div><div class="small-label">RETURN CHECK-IN</div><h3>Record an equipment return</h3><p>Required fields are marked <span style="color:var(--terracotta)">*</span>.</p></div><span class="pill neutral">LOCAL PROTOTYPE</span></div><div class="rule"></div>
      <form id="return-form" class="form-grid">
        <div class="form-field"><label for="return-asset">Equipment ID <span>*</span></label><input class="form-control" id="return-asset" name="assetId" list="asset-options" placeholder="e.g. AUD-0088" required><datalist id="asset-options">${state.items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("")}</datalist></div>
        <div class="form-field"><label for="return-borrower">Borrower name <span>*</span></label><input class="form-control" id="return-borrower" name="borrower" placeholder="Name on the rental" required></div>
        <div class="form-field"><label for="return-condition">Condition on return <span>*</span></label><select class="form-control" id="return-condition" name="condition" required><option value="">Select condition</option><option>Excellent</option><option>Good</option><option>Fair</option><option>Needs repair</option></select></div>
        <div class="form-field"><label for="return-time">Received at <span>*</span></label><input class="form-control" id="return-time" name="time" type="datetime-local" required></div>
        <div class="form-field full"><label for="return-note">Inspection notes</label><textarea class="form-control" id="return-note" name="note" placeholder="Anything the next person should know?"></textarea><span class="form-hint">If something is damaged or missing, record an incident separately so the item is not re-issued.</span></div>
        <div class="form-field full"><label class="check-row"><input type="checkbox" name="complete" required> I have physically checked the item and its accessories.</label></div>
        <div class="form-field full"><div class="form-actions"><small>This prototype stores the event in local browser storage only. It is not sent to MongoDB or PostgreSQL.</small><button class="button terra" type="submit">Record return →</button></div></div>
      </form></section>
      <aside class="panel panel-pad"><div class="panel-title"><div><div class="small-label">EXPECTED AT THE DESK</div><h3>Returns in circulation</h3></div><span class="pill warn">${due.length} OPEN</span></div>
        <div class="side-note-list">${due.slice(0, 4).map((rental, index) => `<div class="side-note"><span class="side-note-index">0${index + 1}</span><div><strong>${esc(rental.item)} · ${esc(rental.itemId)}</strong><small>${esc(rental.borrower)}<br>${esc(rental.due)} · ${esc(rental.status)}</small><button class="table-action" type="button" data-action="new-return" data-prefill="${esc(rental.itemId)}">Start check-in →</button></div></div>`).join("")}</div>
        <div class="notice terracotta"><strong>Inspection principle</strong><br>Update availability only after the condition check. Flag an incident before the next rental if a safety or function issue is found.</div>
      </aside></div>`;
}

function renderIncidents() {
  if (state.dataMode === "live") return renderLiveIncidents();
  const filter = state.incidentFilter;
  const incidents = state.incidents.filter((incident) => filter === "All" || incident.state === filter);
  return `${pageHeading({ eyebrow: "CONDITION REPORTS / SAMPLE DATA", title: "A problem, made visible.", description: "Record the issue, identify the equipment and leave a clear next step for the team.", action: '<button class="button terra" type="button" data-action="new-incident">＋ &nbsp;Log an incident</button>' })}
    <div class="metric-strip">${metric("Open cases", String(state.incidents.filter((incident) => incident.state !== "Resolved").length).padStart(2, "0"), "Across all campuses")}${metric("High severity", String(state.incidents.filter((i) => i.severity === "High" && i.state !== "Resolved").length).padStart(2, "0"), "Review first", "down")}${metric("Awaiting inspection", "02", "Equipment held from issue")}${metric("Resolved this week", "07", "Illustrative sample", "up")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input id="incident-search" type="search" placeholder="Search ID, equipment or issue" aria-label="Search incidents"></label><select class="filter-select" id="incident-filter">${["All", "Open", "In review", "Assigned", "Resolved"].map((option) => `<option ${filter === option ? "selected" : ""}>${option}</option>`).join("")}</select><span class="pill neutral">${incidents.length} CASES · SAMPLE</span></div>
    <div id="incident-table">${incidentTable(incidents)}</div>
    <div class="section-heading"><div><h2>Response, not just reporting</h2><p>Use a clear severity and an assigned next action.</p></div></div>
    <div class="overview-grid"><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">WHEN AN ISSUE IS FOUND</div><h3>Contain, assess, resolve</h3></div></div><div class="side-note-list"><div class="side-note"><span class="side-note-index">01</span><div><strong>Hold unsafe equipment</strong><small>Change availability before another borrower can check it out.</small></div></div><div class="side-note"><span class="side-note-index">02</span><div><strong>Keep the detail factual</strong><small>Record symptoms and time observed; avoid guessing at a cause.</small></div></div><div class="side-note"><span class="side-note-index">03</span><div><strong>Give the next action an owner</strong><small>Repair, inspect, contact borrower or close with a reason.</small></div></div></div></section><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">DATA LIFECYCLE</div><h3>Incident event route</h3></div></div><div class="queue-list">${["Desk report", "Validation & deduplication", "Event history", "State projection"].map((label, index) => `<div class="queue-row"><span class="queue-index">0${index + 1}</span><div><strong>${label}</strong><small>${["Staff records a factual event", "Required IDs and fields checked", "MongoDB in the existing pipeline", "Redis view after processing"][index]}</small></div>${index < 3 ? '<span aria-hidden="true" class="mono">→</span>' : '<span class="pill neutral">NOT CONNECTED</span>'}</div>`).join("")}</div></section></div>`;
}

function incidentTable(incidents) {
  if (!incidents.length) return '<div class="panel empty-state"><strong>No incidents in this view</strong>Try another filter.</div>';
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Reference</th><th>Equipment / campus</th><th>What happened</th><th>Severity</th><th>Reported</th><th>State</th></tr></thead><tbody>${incidents.map((incident) => `<tr><td><span class="table-code">${esc(incident.reference)}</span></td><td><span class="table-primary">${esc(incident.item)}</span><span class="table-secondary">${esc(incident.itemId)} · ${esc(incident.campus)}</span></td><td>${esc(incident.title)}</td><td><span class="pill ${incident.severity === "High" ? "bad" : incident.severity === "Medium" ? "warn" : "neutral"}">${esc(incident.severity)}</span></td><td>${esc(incident.time)}</td><td><button class="pill ${incident.state === "Resolved" ? "good" : "neutral"} status-button" type="button" data-incident="${esc(incident.reference)}" title="Update sample incident state">${esc(incident.state)}</button></td></tr>`).join("")}</tbody></table></div>`;
}

function renderActivity() {
  if (state.dataMode === "live") return renderLiveActivity();
  const recent = [...state.events].reverse();
  const merged = [...recent.map((event) => ({ ...event, local: true })), ...activitySeed];
  return `${pageHeading({ eyebrow: "EVENT HISTORY / BROWSER-LOCAL DEMO", title: "A record of what moved.", description: "Sample activity alongside actions captured in this browser. Nothing here is an authoritative system-of-record history." })}
    <div class="metric-strip">${metric("Visible sample events", String(merged.length).padStart(2, "0"), "Seeded + local prototype events")}${metric("New local actions", String(state.events.length).padStart(2, "0"), "Not sent to the backend")}${metric("Accepted by pipeline", "—", "No live connection")}${metric("Data freshness", "Demo", "Illustrative timeline")}</div>
    <div class="toolbar"><label class="search-field"><span>⌕</span><input id="activity-search" type="search" placeholder="Search equipment, event or person" aria-label="Search activity"></label><select id="activity-filter" class="filter-select"><option>All activity</option><option>Rental</option><option>Return</option><option>Incident</option><option>Simulation</option></select><span class="pill neutral">LOCAL + SAMPLE</span></div>
    <div id="activity-table">${activityTable(merged)}</div>
    <div class="section-heading"><div><h2>What happens to an operation</h2><p>The designed route is visible; connecting it is a future implementation step.</p></div></div><div class="pipeline-ribbon">${pipelineSteps.slice(0, 6).map((step) => `<div class="pipeline-stage"><small>${step.number}</small><strong>${step.name}</strong><span>${step.store}</span></div>`).join("")}</div>`;
}

function activityTable(entries) {
  if (!entries.length) return '<div class="panel empty-state"><strong>No matching activity</strong>Try another search or type.</div>';
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Time</th><th>Operation</th><th>Detail</th><th>Origin</th><th>Status</th></tr></thead><tbody>${entries.map((entry) => `<tr><td><span class="table-code">${esc(entry.time)}</span></td><td><span class="table-primary">${esc(entry.type)}</span></td><td>${esc(entry.title)}<span class="table-secondary">${esc(entry.detail)}</span></td><td>${entry.local ? '<span class="pill terra">BROWSER LOCAL</span>' : esc(entry.source)}</td><td><span class="pill ${entry.status === "Attention" ? "warn" : entry.local ? "neutral" : "good"}">${esc(entry.status)}</span></td></tr>`).join("")}</tbody></table></div>`;
}

function renderPipeline() {
  if (state.dataMode === "live") return renderLivePipeline();
  const localCount = state.events.length;
  return `${pageHeading({ eyebrow: "DATA OFFICE / PIPELINE OBSERVABILITY", title: "Follow the event, not just the number.", description: "A conceptual view of the existing CampusEquip pipeline. The frontend is not connected to Airflow, PostgreSQL, MongoDB, Redis or TimescaleDB." })}
    <div class="notice terracotta"><strong>Demonstration view</strong> Metrics below are illustrative and are not measurements from your running services. Local prototype actions are shown separately in the queue.</div>
    <div class="section-heading"><div><h2>Illustrative run · sample batch 004</h2><p>Reference values demonstrate the information architecture; they do not represent a real run.</p></div><span class="pill neutral">NO LIVE TELEMETRY</span></div>
    <div class="pipeline-overview">${[["Events generated", "1,240", "Illustrative sample"], ["Events received", "1,238", "2 not delivered"], ["Accepted records", "1,211", "97.8% of received"], ["Rejected records", "19", "1.5% · sample"], ["Duplicates", "8", "0.6% · idempotent"], ["Latency p95", "184 ms", "Illustrative only"], ["Throughput", "82 / sec", "Sample window"], ["Error rate", "0.4%", "Illustrative only"]].map(([label, value, note]) => `<div class="pipeline-stat"><div class="small-label">${label}</div><strong>${value}</strong><small>${note}</small></div>`).join("")}</div>
    <div class="section-heading"><div><h2>Processing lifecycle</h2><p>Each operation should pass through validation and quality rules before it becomes visible.</p></div><span class="mono-note">8 STAGES · DESIGNED ROUTE</span></div>
    <div class="pipeline-flow">${pipelineSteps.map((step) => `<article class="flow-step"><span class="flow-step-id">${step.number} / CHECKPOINT</span><h3>${step.name}</h3><p>${step.detail}</p><span class="flow-store">${step.store}</span></article>`).join("")}</div>
    <div class="pipeline-architecture"><div class="arch-node"><span class="arch-mark">IN</span><strong>New operation</strong><small>Staff / simulation UI</small></div><span class="arch-arrow">→</span><div class="arch-node"><span class="arch-mark">QC</span><strong>Existing pipeline</strong><small>Validation · dedup · Airflow</small></div><span class="arch-arrow">→</span><div class="arch-node"><span class="arch-mark">DB</span><strong>Purpose-fit stores</strong><small>PostgreSQL · MongoDB · Redis</small></div><span class="arch-arrow">→</span><div class="arch-node"><span class="arch-mark">↗</span><strong>Operations view</strong><small>Future live integration</small></div></div>
    <div class="section-heading"><div><h2>Prototype event queue</h2><p>${localCount} action${localCount === 1 ? "" : "s"} stored in this browser only.</p></div><span class="pill neutral">NOT SENT TO PIPELINE</span></div>
    <section class="panel panel-pad"><div class="queue-list">${eventRows(8)}</div></section>
    <div class="section-heading"><div><h2>Data ownership</h2><p>One pipeline; purpose-built stores. Not one database per role.</p></div></div>
    <div class="overview-grid">${[["PostgreSQL", "Transactional contracts and rental data.", "SOURCE OF TRUTH"], ["MongoDB", "Immutable event history and ingestion journal.", "EVENT RECORD"], ["Redis", "Rebuildable operational state and short-lived views.", "LIVE PROJECTION"], ["TimescaleDB", "Time-series positions and task-attempt measures.", "ANALYTICAL"]].map(([name, text, label]) => `<section class="panel panel-pad"><div class="small-label">${label}</div><h3 style="margin:9px 0 5px;font:500 19px var(--display)">${name}</h3><p style="margin:0;color:var(--ink-soft);font-size:10px;line-height:1.6">${text}</p></section>`).join("")}</div>`;
}

function renderSimulation() {
  return `${pageHeading({ eyebrow: "ENGINEERING DESK / CONTROLLED DEMONSTRATION", title: "Push the pipeline, safely.", description: "A browser-only visual simulation of event volume and backlog. It never generates network traffic or writes to project services." })}
    <div class="notice terracotta"><strong>Simulation only</strong> The counter is a local estimate at the selected rate—not an actual throughput test and not data from Airflow or TimescaleDB.</div>
    <div class="section-heading"><div><h2>Rate bench</h2><p>Choose an event rate, observe the counter and stop at any time.</p></div><span class="pill neutral">NO BACKEND CONNECTION</span></div>
    <div class="sim-layout"><section class="sim-console"><div class="console-top"><span>CAMPUS EQUIP / EVENT BENCH / SESSION <span id="sim-session-id">LOCAL-001</span></span><span class="sim-status ${state.simulationRunning ? "running" : ""}" id="sim-status"><i></i><span>${state.simulationRunning ? "SIMULATING" : "STANDBY"}</span></span></div>
      <div class="console-reading"><div><small>EVENTS GENERATED · LOCAL ESTIMATE</small><strong id="sim-generated">${state.simulationGenerated.toLocaleString()}</strong><em id="sim-rate-readout">${state.simulationRate.toLocaleString()} events / second selected</em></div><div><small>BACKLOG · VISUAL ESTIMATE</small><strong id="sim-backlog">0</strong><em>Illustrative only · not measured</em></div></div>
      <div class="sim-chart" aria-label="Illustrative simulation throughput plot"><div class="sim-bars" id="sim-bars">${series.slice(-28).map((height) => `<i style="height:${Math.max(7, height - 5)}%"></i>`).join("")}</div></div><div class="sim-foot"><span>SESSION WINDOW</span><span>LIVE VIEW IS SIMULATED</span><span id="sim-runtime">00:00</span></div>
      <div class="backlog-line"><span>Simulated processing completion</span><strong id="sim-processed">${state.simulationProcessed.toLocaleString()} events</strong></div></section>
      <aside class="panel sim-controls"><div class="small-label">LOAD PROFILE</div><div class="panel-title"><div><h3>Select a target rate</h3><p>Four requested demonstration presets.</p></div></div><div class="rate-options">${[10, 100, 1000, 10000].map((rate) => `<button class="rate-button ${state.simulationRate === rate ? "active" : ""}" type="button" data-rate="${rate}">${rate.toLocaleString()} / sec</button>`).join("")}</div>
        <div class="sim-actions"><button class="button terra" type="button" id="simulation-start" ${state.simulationRunning ? "disabled" : ""}>▶ &nbsp;Start</button><button class="button secondary" type="button" id="simulation-stop" ${state.simulationRunning ? "" : "disabled"}>■ &nbsp;Stop</button></div>
        <p class="sim-explain"><strong>Safety note.</strong> Rate selection changes only an in-browser counter and chart. No requests, jobs or synthetic records are sent to the project databases.</p>
        <div class="rule"></div><div class="small-label">WHAT A REAL TEST WOULD MEASURE</div><div class="side-note-list"><div class="side-note"><span class="side-note-index">01</span><div><strong>Input vs. accepted</strong><small>Producer and consumer counts from a real run.</small></div></div><div class="side-note"><span class="side-note-index">02</span><div><strong>Latency & backlog</strong><small>Measured from task-attempt timestamps.</small></div></div></div></aside></div>`;
}

function renderSettings() {
  const p = profile();
  const live = state.dataMode === "live";
  return `${pageHeading({ eyebrow: "WORKSPACE / PREFERENCES", title: "A desk set to your role.", description: "Role selection previews the interface only; it is not authentication or access control." })}
    <div class="overview-grid"><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">ROLE PREVIEW</div><h3>Current view</h3><p>Role switching changes navigation and information hierarchy, not permissions.</p></div><span class="pill neutral">PREVIEW ONLY</span></div><div class="rule"></div>
      ${Object.entries(roleProfiles).map(([id, person]) => `<button class="quick-action role-option" type="button" data-role="${id}" style="width:100%;margin-bottom:8px;${id === state.role ? "border-color:var(--terracotta);background:var(--terra-pale)" : ""}"><span class="avatar role-avatar">${person.initials}</span><span style="flex:1"><strong>${person.title}</strong><small style="display:block;margin-top:3px;color:var(--muted)">${person.campus} · ${person.intro}</small></span>${id === state.role ? '<span class="pill terra">CURRENT</span>' : '<span class="mono">→</span>'}</button>`).join("")}
    </section><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">DATA MODE</div><h3>${live ? "Connected · limited write" : "Illustrative sample"}</h3><p>${live ? "Live data is read across the app; the Returns page can append an event through the pipeline." : "This session is using sample records stored in the browser."}</p></div><button class="button secondary" type="button" id="toggle-data-mode">${live ? "Use sample data" : state.liveData ? "Return to live data" : "Retry connection"}</button></div><div class="rule"></div><div class="side-note-list">${[["PostgreSQL", "Contracts, equipment types and reference data."], ["MongoDB", "Processed event history and ingestion journal."], ["Redis", "Rebuildable incident projection."], ["TimescaleDB", "Positions and measured task attempts."]].map(([name, detail], i) => `<div class="side-note"><span class="side-note-index">0${i + 1}</span><div><strong>${name}</strong><small>${detail}</small></div></div>`).join("")}</div></section></div>
    <div class="section-heading"><div><h2>Data boundaries</h2><p>Most live pages are read-only; Returns can append a validated event.</p></div></div><section class="panel panel-pad"><div class="notice terracotta"><strong>Schema limitation</strong><br>The existing project tracks equipment catalogue types and transactional contracts, but not physical inventory, due dates, condition checks, or incident assignment workflows. Those are not inferred by this interface.</div><div class="notice"><strong>Sample-only actions</strong><br>Rental and incident forms and the simulation are available only in sample mode. Live return events go through the validated pipeline. No database credentials are sent to the browser; the role switcher is not authentication.</div></section>
    ${live ? "" : `<div class="section-heading"><div><h2>Prototype data</h2><p>Seed records are illustrative; actions are saved only in this browser's local storage.</p></div></div><section class="panel panel-pad"><div class="panel-title"><div><div class="small-label">LOCAL SESSION</div><h3>Reset sample actions</h3><p>Clears locally created events and restores the sample catalogue.</p></div><button class="button secondary" type="button" id="reset-prototype">Reset this prototype</button></div></section>`}`;
}

function formMarkup(type) {
  const availableItems = state.items.filter((item) => item.status === "Available");
  if (type === "rental") {
    return `${pageHeading({ eyebrow: "DESK OPERATIONS / CHECK-OUT", title: "Issue equipment, clearly.", description: "Capture who is borrowing what, and when it is due." })}
      <div class="split-layout"><section class="panel form-panel"><div class="panel-title"><div><div class="small-label">NEW RENTAL</div><h3>Borrower and equipment</h3><p>Fields marked <span style="color:var(--terracotta)">*</span> are required.</p></div><span class="pill neutral">BROWSER LOCAL</span></div><div class="rule"></div>
        <form id="rental-form" class="form-grid"><div class="form-field"><label for="borrower-name">Borrower full name <span>*</span></label><input class="form-control" id="borrower-name" name="borrower" required placeholder="e.g. Lina Amrani"></div>
          <div class="form-field"><label for="borrower-id">Student or staff ID <span>*</span></label><input class="form-control" id="borrower-id" name="borrowerId" required placeholder="e.g. ST-2026-0418"></div>
          <div class="form-field full"><label for="rental-asset">Available equipment <span>*</span></label><select class="form-control" id="rental-asset" name="assetId" required><option value="">Choose an available item</option>${availableItems.map((item) => `<option value="${esc(item.id)}">${esc(item.id)} · ${esc(item.name)} — ${esc(item.location)}</option>`).join("")}</select><span class="form-hint">${availableItems.length} sample assets currently marked available.</span></div>
          <div class="form-field"><label for="rental-start">Issue time <span>*</span></label><input class="form-control" type="datetime-local" id="rental-start" name="start" required></div>
          <div class="form-field"><label for="rental-due">Expected return <span>*</span></label><input class="form-control" type="datetime-local" id="rental-due" name="due" required></div>
          <div class="form-field full"><label for="rental-purpose">Purpose or course</label><input class="form-control" id="rental-purpose" name="purpose" placeholder="Optional context for the desk"></div>
          <div class="form-field full"><label class="check-row"><input type="checkbox" required> Borrower has confirmed the equipment and due date.</label></div>
          <div class="form-field full"><div class="form-actions"><small>This action creates a prototype event in this browser. It does not create a contract in PostgreSQL or bypass the existing pipeline.</small><button class="button terra" type="submit">Review & record →</button></div></div></form></section>
        <aside class="panel panel-pad"><div class="panel-title"><div><div class="small-label">BEFORE ISSUE</div><h3>A complete handover</h3></div></div><div class="side-note-list"><div class="side-note"><span class="side-note-index">01</span><div><strong>Confirm the identity</strong><small>Use the institution's existing borrower reference.</small></div></div><div class="side-note"><span class="side-note-index">02</span><div><strong>Check the item</strong><small>Match its tag, condition and accessories.</small></div></div><div class="side-note"><span class="side-note-index">03</span><div><strong>Make the due date explicit</strong><small>The next shift needs one clear return time.</small></div></div></div><div class="notice">Operations in this prototype are <strong>browser-local examples</strong> until connected to the existing pipeline.</div></aside></div>`;
  }
  if (type === "return") return renderReturns();
  return `${pageHeading({ eyebrow: "DESK OPERATIONS / CONDITION REPORT", title: "Make the issue actionable.", description: "Record what happened and keep affected equipment out of circulation until it is safe." })}
    <div class="split-layout"><section class="panel form-panel"><div class="panel-title"><div><div class="small-label">NEW INCIDENT</div><h3>Equipment and observation</h3><p>Be specific; do not infer a cause.</p></div><span class="pill neutral">BROWSER LOCAL</span></div><div class="rule"></div>
      <form id="incident-form" class="form-grid"><div class="form-field"><label for="incident-asset">Equipment ID <span>*</span></label><input class="form-control" id="incident-asset" name="assetId" list="incident-assets" required placeholder="e.g. NET-0114"><datalist id="incident-assets">${state.items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join("")}</datalist></div>
        <div class="form-field"><label for="incident-severity">Severity <span>*</span></label><select class="form-control" id="incident-severity" name="severity" required><option value="">Select severity</option><option>Low</option><option>Medium</option><option>High</option></select></div>
        <div class="form-field full"><label for="incident-summary">Short description <span>*</span></label><input class="form-control" id="incident-summary" name="summary" required placeholder="e.g. Intermittent signal on port 3"></div>
        <div class="form-field full"><label for="incident-detail">What did you observe? <span>*</span></label><textarea class="form-control" id="incident-detail" name="detail" required placeholder="Describe the symptom, time and conditions. Avoid assumptions about the cause."></textarea></div>
        <div class="form-field"><label for="incident-reporter">Reported by <span>*</span></label><input class="form-control" id="incident-reporter" name="reporter" required value="${esc(profile().name)}"></div>
        <div class="form-field"><label for="incident-hold">Availability <span>*</span></label><select class="form-control" id="incident-hold" name="hold" required><option>Hold from issue</option><option>Available with note</option></select></div>
        <div class="form-field full"><div class="form-actions"><small>A prototype event remains in local browser storage. A real record must enter the existing event pipeline.</small><button class="button terra" type="submit">Record incident →</button></div></div></form></section>
      <aside class="panel panel-pad"><div class="panel-title"><div><div class="small-label">KEEP PEOPLE SAFE</div><h3>First response</h3></div></div><div class="side-note-list"><div class="side-note"><span class="side-note-index">01</span><div><strong>Pause circulation</strong><small>Hold equipment if it could be unsafe or unreliable.</small></div></div><div class="side-note"><span class="side-note-index">02</span><div><strong>Keep the detail factual</strong><small>Write down what was observed, not an unverified diagnosis.</small></div></div><div class="side-note"><span class="side-note-index">03</span><div><strong>Leave a next step</strong><small>Inspection, repair or follow-up with the borrower.</small></div></div></div></aside></div>`;
}

function bindPageControls() {
  document.querySelector("#equipment-search")?.addEventListener("input", (event) => {
    state.filter = event.target.value;
    state.pageNumber = 1;
    render();
    const input = document.querySelector("#equipment-search");
    input?.focus();
    input?.setSelectionRange(state.filter.length, state.filter.length);
  });
  document.querySelector("#status-filter")?.addEventListener("change", (event) => { state.statusFilter = event.target.value; state.pageNumber = 1; render(); });
  document.querySelector("#category-filter")?.addEventListener("change", (event) => { state.categoryFilter = event.target.value; state.pageNumber = 1; render(); });
  document.querySelector("#rental-search")?.addEventListener("input", updateRentalTable);
  document.querySelector("#rental-filter")?.addEventListener("change", updateRentalTable);
  document.querySelector("#incident-search")?.addEventListener("input", updateIncidentTable);
  document.querySelector("#incident-filter")?.addEventListener("change", (event) => { state.incidentFilter = event.target.value; updateIncidentTable(); });
  document.querySelector("#activity-search")?.addEventListener("input", updateActivityTable);
  document.querySelector("#activity-filter")?.addEventListener("change", updateActivityTable);
  document.querySelector("#rental-form")?.addEventListener("submit", submitRental);
  document.querySelector("#return-form")?.addEventListener("submit", submitReturn);
  document.querySelector("#live-return-form")?.addEventListener("submit", submitLiveReturn);
  document.querySelector("#incident-form")?.addEventListener("submit", submitIncident);
  document.querySelector("#reset-prototype")?.addEventListener("click", resetPrototype);
  document.querySelector("#simulation-start")?.addEventListener("click", startSimulation);
  document.querySelector("#simulation-stop")?.addEventListener("click", stopSimulation);
  document.querySelectorAll("[data-rate]").forEach((button) => button.addEventListener("click", () => {
    if (state.simulationRunning) return;
    state.simulationRate = Number(button.dataset.rate);
    render();
  }));
}

function updateRentalTable() {
  const query = (document.querySelector("#rental-search")?.value || "").trim().toLowerCase();
  const filter = document.querySelector("#rental-filter")?.value || (state.dataMode === "live" ? "All contracts" : "All rentals");
  const selected = state.rentals.filter((rental) => `${rental.reference} ${rental.borrower} ${rental.item} ${rental.itemId} ${rental.campus}`.toLowerCase().includes(query)
    && ((state.dataMode === "live" ? filter === "All contracts" : filter === "All rentals") || rental.status === filter));
  document.querySelector("#rental-table").innerHTML = rentalsTable(selected);
}

function updateIncidentTable() {
  const query = (document.querySelector("#incident-search")?.value || "").trim().toLowerCase();
  const selected = state.incidents.filter((incident) => (state.incidentFilter === "All" || incident.state === state.incidentFilter)
    && `${incident.reference} ${incident.item} ${incident.itemId} ${incident.title} ${incident.campus}`.toLowerCase().includes(query));
  document.querySelector("#incident-table").innerHTML = incidentTable(selected);
}

function updateActivityTable() {
  const query = (document.querySelector("#activity-search")?.value || "").trim().toLowerCase();
  const filter = document.querySelector("#activity-filter")?.value || "All activity";
  const recent = state.dataMode === "live" ? state.events : [...state.events].reverse();
  const source = state.dataMode === "live" ? recent : [...recent.map((event) => ({ ...event, local: true })), ...activitySeed];
  const entries = source.filter((entry) =>
    (filter === "All activity" || entry.type === filter)
    && `${entry.time} ${entry.type} ${entry.title} ${entry.detail}`.toLowerCase().includes(query));
  document.querySelector("#activity-table").innerHTML = activityTable(entries);
}

function setDateDefaults(formId, startId, dueId) {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  const start = local.toISOString().slice(0, 16);
  const later = new Date(local.getTime() + 24 * 60 * 60000).toISOString().slice(0, 16);
  const form = document.querySelector(`#${formId}`);
  if (form && startId) form.elements[startId].value = start;
  if (form && dueId) form.elements[dueId].value = later;
}

function submitRental(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const item = state.items.find((candidate) => candidate.id === values.get("assetId"));
  if (!item || item.status !== "Available") {
    toast("Choose an item currently marked available.", "Check availability");
    return;
  }
  const dueDate = new Date(values.get("due"));
  if (Number.isNaN(dueDate.valueOf()) || dueDate <= new Date(values.get("start"))) {
    form.elements.due.setCustomValidity("The return time must be after the issue time.");
    form.reportValidity();
    form.elements.due.setCustomValidity("");
    return;
  }
  const reference = `LO-LOCAL-${String(Date.now()).slice(-5)}`;
  const title = `${item.name} checked out`;
  state.rentals.unshift({ reference, borrower: values.get("borrower"), item: item.name, itemId: item.id, campus: item.campus, due: dueDate.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }), status: "On time" });
  item.status = "On loan";
  addLocalEvent({ type: "Rental", title, detail: `${item.id} · ${values.get("borrower")} · ${reference}`, status: "Queued locally" });
  saveState();
  showLifecycle(title, "Local prototype event. The existing validation, deduplication and loading pipeline is not connected to this screen.");
}

function submitReturn(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const item = state.items.find((candidate) => candidate.id.toLowerCase() === String(values.get("assetId")).trim().toLowerCase());
  if (!item) {
    form.elements.assetId.setCustomValidity("Choose an asset from this sample catalogue.");
    form.reportValidity();
    form.elements.assetId.setCustomValidity("");
    return;
  }
  item.condition = values.get("condition") === "Needs repair" ? "Needs check" : values.get("condition");
  item.status = values.get("condition") === "Needs repair" ? "Service" : "Available";
  const rental = state.rentals.find((candidate) => candidate.itemId === item.id && candidate.borrower.toLowerCase() === String(values.get("borrower")).trim().toLowerCase());
  if (rental) rental.status = "Returned";
  const title = `${item.name} return recorded`;
  addLocalEvent({ type: "Return", title, detail: `${item.id} · ${values.get("borrower")} · condition: ${values.get("condition")}`, status: "Queued locally" });
  if (values.get("condition") === "Needs repair") {
    state.incidents.unshift({ reference: `IN-LOCAL-${String(Date.now()).slice(-4)}`, item: item.name, itemId: item.id, title: values.get("note") || "Needs repair after return inspection", campus: item.campus, severity: "Medium", state: "Open", time: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) });
  }
  saveState();
  showLifecycle(title, "The return and condition check are saved in this browser only. They are not written to PostgreSQL or sent through Airflow.");
}

async function submitLiveReturn(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const button = form.querySelector('button[type="submit"]');
  const submission = {
    contract_id: Number(values.get("contractId")),
    condition: values.get("condition"),
    notes: values.get("notes"),
  };
  const fingerprint = JSON.stringify(submission);
  if (form.dataset.pendingFingerprint !== fingerprint) {
    form.dataset.pendingFingerprint = fingerprint;
    form.dataset.pendingEventId = crypto.randomUUID();
    form.dataset.pendingObservedAt = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  }
  button.disabled = true;
  try {
    const response = await fetch("/api/prototype/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...submission,
        event_id: form.dataset.pendingEventId,
        observed_at: form.dataset.pendingObservedAt,
      }),
    });
    const result = await response.json();
    if (!response.ok || result.ok !== true) {
      throw new Error(result.erreur || `Pipeline request failed (${response.status})`);
    }
    form.reset();
    delete form.dataset.pendingFingerprint;
    delete form.dataset.pendingEventId;
    delete form.dataset.pendingObservedAt;
    await loadLiveData();
    const ingestion = result.ingestion;
    toast(
      `${ingestion.inserted} event stored; ${ingestion.rejected} rejected. Batch ${ingestion.batch_no} · ${ingestion.status}.`,
      "Return sent through pipeline",
    );
    if (result.incident_projection.status !== "connected") {
      toast(result.incident_projection.error, "Redis projection needs attention");
    }
  } catch (error) {
    toast(error instanceof Error ? error.message : "The event could not be confirmed.", "Pipeline error");
  } finally {
    if (form.isConnected) button.disabled = false;
  }
}

function submitIncident(event) {
  event.preventDefault();
  const values = new FormData(event.currentTarget);
  const item = state.items.find((candidate) => candidate.id.toLowerCase() === String(values.get("assetId")).trim().toLowerCase());
  if (!item) {
    event.currentTarget.elements.assetId.setCustomValidity("Choose an asset from this sample catalogue.");
    event.currentTarget.reportValidity();
    event.currentTarget.elements.assetId.setCustomValidity("");
    return;
  }
  if (values.get("hold") === "Hold from issue") item.status = "Service";
  const reference = `IN-LOCAL-${String(Date.now()).slice(-4)}`;
  state.incidents.unshift({ reference, item: item.name, itemId: item.id, title: values.get("summary"), campus: item.campus, severity: values.get("severity"), state: "Open", time: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) });
  const title = `Incident reported · ${item.name}`;
  addLocalEvent({ type: "Incident", title, detail: `${item.id} · ${values.get("severity")} · ${values.get("reporter")}`, status: "Queued locally" });
  saveState();
  showLifecycle(title, "This incident and availability change exist only in the prototype. No operational database was changed.");
}

function addLocalEvent({ type, title, detail, status = "Queued locally" }) {
  state.events.push({ id: `LOCAL-${Date.now()}`, type, title, detail, status, time: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) });
}

function showLifecycle(title, copy) {
  dialogContent.innerHTML = `<div class="dialog-kicker">OPERATION PREVIEW / BROWSER LOCAL</div><h2 class="dialog-title">${esc(title)}</h2><p class="dialog-copy">${esc(copy)}</p><div class="dialog-steps">${["New operation/event", "Validation & normalisation", "Quality checks & deduplication", "Database loading", "Monitoring & visualisation"].map((step, index) => `<div class="dialog-step"><span>0${index + 1}</span><strong>${step}</strong><small>${index === 0 ? "RECORDED LOCALLY" : "DESIGNED · NOT RUN"}</small></div>`).join("")}</div><div class="notice terracotta"><strong>Future integration boundary</strong><br>A production form should submit to a protected application API that enqueues the operation into the existing CampusEquip pipeline. This prototype does not call that API.</div><div class="form-actions"><small>Changes are saved in local browser storage.</small><button class="button" type="button" id="dialog-done">Understood</button></div>`;
  dialog.showModal();
  document.querySelector("#dialog-done").addEventListener("click", () => dialog.close());
  render();
  toast("Saved locally; no service or database was contacted.", "Prototype action saved");
}

function startSimulation() {
  if (state.simulationRunning) return;
  state.simulationRunning = true;
  state.simulationStartedAt = Date.now();
  const step = () => {
    if (!state.simulationRunning) return;
    const generated = Math.max(1, Math.round(state.simulationRate / 4));
    state.simulationGenerated += generated;
    const processing = Math.round(generated * (state.simulationRate <= 1000 ? 0.96 : 0.62));
    state.simulationProcessed += processing;
    updateSimulationReadout();
  };
  step();
  state.simulationTimer = window.setInterval(step, 250);
  updateSimulationReadout();
}

function stopSimulation() {
  if (state.simulationTimer) window.clearInterval(state.simulationTimer);
  state.simulationTimer = null;
  state.simulationRunning = false;
  updateSimulationReadout();
}

function updateSimulationReadout() {
  const generated = document.querySelector("#sim-generated");
  if (!generated) return;
  generated.textContent = state.simulationGenerated.toLocaleString();
  document.querySelector("#sim-processed").textContent = `${state.simulationProcessed.toLocaleString()} events`;
  const backlog = Math.max(0, state.simulationGenerated - state.simulationProcessed);
  document.querySelector("#sim-backlog").textContent = backlog.toLocaleString();
  const runtime = state.simulationRunning ? Math.floor((Date.now() - state.simulationStartedAt) / 1000) : 0;
  document.querySelector("#sim-runtime").textContent = `${String(Math.floor(runtime / 60)).padStart(2, "0")}:${String(runtime % 60).padStart(2, "0")}`;
  const status = document.querySelector("#sim-status");
  status.classList.toggle("running", state.simulationRunning);
  status.querySelector("span").textContent = state.simulationRunning ? "SIMULATING" : "STANDBY";
  document.querySelector("#simulation-start").disabled = state.simulationRunning;
  document.querySelector("#simulation-stop").disabled = !state.simulationRunning;
  document.querySelectorAll("[data-rate]").forEach((button) => { button.disabled = state.simulationRunning; });
  const bars = document.querySelector("#sim-bars");
  if (bars) {
    const heights = [...bars.children].map((bar) => Number.parseFloat(bar.style.height) || 10);
    heights.shift();
    heights.push(15 + Math.random() * 80);
    bars.innerHTML = heights.map((height) => `<i style="height:${height}%"></i>`).join("");
  }
}

function resetPrototype() {
  const confirmed = window.confirm("Clear browser-local actions and restore the sample catalogue? This does not affect the project databases.");
  if (!confirmed) return;
  stopSimulation();
  state.items = structuredClone(equipmentSeed);
  state.rentals = structuredClone(rentalSeed);
  state.incidents = structuredClone(incidentSeed);
  state.events = [];
  saveState();
  render();
  toast("Sample records restored in this browser.", "Prototype reset");
}

function showItem(id) {
  const item = state.items.find((entry) => entry.id === id);
  if (!item) return;
  dialogContent.innerHTML = `<div class="dialog-kicker">ASSET RECORD / ILLUSTRATIVE</div><h2 class="dialog-title">${esc(item.name)}</h2><p class="dialog-copy">${esc(item.id)} · ${esc(item.tag)}<br>${esc(item.campus)} · ${esc(item.location)}</p><div class="rule"></div><div class="pipeline-overview" style="grid-template-columns:1fr 1fr"><div class="pipeline-stat"><div class="small-label">AVAILABILITY</div><strong style="font-size:19px">${esc(item.status)}</strong></div><div class="pipeline-stat" style="border:0"><div class="small-label">CONDITION</div><strong style="font-size:19px">${esc(item.condition)}</strong></div></div><p class="dialog-copy" style="margin-top:16px">This is an illustrative catalogue record. Live item details will later come from the CampusEquip API and existing pipeline.</p>`;
  dialog.showModal();
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#refresh-live-data")) { loadLiveData(); return; }
  if (event.target.closest("#toggle-data-mode")) {
    if (state.dataMode === "live") setDataMode("sample");
    else if (state.liveData) setDataMode("live");
    else loadLiveData();
    return;
  }
  const pageButton = event.target.closest("[data-page]");
  if (pageButton) { setPage(pageButton.dataset.page); return; }
  const action = event.target.closest("[data-action]");
  if (action) {
    const value = action.dataset.action;
    if (["new-rental", "new-incident"].includes(value) && state.dataMode === "live") {
      toast("Live rental and incident actions are unavailable. Use Returns for live event entry, or switch to sample data for local forms.", "Sample-only action");
      return;
    }
    if (value === "new-rental") { setPage("rentals"); window.setTimeout(() => { if (!document.querySelector("#rental-form")) content.insertAdjacentHTML("beforeend", formMarkup("rental")); bindPageControls(); setDateDefaults("rental-form", "start", "due"); content.querySelector("#rental-form")?.scrollIntoView({ behavior: "smooth", block: "start" }); content.querySelector("#borrower-name")?.focus(); }, 0); return; }
    if (value === "new-return") { setPage("returns"); window.setTimeout(() => { if (state.dataMode === "live") { const select = document.querySelector("#live-return-contract"); if (select && action.dataset.contractId) select.value = action.dataset.contractId; select?.focus(); return; } const input = document.querySelector("#return-asset"); if (input) { input.value = action.dataset.prefill || ""; if (input.value) document.querySelector("#return-borrower")?.focus(); } const time = document.querySelector("#return-time"); if (time) time.value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16); }, 0); return; }
    if (value === "new-incident") { setPage("incidents"); window.setTimeout(() => { if (!document.querySelector("#incident-form")) content.insertAdjacentHTML("beforeend", formMarkup("incident")); bindPageControls(); content.querySelector("#incident-form")?.scrollIntoView({ behavior: "smooth", block: "start" }); content.querySelector("#incident-asset")?.focus(); }, 0); return; }
    if (["equipment", "pipeline", "simulation", "activity", "rentals", "returns", "incidents"].includes(value)) { setPage(value); return; }
  }
  const sortButton = event.target.closest("[data-sort]");
  if (sortButton) {
    state.sortDirection = state.sortBy === sortButton.dataset.sort ? state.sortDirection * -1 : 1;
    state.sortBy = sortButton.dataset.sort;
    render();
    return;
  }
  const listPage = event.target.closest("[data-list-page]");
  if (listPage) {
    state.pageNumber = Number(listPage.dataset.listPage);
    render();
    return;
  }
  const roleOption = event.target.closest("[data-role]");
  if (roleOption) { state.role = roleOption.dataset.role; writeLocal("campusequip-role", state.role); setPage("overview"); return; }
  const itemButton = event.target.closest("[data-item]");
  if (itemButton) { showItem(itemButton.dataset.item); return; }
  const incidentButton = event.target.closest("[data-incident]");
  if (incidentButton) {
    const incident = state.incidents.find((entry) => entry.reference === incidentButton.dataset.incident);
    if (incident && incident.state !== "Resolved") {
      incident.state = incident.state === "Open" ? "In review" : incident.state === "In review" ? "Assigned" : "Resolved";
      saveState(); render(); toast(`${incident.reference} moved to ${incident.state}.`, "Sample incident updated");
    }
  }
});

roleSelect.addEventListener("change", (event) => {
  state.role = event.target.value;
  writeLocal("campusequip-role", state.role);
  setPage("overview");
});
document.querySelector("#dismiss-banner").addEventListener("click", () => {
  document.querySelector(".prototype-banner").hidden = true;
});
document.querySelector("#refresh-data").addEventListener("click", loadLiveData);
document.querySelector("#mobile-menu").addEventListener("click", () => {
  document.querySelector(".sidebar").classList.toggle("open");
});
document.querySelector("#profile-button").addEventListener("click", () => {
  toast("Use the role switcher above to preview another experience.", "Role preview");
});
render();
loadLiveData();
