export const roleProfiles = {
  admin: {
    name: "Amina Diallo",
    title: "Network administrator",
    initials: "AD",
    campus: "All campuses",
    greeting: "The network, in motion.",
    intro: "A considered view of equipment, demand and data quality across the university.",
  },
  manager: {
    name: "Youssef Benali",
    title: "Rabat campus manager",
    initials: "YB",
    campus: "Rabat · Engineering",
    greeting: "A campus, running well.",
    intro: "Local stock, active loans and the small details that keep a busy campus moving.",
  },
  staff: {
    name: "Sara El Idrissi",
    title: "Equipment desk",
    initials: "SE",
    campus: "Rabat · Engineering",
    greeting: "Good morning, Sara.",
    intro: "A clear desk for the next handover, return or equipment check.",
  },
};

export const navigation = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "equipment", label: "Equipment", icon: "equipment" },
  { id: "rentals", label: "Rentals", icon: "rentals" },
  { id: "returns", label: "Returns", icon: "returns" },
  { id: "incidents", label: "Incidents", icon: "incidents", count: "3" },
  { id: "activity", label: "Activity history", icon: "activity" },
  { id: "pipeline", label: "Pipeline monitor", icon: "pipeline", adminOnly: true },
  { id: "simulation", label: "Simulation lab", icon: "simulation", adminOnly: true },
  { id: "settings", label: "Preferences", icon: "settings" },
];

export const equipmentSeed = [
  { id: "CAM-0142", name: "Cinema camera", category: "Media", campus: "Rabat · Engineering", location: "Media lab / shelf C2", status: "Available", condition: "Excellent", tag: "Sony FX30", updated: "08:42" },
  { id: "AUD-0088", name: "Field recorder", category: "Audio", campus: "Rabat · Engineering", location: "Equipment desk", status: "On loan", condition: "Good", tag: "Zoom H6", updated: "09:16" },
  { id: "COM-0221", name: "Portable workstation", category: "Computing", campus: "Casablanca · Design", location: "Studio 04", status: "Available", condition: "Good", tag: "ThinkPad P1", updated: "08:31" },
  { id: "LAB-0037", name: "Digital microscope", category: "Laboratory", campus: "Rabat · Engineering", location: "Lab 2 / cabinet A", status: "On loan", condition: "Excellent", tag: "Dino-Lite AM73915", updated: "Yesterday" },
  { id: "NET-0114", name: "Network analyser", category: "Computing", campus: "Marrakech · Science", location: "Network lab", status: "Service", condition: "Needs check", tag: "Fluke LinkIQ", updated: "07:58" },
  { id: "CAM-0159", name: "Mirrorless camera", category: "Media", campus: "Casablanca · Design", location: "Media lab / shelf A1", status: "Available", condition: "Good", tag: "Fujifilm X-S20", updated: "08:55" },
  { id: "LAB-0062", name: "Thermal camera", category: "Laboratory", campus: "Rabat · Engineering", location: "Electronics lab", status: "Overdue", condition: "Good", tag: "FLIR E8-XT", updated: "2 days ago" },
  { id: "AUD-0103", name: "Wireless microphone kit", category: "Audio", campus: "Marrakech · Science", location: "Lecture hall store", status: "Available", condition: "Excellent", tag: "RØDE Wireless PRO", updated: "08:12" },
  { id: "COM-0305", name: "Graphics tablet", category: "Computing", campus: "Rabat · Engineering", location: "Design studio", status: "On loan", condition: "Good", tag: "Wacom Intuos Pro", updated: "10:02" },
  { id: "CAM-0174", name: "Tripod, carbon", category: "Media", campus: "Casablanca · Design", location: "Media lab / rack 3", status: "Available", condition: "Fair", tag: "Manfrotto 055", updated: "Yesterday" },
  { id: "LAB-0091", name: "Oscilloscope", category: "Laboratory", campus: "Marrakech · Science", location: "Electronics lab", status: "Available", condition: "Excellent", tag: "Rigol DS1054Z", updated: "09:04" },
  { id: "COM-0186", name: "Document camera", category: "Computing", campus: "Rabat · Engineering", location: "Teaching services", status: "Service", condition: "Needs check", tag: "IPEVO V4K", updated: "Yesterday" },
];

export const rentalSeed = [
  { reference: "LO-2026-1842", borrower: "Mehdi Alaoui", item: "Field recorder", itemId: "AUD-0088", campus: "Rabat · Engineering", due: "Today · 14:30", status: "Due today" },
  { reference: "LO-2026-1839", borrower: "Nour Bennis", item: "Digital microscope", itemId: "LAB-0037", campus: "Rabat · Engineering", due: "Today · 16:00", status: "On time" },
  { reference: "LO-2026-1817", borrower: "Omar Fassi", item: "Thermal camera", itemId: "LAB-0062", campus: "Rabat · Engineering", due: "05 Nov · 12:00", status: "Overdue" },
  { reference: "LO-2026-1848", borrower: "Lina Amrani", item: "Graphics tablet", itemId: "COM-0305", campus: "Rabat · Engineering", due: "Tomorrow · 09:00", status: "On time" },
  { reference: "LO-2026-1849", borrower: "Adam Chraïbi", item: "Wireless microphone kit", itemId: "AUD-0103", campus: "Marrakech · Science", due: "Tomorrow · 11:30", status: "On time" },
  { reference: "LO-2026-1851", borrower: "Salma Idrissi", item: "Cinema camera", itemId: "CAM-0142", campus: "Rabat · Engineering", due: "08 Nov · 17:00", status: "Reserved" },
];

export const incidentSeed = [
  { reference: "IN-0261", item: "Network analyser", itemId: "NET-0114", title: "Intermittent signal on port 3", campus: "Marrakech · Science", severity: "High", state: "In review", time: "09:24" },
  { reference: "IN-0259", item: "Thermal camera", itemId: "LAB-0062", title: "Return overdue by 2 days", campus: "Rabat · Engineering", severity: "Medium", state: "Open", time: "08:57" },
  { reference: "IN-0257", item: "Document camera", itemId: "COM-0186", title: "Focus ring needs inspection", campus: "Rabat · Engineering", severity: "Low", state: "Assigned", time: "Yesterday" },
  { reference: "IN-0251", item: "Tripod, carbon", itemId: "CAM-0174", title: "Quick-release plate missing", campus: "Casablanca · Design", severity: "Medium", state: "Resolved", time: "05 Nov" },
];

export const activitySeed = [
  { time: "10:02:18", type: "Rental", title: "Graphics tablet checked out", detail: "COM-0305 · Lina Amrani · Rabat", source: "Local sample record", status: "Recorded" },
  { time: "09:24:51", type: "Incident", title: "Network analyser flagged", detail: "NET-0114 · port 3 signal · Marrakech", source: "Local sample record", status: "In review" },
  { time: "09:16:07", type: "Rental", title: "Field recorder checked out", detail: "AUD-0088 · Mehdi Alaoui · Rabat", source: "Local sample record", status: "Recorded" },
  { time: "08:57:42", type: "Return", title: "Thermal camera return overdue", detail: "LAB-0062 · due 05 Nov · Rabat", source: "Local sample record", status: "Attention" },
  { time: "08:42:13", type: "Inventory", title: "Cinema camera condition checked", detail: "CAM-0142 · Media lab · Rabat", source: "Local sample record", status: "Recorded" },
];

export const campuses = [
  { name: "Rabat · Engineering", region: "North", units: 486, active: 72, incidents: 8, utilization: 71, delta: "+4.2%" },
  { name: "Casablanca · Design", region: "Atlantic", units: 358, active: 51, incidents: 5, utilization: 64, delta: "+1.8%" },
  { name: "Marrakech · Science", region: "South", units: 294, active: 39, incidents: 3, utilization: 58, delta: "−0.6%" },
];

export const pipelineSteps = [
  { number: "01", name: "Intake", detail: "Event arrives from the equipment desk", store: "Event envelope" },
  { number: "02", name: "Validation", detail: "Required fields, references and timestamps", store: "Quality rules" },
  { number: "03", name: "Normalisation", detail: "Consistent identifiers and event shape", store: "Canonical event" },
  { number: "04", name: "Quality checks", detail: "Contract, device and payload constraints", store: "Acceptance decision" },
  { number: "05", name: "Deduplication", detail: "Stable device + event identity", store: "Idempotency key" },
  { number: "06", name: "Processing", detail: "Derive current operational state", store: "State projection" },
  { number: "07", name: "Database loading", detail: "PostgreSQL · MongoDB · Redis · TimescaleDB", store: "Existing data pipeline" },
  { number: "08", name: "Monitoring", detail: "Attempts, latency and rejection reasons", store: "Airflow · TimescaleDB" },
];

export const series = [28, 36, 31, 47, 42, 54, 46, 63, 51, 72, 66, 81, 68, 87, 74, 92, 82, 98, 76, 89, 84, 100, 91, 108];

export function readLocal(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

export function writeLocal(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    return false;
  }
  return true;
}
