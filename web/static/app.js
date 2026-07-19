const state = {
  health: null,
  activeCaseId: null,
  searchResults: [],
  timeline: [],
  cases: [],
  citations: [],
  traces: [],
  answer: "",
  are: null,
  matter: null,
  courtProfiles: [],
  firmProfiles: [],
  staffDirectory: [],
  authority: null,
  templates: [],
  analysis: null,
  ingestActivity: [],
  surfaceView: "all",
  draftPanelOpen: true,
  chatMode: "legal",
  creatorUnlocked: false,
  lastDemoSeed: null,
};

const els = {};
const CHAT_MODE_STORAGE_KEY = "claire-chat-mode";
const CREATOR_UNLOCK_STORAGE_KEY = "claire-creator-unlocked";
const API_BASE = (() => {
  const path = window.location.pathname || "/";
  return path === "/veritas" || path.startsWith("/veritas/") ? "/veritas" : "";
})();

function apiPath(url) {
  if (typeof url === "string" && url.startsWith("/")) {
    return `${API_BASE}${url}`;
  }
  return url;
}

function bind() {
  [
    "backend-chip",
    "health-chip",
    "ocr-chip",
    "index-chip",
    "license-chip",
    "model-chip",
    "continuity-chip",
    "workspace-ready-chip",
    "analysis-ready-chip",
    "review-boundary-chip",
    "model-availability-note",
    "demo-evidence-count",
    "demo-timeline-count",
    "demo-contradiction-count",
    "demo-citation-count",
    "demo-packet-status",
    "technical-status-detail",
    "case-list",
    "evidence-list",
    "queue-list",
    "timeline-list",
    "citation-list",
    "trace-list",
    "answer-panel",
    "answer-status",
    "answer-sources",
    "conversation-shell",
    "chat-mode-chip",
    "chat-mode-note",
    "chat-mode-legal",
    "chat-mode-creator",
    "guide-primary-title",
    "guide-primary-status",
    "guide-primary-copy",
    "guide-checklist-status",
    "guide-checklist",
    "memory-metrics",
    "upload-input",
    "upload-name",
    "ingest-status",
    "ingest-summary",
    "processing-summary",
    "workflow-strip",
    "chat-input",
    "search-input",
    "ocr-input",
    "ocr-output",
    "case-filter",
    "gyro-prefix",
    "gyro-items",
    "matter-title",
    "matter-court",
    "matter-plaintiff",
    "matter-defendant",
    "matter-practice",
    "matter-notes",
  "court-profile-select",
  "draft-template-select",
    "court-rules-path",
    "corpus-path",
    "folder-ingest-card",
    "folder-ingest-note",
    "paste-evidence",
    "redact-export",
    "export-format",
    "docket-input",
    "docket-text",
    "billing-increment",
  "billing-rate",
    "matter-status",
    "matter-summary-left",
    "billing-summary",
    "analysis-list",
  "court-profile-list",
    "court-profile-report",
    "court-rules-status",
    "docket-status",
    "template-list",
    "theory-output",
    "anomaly-list",
    "filing-list",
    "draft-output",
    "active-matter-chip",
    "surface-label",
    "open-ops-window",
    "open-investigation-window",
    "open-output-window",
    "front-door-input",
    "front-door-go",
    "front-door-clear",
    "front-door-new-matter",
    "front-door-open-matter",
    "front-door-upload",
    "front-door-search",
    "front-door-timeline",
    "front-door-contradictions",
    "front-door-citation",
    "front-door-draft",
    "front-door-status",
    "front-door-response",
    "front-door-result",
    "demo-matter-result",
    "matter-selection-result",
    "matter-result",
    "health-result",
    "file-ingest-result",
    "folder-ingest-result",
    "paste-ingest-result",
    "search-result",
    "chat-result",
    "timeline-result",
    "contradictions-result",
    "trace-result",
    "packet-result",
    "export-result",
    "ocr-result",
    "firm-result",
    "staff-result",
    "authority-result",
    "court-rules-result",
    "docket-result",
    "firm-profile-select",
    "firm-name",
    "firm-office-name",
    "firm-office-address",
    "firm-phone",
    "firm-email",
    "firm-website",
    "firm-confidentiality-notice",
    "firm-default-footer",
    "firm-profile-status",
    "save-firm-profile",
    "staff-full-name",
    "staff-role",
    "staff-title",
    "staff-bar-number",
    "staff-office",
    "staff-email",
    "staff-phone",
    "staff-initials",
    "staff-signature-block",
    "staff-directory-list",
    "staff-directory-status",
    "save-staff-member",
    "authority-firm-profile",
    "authority-prepared-by",
    "authority-reviewed-by",
    "authority-approved-by",
    "authority-signed-by",
    "authority-filed-by",
    "authority-summary",
    "authority-status",
    "save-authority-stamp",
    "draft-panel",
    "toggle-draft-panel",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

async function json(url, opts = {}) {
  const res = await fetch(apiPath(url), { headers: { "Content-Type": "application/json", ...(opts.headers || {}) }, ...opts });
  if (!res.ok) {
    let detail = "";
    try {
      const payload = await res.json();
      detail = typeof payload.detail === "string"
        ? payload.detail
        : payload.detail?.message || payload.message || "";
    } catch {
      detail = await res.text();
    }
    throw new Error(publicErrorMessage(res.status, detail));
  }
  return await res.json();
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 700px)").matches;
}

function resultBody(panel) {
  return panel?.querySelector(".action-result-body") || panel;
}

function setActionPanel(panelId, status, html) {
  const panel = els[panelId] || document.getElementById(panelId);
  if (!panel) return;
  panel.classList.remove("loading", "success", "error");
  if (status) panel.classList.add(status);
  const body = resultBody(panel);
  if (body) body.innerHTML = html || "No result yet.";
}

function clearActionPanel(panelId) {
  setActionPanel(panelId, "", "No result yet.");
}

function scrollActionPanel(panelId) {
  const panel = els[panelId] || document.getElementById(panelId);
  if (panel && isMobileViewport()) {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function resultRows(rows) {
  return `<div class="action-result-grid">${rows.map(([label, value]) => `
    <div class="action-result-row">
      <span>${escapeHtml(label)}</span>
      <span>${value}</span>
    </div>
  `).join("")}</div>`;
}

function resultItems(items, renderer, empty = "No results returned.") {
  const rows = items || [];
  if (!rows.length) return `<div class="note">${escapeHtml(empty)}</div>`;
  return `<div class="action-result-list">${rows.map((item) => `<div class="action-result-item">${renderer(item)}</div>`).join("")}</div>`;
}

function errorPanelMessage(error) {
  return `<div class="note">${escapeHtml(error?.message || error || "The action failed. Try again.")}</div>`;
}

async function withAction(buttonOrId, panelId, loadingMessage, action) {
  const button = typeof buttonOrId === "string" ? document.getElementById(buttonOrId) : buttonOrId;
  if (button?.disabled) return null;
  const priorText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  }
  setActionPanel(panelId, "loading", `<div class="note">${escapeHtml(loadingMessage)}</div>`);
  scrollActionPanel(panelId);
  try {
    const result = await action();
    if (button && priorText) button.textContent = priorText;
    return result;
  } catch (error) {
    setActionPanel(panelId, "error", errorPanelMessage(error));
    scrollActionPanel(panelId);
    return null;
  } finally {
    if (button) {
      button.disabled = false;
      button.setAttribute("aria-busy", "false");
    }
  }
}

function publicErrorMessage(status, detail = "") {
  const text = String(detail || "").replace(/\s+/g, " ").trim();
  if (status === 400) return text || "The request is incomplete. Check the field and try again.";
  if (status === 404) return "The requested Veritas record was not found.";
  if (status === 409) return text || "The current matter needs review before this action can proceed.";
  if (status === 413) return "The upload is too large for this route.";
  if (status === 415) return "That file type is not supported in this route.";
  if (status >= 500) return "The Veritas service could not complete that action. Try again or check Technical Details.";
  return text || `Request failed (${status}).`;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function fmtTime(value) {
  if (value === undefined || value === null) return "n/a";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  return new Date(num * 1000).toLocaleString();
}

function short(text, max = 180) {
  const t = String(text ?? "").replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max)}...` : t;
}

function slugify(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || `matter-${Date.now()}`;
}

function displayModelName(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.split(/[\\/]/).filter(Boolean).pop() || text;
}

function setChip(el, text, mode = "") {
  if (!el) return;
  el.className = `status-chip ${mode}`.trim();
  el.textContent = text;
}

function surfaceLabel(view = state.surfaceView) {
  if (view === "ops") return "Operations Surface";
  if (view === "investigation") return "Investigation Surface";
  if (view === "output") return "Output Surface";
  return "Integrated Surface";
}

function renderSurface() {
  document.body.dataset.surfaceView = state.surfaceView;
  document.querySelectorAll("[data-surfaces]").forEach((node) => {
    const allowed = String(node.getAttribute("data-surfaces") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    node.hidden = state.surfaceView !== "all" && !allowed.includes(state.surfaceView);
  });
  if (els["surface-label"]) {
    els["surface-label"].textContent = surfaceLabel();
  }
}

function surfaceUrl(view) {
  const url = new URL(window.location.href);
  if (view === "all") {
    url.searchParams.delete("view");
  } else {
    url.searchParams.set("view", view);
  }
  return url.toString();
}

function matterStats() {
  const traces = state.traces || [];
  const citations = state.citations || [];
  const searchResults = state.searchResults || [];
  const timeline = state.timeline || [];
  const analysis = state.analysis || {};
  const anomalies = analysis.anomalies || [];
  const packet = analysis.packet || {};
  const records = analysis.records || [];
  const evidenceCount = Math.max(searchResults.length, records.length, Number(state.lastDemoSeed?.evidence_items || 0));
  const timelineCount = timeline.length;
  const contradictionCount = anomalies.filter((item) => {
    const label = `${item.label || ""} ${item.summary || ""}`.toLowerCase();
    return label.includes("contradiction") || label.includes("inconsisten") || label.includes("conflict") || label.includes("deadline");
  }).length || Number(state.lastDemoSeed?.analysis?.anomalies?.length || 0);
  const citationCount = citations.length || searchResults.filter((item) => item.citation || item.source_url || item.source_name).length;
  const hasPacket = Boolean(packet.template || packet.sections?.length || traces.some((item) => item.event_type === "draft"));
  return { evidenceCount, timelineCount, contradictionCount, citationCount, hasPacket };
}

function workflowState() {
  const stats = matterStats();
  const traces = state.traces || [];
  const hasIngest = stats.evidenceCount > 0 || traces.some((item) => item.event_type === "ingest" || item.event_type === "demo_matter_loaded");
  const hasQuery = state.answer || state.searchResults.length > 0 || traces.some((item) => item.event_type === "chat" || item.event_type === "analysis");
  const hasTrace = traces.length > 0;
  return [
    { label: "Ingest", status: hasIngest ? "Complete" : "Not started", count: stats.evidenceCount },
    { label: "Index", status: hasIngest ? "Complete" : "Not started", count: stats.evidenceCount },
    { label: "Query", status: hasQuery ? "Complete" : (hasIngest ? "Ready" : "Not started"), count: state.searchResults.length },
    { label: "Trace", status: hasTrace ? "Complete" : "Not started", count: traces.length },
    { label: "Timeline", status: stats.timelineCount ? "Complete" : (hasIngest ? "Ready" : "Not started"), count: stats.timelineCount },
  ];
}

function updateInvestorSummary() {
  const stats = matterStats();
  if (els["demo-evidence-count"]) els["demo-evidence-count"].textContent = String(stats.evidenceCount);
  if (els["demo-timeline-count"]) els["demo-timeline-count"].textContent = String(stats.timelineCount);
  if (els["demo-contradiction-count"]) els["demo-contradiction-count"].textContent = String(stats.contradictionCount);
  if (els["demo-citation-count"]) els["demo-citation-count"].textContent = String(stats.citationCount);
  if (els["demo-packet-status"]) {
    els["demo-packet-status"].textContent = stats.hasPacket
      ? "Preview ready"
      : stats.evidenceCount > 0
        ? "Ready to draft"
        : "Not ready";
  }
  if (els["workflow-strip"]) {
    els["workflow-strip"].innerHTML = workflowState().map((stage) => {
      const ready = stage.status === "Ready";
      const complete = stage.status === "Complete";
      const error = stage.status === "Error";
      return `
        <div class="workflow-stage ${complete ? "active ready" : ""} ${ready ? "active" : ""} ${error ? "error" : ""}">
          <strong>${escapeHtml(stage.label)}</strong>
          <span>${escapeHtml(stage.status)} • ${escapeHtml(stage.count)}</span>
        </div>
      `;
    }).join("");
  }
  if (els["ingest-status"]) {
    const current = state.activeCaseId || "unassigned";
    els["ingest-status"].textContent = stats.evidenceCount
      ? `Active matter ${current}: ${stats.evidenceCount} evidence record(s) available.`
      : "Awaiting evidence ingest or sample matter load.";
  }
  if (els["upload-name"]) {
    els["upload-name"].textContent = stats.timelineCount
      ? `${stats.timelineCount} chronology event(s) and ${state.traces.length} provenance trace(s) in view.`
      : "No chronology activity yet.";
  }
}

function updateLocalOnlyControls() {
  const localFolder = Boolean(state.health?.capabilities?.local_folder_import);
  if (els["folder-ingest-card"]) {
    els["folder-ingest-card"].classList.toggle("feature-disabled", !localFolder);
    els["folder-ingest-card"].setAttribute("aria-disabled", localFolder ? "false" : "true");
  }
  if (els["folder-ingest-note"]) {
    els["folder-ingest-note"].textContent = localFolder
      ? "Local desktop mode: recursively ingest an authorized evidence folder. ZIPs inside the folder will be expanded and indexed."
      : "Coming in Pilot for authorized local desktop deployments. Browser visitors can use file upload, ZIP upload, or pasted evidence.";
  }
  if (els["corpus-path"]) els["corpus-path"].disabled = !localFolder;
  const runCorpus = document.getElementById("run-corpus");
  if (runCorpus) {
    runCorpus.disabled = !localFolder;
    runCorpus.textContent = localFolder ? "Ingest Folder" : "Local Only";
    runCorpus.title = localFolder ? "Ingest an authorized local folder" : "Folder import is disabled on the hosted public demo.";
  }
  if (!localFolder) {
    setActionPanel("folder-ingest-result", "error", resultRows([
      ["Status", "Coming in Pilot for hosted public demo."],
      ["Reason", "Folder import requires authorized local desktop mode."],
      ["Use instead", "File upload, ZIP upload, or pasted evidence."],
    ]));
  }
}

function renderDraftPanel() {
  const panel = els["draft-panel"];
  const button = els["toggle-draft-panel"];
  if (!panel || !button) return;
  panel.classList.toggle("collapsed", !state.draftPanelOpen);
  button.textContent = state.draftPanelOpen ? "Hide Printer" : "Show Printer";
}

function normalizeChatMode(mode) {
  return String(mode || "").toLowerCase() === "creator" ? "creator" : "legal";
}

function renderChatMode() {
  const mode = normalizeChatMode(state.chatMode);
  const creatorActive = mode === "creator";
  const creatorReady = Boolean(state.creatorUnlocked);
  if (els["chat-mode-chip"]) {
    els["chat-mode-chip"].textContent = creatorActive ? "Creator Mode" : "Legal Mode";
  }
  if (els["chat-mode-note"]) {
    els["chat-mode-note"].textContent = creatorActive
      ? "Creator continuity is active. House context is available, but it is not legal evidence."
      : "The model only receives grounded snippets from the active matter bundle and memory cache.";
  }
  if (els["chat-mode-legal"]) {
    els["chat-mode-legal"].classList.toggle("active", !creatorActive);
  }
  if (els["chat-mode-creator"]) {
    els["chat-mode-creator"].classList.toggle("active", creatorActive);
    els["chat-mode-creator"].textContent = creatorReady ? "Creator Mode" : "Creator Mode Locked";
  }
  if (els["chat-input"]) {
    els["chat-input"].placeholder = creatorActive
      ? "Creator continuity is active. Ask Claire about Lucius Prime, house context, or the active matter. Use Ctrl/Cmd + Enter to send."
      : "Ask about the record, compare exhibits, summarize chronology, or request a citation-backed analysis. Use Ctrl/Cmd + Enter to send.";
  }
}

function currentFirmProfileId() {
  return String(els["firm-profile-select"]?.value || els["authority-firm-profile"]?.value || state.matter?.firm_profile_id || "").trim();
}

function renderSelectOptions(selectId, items, selectedId, blankLabel = "Unassigned") {
  const select = els[selectId];
  if (!select) return;
  const options = [`<option value="">${escapeHtml(blankLabel)}</option>`].concat(
    (items || []).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.full_name || item.name || item.id)}</option>`)
  );
  select.innerHTML = options.join("");
  if (selectedId !== undefined && selectedId !== null) {
    select.value = selectedId || "";
  }
}

function renderFirmProfiles(items) {
  state.firmProfiles = items || [];
  const currentId = currentFirmProfileId() || state.firmProfiles[0]?.id || "";
  renderSelectOptions("firm-profile-select", state.firmProfiles, currentId, "Select firm profile");
  renderSelectOptions("authority-firm-profile", state.firmProfiles, currentId, "Select firm profile");
  const selectedRaw = state.firmProfiles.find((item) => item.id === currentId) || state.firmProfiles[0] || {};
  const selected = normalizeDemoFirmProfile(selectedRaw);
  if (els["firm-name"]) els["firm-name"].value = selected.name || "";
  if (els["firm-office-name"]) els["firm-office-name"].value = selected.office_name || "";
  if (els["firm-office-address"]) els["firm-office-address"].value = selected.office_address || "";
  if (els["firm-phone"]) els["firm-phone"].value = selected.phone || "";
  if (els["firm-email"]) els["firm-email"].value = selected.email || "";
  if (els["firm-website"]) els["firm-website"].value = selected.website || "";
  if (els["firm-confidentiality-notice"]) els["firm-confidentiality-notice"].value = selected.confidentiality_notice || "";
  if (els["firm-default-footer"]) els["firm-default-footer"].value = selected.default_footer || "";
  if (els["firm-profile-status"]) {
    els["firm-profile-status"].textContent = selected.name ? "Loaded" : "Ready";
  }
}

function normalizeDemoFirmProfile(profile) {
  const next = { ...(profile || {}) };
  const joined = [next.name, next.office_name, next.office_address, next.default_footer].filter(Boolean).join(" | ");
  const looksPlaceholder = /Acme Litigation Group|Downtown Office|100 Main St/i.test(joined);
  if (!looksPlaceholder) return next;
  if (/Acme Litigation Group/i.test(String(next.name || ""))) next.name = "Demo Litigation Firm";
  if (/Downtown Office/i.test(String(next.office_name || ""))) next.office_name = "California Trial Office";
  if (/100 Main St/i.test(String(next.office_address || ""))) next.office_address = "Demo Profile - Not a Real Firm";
  if (/Acme Litigation Group/i.test(String(next.default_footer || ""))) next.default_footer = "Demo Litigation Firm - Attorney Review Required";
  return next;
}

function renderStaffDirectory(items) {
  state.staffDirectory = items || [];
  const selectedId = state.authority?.assignments?.prepared_by?.id || state.matter?.prepared_by_id || "";
  const staff = state.staffDirectory;
  const selects = [
    "authority-prepared-by",
    "authority-reviewed-by",
    "authority-approved-by",
    "authority-signed-by",
    "authority-filed-by",
  ];
  selects.forEach((id) => renderSelectOptions(id, staff, state.authority?.assignments?.[id.replace("authority-", "").replace(/-/g, "_")]?.id || "", "Unassigned"));
  if (els["staff-directory-list"]) {
    els["staff-directory-list"].innerHTML = staff.length ? staff.map((item) => `
      <div class="hint-card">
        <div class="stack-row">
          <strong>${escapeHtml(item.full_name || item.id || "Staff Member")}</strong>
          <span class="timeline-pill">${escapeHtml(item.role || "legal_assistant")}</span>
        </div>
        <div class="note">${escapeHtml([item.title, item.office, item.email].filter(Boolean).join(" • "))}</div>
        <div class="note">${escapeHtml(item.signature_block || item.document_stamp || "")}</div>
      </div>
    `).join("") : `<div class="note">No staff members saved yet.</div>`;
  }
  if (els["staff-directory-status"]) {
    els["staff-directory-status"].textContent = `${staff.length} saved`;
  }
  if (els["staff-full-name"] && !els["staff-full-name"].value) {
    els["staff-full-name"].value = "";
  }
  if (els["authority-status"]) {
    els["authority-status"].textContent = state.authority?.valid === false ? "Review" : "Ready";
  }
  if (els["authority-summary"] && state.authority) {
    const lines = state.authority.summary ? [state.authority.summary] : [];
    if (state.authority.violations?.length) {
      lines.push(`Violations: ${state.authority.violations.join(" | ")}`);
    }
    els["authority-summary"].textContent = lines.join(" • ") || "Select staff members to stamp the active matter and packet.";
  }
}

function renderAuthority(data) {
  state.authority = data || null;
  const authority = state.authority || {};
  if (els["authority-firm-profile"]) {
    els["authority-firm-profile"].value = authority.firm_profile?.id || currentFirmProfileId() || "";
  }
  const assignments = authority.assignments || {};
  const assignmentMap = {
    "authority-prepared-by": assignments.prepared_by?.id || "",
    "authority-reviewed-by": assignments.reviewed_by?.id || "",
    "authority-approved-by": assignments.approved_by?.id || "",
    "authority-signed-by": assignments.signed_by?.id || "",
    "authority-filed-by": assignments.filed_by?.id || "",
  };
  Object.entries(assignmentMap).forEach(([selectId, value]) => {
    if (els[selectId]) els[selectId].value = value || "";
  });
  if (els["authority-summary"]) {
    const lines = authority.stamp_lines || [];
    els["authority-summary"].textContent = lines.length ? lines.join(" • ") : "Select staff members to stamp the active matter and packet.";
  }
}

function collectFirmProfilePayload() {
  const current = state.firmProfiles.find((item) => item.id === currentFirmProfileId()) || {};
  return {
    id: current.id || undefined,
    name: els["firm-name"]?.value?.trim() || current.name || "",
    office_name: els["firm-office-name"]?.value?.trim() || "",
    office_address: els["firm-office-address"]?.value?.trim() || "",
    phone: els["firm-phone"]?.value?.trim() || "",
    email: els["firm-email"]?.value?.trim() || "",
    website: els["firm-website"]?.value?.trim() || "",
    confidentiality_notice: els["firm-confidentiality-notice"]?.value?.trim() || "",
    default_footer: els["firm-default-footer"]?.value?.trim() || "",
  };
}

function collectStaffPayload() {
  return {
    full_name: els["staff-full-name"]?.value?.trim() || "",
    role: els["staff-role"]?.value || "legal_assistant",
    title: els["staff-title"]?.value?.trim() || "",
    bar_number: els["staff-bar-number"]?.value?.trim() || "",
    office: els["staff-office"]?.value?.trim() || "",
    email: els["staff-email"]?.value?.trim() || "",
    phone: els["staff-phone"]?.value?.trim() || "",
    initials: els["staff-initials"]?.value?.trim() || "",
    signature_block: els["staff-signature-block"]?.value?.trim() || "",
  };
}

function collectAuthorityPayload() {
  return {
    case_id: state.activeCaseId || null,
    firm_profile_id: els["authority-firm-profile"]?.value || currentFirmProfileId() || null,
    prepared_by_id: els["authority-prepared-by"]?.value || null,
    reviewed_by_id: els["authority-reviewed-by"]?.value || null,
    approved_by_id: els["authority-approved-by"]?.value || null,
    signed_by_id: els["authority-signed-by"]?.value || null,
    filed_by_id: els["authority-filed-by"]?.value || null,
  };
}

async function saveFirmProfile() {
  const data = await json("/firm-profile", {
    method: "POST",
    body: JSON.stringify(collectFirmProfilePayload()),
  });
  renderFirmProfiles(data.items || []);
  await refreshWorkspace();
  if (els["firm-profile-status"]) els["firm-profile-status"].textContent = "Saved";
  setActionPanel("firm-result", "success", resultRows([
    ["Status", "Firm profile saved."],
    ["Profiles", escapeHtml((data.items || []).length)],
    ["Active profile", escapeHtml(currentFirmProfileId() || "n/a")],
  ]));
  scrollActionPanel("firm-result");
}

async function saveStaffMember() {
  const data = await json("/staff-directory", {
    method: "POST",
    body: JSON.stringify(collectStaffPayload()),
  });
  if (els["staff-full-name"]) els["staff-full-name"].value = "";
  if (els["staff-title"]) els["staff-title"].value = "";
  if (els["staff-bar-number"]) els["staff-bar-number"].value = "";
  if (els["staff-office"]) els["staff-office"].value = "";
  if (els["staff-email"]) els["staff-email"].value = "";
  if (els["staff-phone"]) els["staff-phone"].value = "";
  if (els["staff-initials"]) els["staff-initials"].value = "";
  if (els["staff-signature-block"]) els["staff-signature-block"].value = "";
  renderStaffDirectory(data.items || []);
  await refreshWorkspace();
  setActionPanel("staff-result", "success", resultRows([
    ["Status", "Staff member saved."],
    ["Directory count", escapeHtml((data.items || []).length)],
  ]));
  scrollActionPanel("staff-result");
}

async function saveAuthorityStamp() {
  const data = await json("/authority", {
    method: "POST",
    body: JSON.stringify(collectAuthorityPayload()),
  });
  renderAuthority(data.authority || data);
  if (data.bundle) {
    renderMatter(data.bundle);
  }
  await refreshWorkspace();
  setActionPanel("authority-result", "success", resultRows([
    ["Status", "Responsibility stamp saved."],
    ["Matter", escapeHtml(state.activeCaseId || "unassigned")],
    ["Review status", escapeHtml((data.authority || data)?.valid === false ? "Review required" : "Ready")],
  ]));
  scrollActionPanel("authority-result");
}

function setFrontDoorStatus(status, message) {
  if (els["front-door-status"]) {
    els["front-door-status"].textContent = status;
  }
  if (els["front-door-response"]) {
    els["front-door-response"].textContent = message;
  }
  setActionPanel("front-door-result", status === "Clarify" ? "error" : status === "Ready" ? "" : "success", resultRows([
    ["Status", escapeHtml(status || "Ready")],
    ["Result", escapeHtml(message || "No result yet.")],
  ]));
}

function normalizeFrontDoorText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function stripCommandPrefix(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      return normalizeFrontDoorText(match[1] || "");
    }
  }
  return "";
}

function findMatchingCase(text) {
  const query = String(text || "").toLowerCase();
  if (!query) return null;
  return state.cases.find((item) => {
    const caseId = String(item.case_id || "").toLowerCase();
    const title = String(item.title || "").toLowerCase();
    return (caseId && query.includes(caseId)) || (title && query.includes(title));
  }) || null;
}

function focusElement(id) {
  const el = els[id] || document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  if (typeof el.focus === "function") {
    el.focus({ preventScroll: true });
  }
}

function selectCaseId(caseId) {
  if (!caseId) return false;
  state.activeCaseId = caseId;
  state.analysis = null;
  if (els["case-filter"]) {
    els["case-filter"].textContent = caseId;
  }
  refreshWorkspace();
  return true;
}

async function createMatterFromFrontDoor(text) {
  const title = stripCommandPrefix(text, [
    /^(?:create|start|open)\s+(?:a\s+)?new\s+matter(?:\s+(?:called|named|titled))?[:\-\s]+(.+)$/i,
    /^(?:new\s+matter)(?:\s+(?:called|named|titled))?[:\-\s]+(.+)$/i,
  ]);
  if (!title) {
    setFrontDoorStatus("Clarify", "What should I name the new matter?");
    document.getElementById("new-case")?.click();
    return;
  }
  state.activeCaseId = slugify(title);
  if (els["matter-title"]) els["matter-title"].value = title;
  if (els["matter-status"]) els["matter-status"].textContent = "Matter draft created";
  if (els["case-filter"]) els["case-filter"].textContent = state.activeCaseId;
  await saveMatter();
  focusElement("matter-title");
  setFrontDoorStatus("Routed", `Created matter shell: ${title}.`);
}

async function openMatterFromFrontDoor(text) {
  const existing = findMatchingCase(text);
  if (existing) {
    selectCaseId(existing.case_id);
    setFrontDoorStatus("Routed", `Opened matter: ${existing.title || existing.case_id}.`);
    return;
  }
  const name = stripCommandPrefix(text, [
    /^(?:open|select|switch to)\s+(?:an?\s+)?(?:existing\s+)?matter(?:\s+(?:called|named|titled))?[:\-\s]+(.+)$/i,
    /^(?:open|select|switch to)\s+(?:an?\s+)?case(?:\s+(?:called|named|titled))?[:\-\s]+(.+)$/i,
  ]);
  if (name) {
    const match = state.cases.find((item) => String(item.title || "").toLowerCase() === name.toLowerCase() || String(item.case_id || "").toLowerCase() === slugify(name));
    if (match) {
      selectCaseId(match.case_id);
      setFrontDoorStatus("Routed", `Opened matter: ${match.title || match.case_id}.`);
      return;
    }
  }
  setFrontDoorStatus("Clarify", "Which matter should I open?");
  focusElement("case-list");
}

async function addEvidenceFromFrontDoor() {
  focusElement("upload-input");
  setFrontDoorStatus("Routed", "Upload a file or ZIP into the active matter.");
}

async function searchMatterFromFrontDoor(text) {
  const query = stripCommandPrefix(text, [
    /^(?:search|find)\s+(?:this\s+)?(?:matter|record|evidence)?[:\-\s]+(.+)$/i,
    /^(?:search|find)\s+for[:\-\s]+(.+)$/i,
  ]) || stripCommandPrefix(text, [/^(?:search|find)\s+(.+)$/i]);
  if (!query) {
    setFrontDoorStatus("Clarify", "What should I search in this matter?");
    focusElement("search-input");
    return;
  }
  if (els["search-input"]) els["search-input"].value = query;
  await runSearch();
  setFrontDoorStatus("Routed", `Searching the matter for: ${query}.`);
}

async function timelineFromFrontDoor() {
  await runAnalysis();
  focusElement("timeline-list");
  setFrontDoorStatus("Routed", "Built the current matter timeline.");
}

async function contradictionsFromFrontDoor() {
  await runAnalysis();
  focusElement("anomaly-list");
  setFrontDoorStatus("Routed", "Reviewed contradictions and anomalies.");
}

async function researchCitationFromFrontDoor(text) {
  const query = stripCommandPrefix(text, [
    /^(?:research|lookup|look up)\s+(?:a\s+)?citation[:\-\s]+(.+)$/i,
    /^(?:citation|authority|case)\s+[:\-\s]+(.+)$/i,
  ]) || stripCommandPrefix(text, [/^(?:research|lookup|look up)\s+(.+)$/i]);
  if (!query) {
    setFrontDoorStatus("Clarify", "Which citation should I research?");
    focusElement("chat-input");
    return;
  }
  if (els["chat-input"]) els["chat-input"].value = query;
  setChatMode("legal");
  await runChat();
  setFrontDoorStatus("Routed", `Researching citation: ${query}.`);
}

async function draftReportFromFrontDoor() {
  await runDraft();
  focusElement("draft-panel");
  setFrontDoorStatus("Routed", "Drafted a report from admitted evidence.");
}

async function routeFrontDoorRequest(rawText) {
  const text = normalizeFrontDoorText(rawText);
  if (!text) {
    setFrontDoorStatus("Ready", "Type a legal task or choose a quick action.");
    return;
  }
  const lower = text.toLowerCase();
  if (/(?:^|\b)(?:new matter|create a new matter|create matter|start new matter)\b/.test(lower)) {
    await createMatterFromFrontDoor(text);
    return;
  }
  if (/(?:^|\b)(?:open existing matter|open matter|select matter|switch to matter|open case)\b/.test(lower)) {
    await openMatterFromFrontDoor(text);
    return;
  }
  if (/(?:^|\b)(?:add evidence|upload evidence|ingest evidence|attach evidence)\b/.test(lower)) {
    await addEvidenceFromFrontDoor();
    return;
  }
  if (/(?:^|\b)(?:search this matter|search matter|search evidence|find evidence|search record)\b/.test(lower)) {
    await searchMatterFromFrontDoor(text);
    return;
  }
  if (/(?:^|\b)(?:build a timeline|build timeline|timeline)\b/.test(lower)) {
    await timelineFromFrontDoor();
    return;
  }
  if (/(?:^|\b)(?:find contradictions|contradictions|anomalies)\b/.test(lower)) {
    await contradictionsFromFrontDoor();
    return;
  }
  if (/(?:^|\b)(?:research a citation|research citation|citation lookup|look up citation)\b/.test(lower)) {
    await researchCitationFromFrontDoor(text);
    return;
  }
  if (/(?:^|\b)(?:draft a report|draft report|report from admitted evidence|draft packet)\b/.test(lower)) {
    await draftReportFromFrontDoor();
    return;
  }
  if (els["chat-input"]) els["chat-input"].value = text;
  setFrontDoorStatus("Routed", "Sending the request to grounded analysis.");
  await runChat();
}

function renderGuideMe() {
  const memory = state.health?.memory || {};
  const matterReady = Boolean(state.activeCaseId && state.activeCaseId !== "unassigned");
  const hasDocuments = Number(memory.documents || 0) > 0;
  const hasEvidence = Number(memory.evidence || 0) > 0;
  const hasTimeline = (state.timeline || []).length > 0;
  const hasCitations = (state.citations || []).length > 0;
  const hasPacket = Boolean(state.analysis?.packet);
  const steps = [
    { label: "Matter selected", done: matterReady },
    { label: "Evidence uploaded or pasted", done: hasDocuments || hasEvidence },
    { label: "Timeline populated", done: hasTimeline },
    { label: "Grounded sources reviewed", done: hasCitations },
    { label: "Attorney-review packet drafted", done: hasPacket },
  ];
  const complete = steps.filter((step) => step.done).length;
  let title = "Start Evidence Intake";
  let status = "Ready";
  let copy = "Create or select a matter, then upload documents, photos, notes, or docket exports.";
  if (matterReady && !(hasDocuments || hasEvidence)) {
    title = "Add Matter Evidence";
    status = "Ingest";
    copy = "Upload files, ingest a folder, paste OCR text, or import a docket for the active matter.";
  } else if (hasDocuments || hasEvidence) {
    title = "Review the Source Trail";
    status = "Review";
    copy = "Search the record, inspect citations, and ask Claire for grounded summaries tied to the active matter.";
  }
  if (hasTimeline && hasCitations) {
    title = "Prepare Attorney Packet";
    status = "Packet";
    copy = "Run analysis, check anomalies and missing fields, then generate an attorney-review packet.";
  }
  if (hasPacket) {
    title = "Packet Ready for Review";
    status = "Attorney Review";
    copy = "Review the packet, source links, and redactions before any attorney-facing use.";
  }
  if (els["guide-primary-title"]) els["guide-primary-title"].textContent = title;
  if (els["guide-primary-status"]) els["guide-primary-status"].textContent = status;
  if (els["guide-primary-copy"]) els["guide-primary-copy"].textContent = copy;
  if (els["guide-checklist-status"]) els["guide-checklist-status"].textContent = `${complete} / ${steps.length}`;
  if (els["guide-checklist"]) {
    els["guide-checklist"].innerHTML = steps.map((step) => `${step.done ? "✓" : "□"} ${escapeHtml(step.label)}`).join("<br>");
  }
}

function setChatMode(mode, { persist = true } = {}) {
  const normalized = normalizeChatMode(mode);
  if (normalized === "creator" && !state.creatorUnlocked) {
    state.chatMode = "legal";
    renderChatMode();
    if (els["answer-status"]) {
      els["answer-status"].textContent = "Creator Locked";
    }
    if (els["answer-panel"]) {
      els["answer-panel"].innerHTML = `<div class="note">Creator Mode is locked. Enter the configured unlock phrase once in the conversation shell to unlock it.</div>`;
    }
    return false;
  }
  state.chatMode = normalized;
  if (persist) {
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, state.chatMode);
  }
  renderChatMode();
  return true;
}

function syncCreatorSession(session, fallbackMode = null) {
  if (!session) return;
  if (session.unlocked) {
    state.creatorUnlocked = true;
    localStorage.setItem(CREATOR_UNLOCK_STORAGE_KEY, "true");
  }
  setChatMode(session.unlocked ? (fallbackMode || "creator") : (fallbackMode || state.chatMode));
}

function renderHealth(data) {
  state.health = data;
  const model = data?.model || {};
  const modelReason = model?.reason || (data?.llm_connected ? "connected" : "offline");
  const modelLabel = data?.llm_connected
    ? "Analysis Online"
    : modelReason === "missing_server_and_model" || modelReason === "missing_server" || modelReason === "missing_model"
      ? "Analysis Limited"
      : "Analysis Offline";
  setChip(els["backend-chip"], data?.backend?.status === "online" ? "Backend Online" : "Backend Unknown", data?.backend?.status === "online" ? "ok" : "warn");
  setChip(els["health-chip"], modelLabel, data?.llm_connected ? "ok" : "warn");
  setChip(els["ocr-chip"], data?.capabilities?.ocr ? "OCR Ready" : "OCR Offline", data?.capabilities?.ocr ? "ok" : "warn");
  setChip(els["index-chip"], data?.index?.indexed ? "Index Ready" : "Index Empty", data?.index?.indexed ? "ok" : "warn");
  const licensed = Boolean(data?.license?.licensed) && !Boolean(data?.license?.expired);
  setChip(els["license-chip"], licensed ? "License Active" : "Evaluation", licensed ? "ok" : "warn");
  const activeModelLabel = displayModelName(data?.model?.model_id || data?.model_id) || "local model";
  const contextLabel = data?.model?.context_size ? `ctx ${data.model.context_size}` : "ctx n/a";
  setChip(els["model-chip"], data?.llm_connected ? `${activeModelLabel} • adaptive • ${contextLabel}` : "Analysis Limited", data?.llm_connected ? "ok" : "warn");
  const continuity = data?.firm_tier_continuity || {};
  if (els["continuity-chip"]) {
    if (continuity.enabled) {
      els["continuity-chip"].hidden = false;
      setChip(
        els["continuity-chip"],
        continuity.reset_recommended ? "Continuity Refresh" : "Continuity Stable",
        continuity.reset_recommended ? "warn" : "ok"
      );
    } else {
      els["continuity-chip"].hidden = true;
    }
  }
  setChip(els["workspace-ready-chip"], "Evidence Workspace Ready", "ok");
  setChip(els["analysis-ready-chip"], data?.llm_connected ? "Local Analysis Online" : "Local Analysis Limited", data?.llm_connected ? "ok" : "warn");
  setChip(els["review-boundary-chip"], "Attorney Review Required", "warn");
  updateLocalOnlyControls();
  if (els["model-availability-note"]) {
    els["model-availability-note"].textContent = data?.llm_connected
      ? "Local analysis model online. Evidence organization, timeline review, source search, and packet drafting are available."
      : "Local analysis model unavailable - document organization and read-only evidence tools remain available.";
  }
  const memory = data?.memory || {};
  els["memory-metrics"].innerHTML = `
    <div class="metric-card"><span>Documents</span><strong>${memory.documents ?? 0}</strong></div>
    <div class="metric-card"><span>Cases</span><strong>${memory.cases ?? 0}</strong></div>
    <div class="metric-card"><span>Matters</span><strong>${memory.matters ?? 0}</strong></div>
    <div class="metric-card"><span>Evidence</span><strong>${memory.evidence ?? 0}</strong></div>
    <div class="metric-card"><span>Filings</span><strong>${memory.filings ?? 0}</strong></div>
    <div class="metric-card"><span>Trace</span><strong>${memory.traces ?? 0}</strong></div>
  `;
  updateInvestorSummary();
  if (els["processing-summary"]) {
    const capabilities = data?.capabilities || {};
    const modelSummary = data?.llm_connected
      ? "Local analysis model connected"
      : modelReason === "missing_server_and_model"
        ? "Local analysis model unavailable"
        : modelReason === "missing_server"
          ? "Local analysis model unavailable"
          : modelReason === "missing_model"
            ? "Local analysis model unavailable"
            : "Local analysis service offline";
    els["processing-summary"].textContent =
      `${modelSummary}. OCR: ${capabilities.ocr ? "ready" : "unavailable"}. PDF export: ${capabilities.pdf_export ? "ready" : "unavailable"}. DOCX export: ${capabilities.docx_export ? "ready" : "unavailable"}.`;
  }
  if (els["technical-status-detail"]) {
    const capabilities = data?.capabilities || {};
    els["technical-status-detail"].textContent = [
      `Backend status: ${data?.backend?.status || "unknown"}`,
      `Model connected: ${Boolean(data?.llm_connected)}`,
      `Model id: ${displayModelName(data?.model_id) || "local"}`,
      `Model mode policy: ${data?.model?.mode_policy || "n/a"}`,
      `Model context size: ${data?.model?.context_size || "n/a"}`,
      `Fallback model: ${data?.model?.fallback_model || "n/a"}`,
      `Model endpoint: ${data?.api_url || "n/a"}`,
      `Model reason: ${modelReason || "n/a"}`,
      `OCR: ${capabilities.ocr ? "ready" : "unavailable"}`,
      `PDF export: ${capabilities.pdf_export ? "ready" : "unavailable"}`,
      `DOCX export: ${capabilities.docx_export ? "ready" : "unavailable"}`,
      `Index: ${data?.index?.indexed ? "ready" : "empty"}`,
    ].join("\n");
  }
  renderGuideMe();
}

function renderHealthResult(data) {
  const capabilities = data?.capabilities || {};
  const model = data?.model || {};
  const deployment = data?.deployment || {};
  const modelLabel = displayModelName(model.model_id || data?.model_id) || "connected";
  return resultRows([
    ["Application health", escapeHtml(data?.backend?.status || "unknown")],
    ["Deployed SHA", escapeHtml(deployment.source_git_sha || "unavailable")],
    ["Build ref", escapeHtml(deployment.source_git_ref || "unavailable")],
    ["Model availability", escapeHtml(data?.llm_connected ? modelLabel : "Unavailable or degraded")],
    ["OCR availability", escapeHtml(capabilities.ocr ? "Available" : "Unavailable")],
    ["PDF export", escapeHtml(capabilities.pdf_export ? "Available" : "Unavailable")],
    ["DOCX export", escapeHtml(capabilities.docx_export ? "Available" : "Unavailable")],
    ["Continuity", escapeHtml(data?.firm_tier_continuity?.enabled ? "Available" : "Limited")],
    ["Provenance", escapeHtml((data?.memory?.traces ?? 0) > 0 ? `${data.memory.traces} trace record(s)` : "No trace records yet")],
  ]);
}

function renderMatterSelectionResult(bundle) {
  const matter = bundle?.matter || state.matter || {};
  return resultRows([
    ["Selected matter", escapeHtml(matter.title || matter.case_id || state.activeCaseId || "None")],
    ["Matter ID", escapeHtml(matter.case_id || state.activeCaseId || "unassigned")],
    ["Court", escapeHtml(matter.court_name || "n/a")],
    ["Practice area", escapeHtml(matter.practice_area || "n/a")],
    ["Summary", escapeHtml(`${matter.plaintiff || "Plaintiff"} v. ${matter.defendant || "Defendant"}`)],
  ]);
}

function renderDemoMatterResult(data) {
  return resultRows([
    ["Loaded matter", escapeHtml(data?.matter?.title || "Harbor Point Commercial Dispute")],
    ["Matter ID", escapeHtml(data?.case_id || data?.matter?.case_id || state.activeCaseId || "harbor-point-commercial-dispute")],
    ["Document count", escapeHtml(data?.evidence_items ?? matterStats().evidenceCount ?? 0)],
    ["Timeline events", escapeHtml(data?.timeline_events ?? matterStats().timelineCount ?? 0)],
    ["Contradictions", escapeHtml(data?.analysis?.anomalies?.length ?? matterStats().contradictionCount ?? 0)],
    ["Status", "Sample Demo Matter loaded for attorney-review workflow."],
  ]);
}

function renderSearchResultPanel(query, data) {
  const items = data?.items || [];
  return `
    ${resultRows([
      ["Query", escapeHtml(query || "")],
      ["Matches", escapeHtml(items.length)],
      ["Confidence", escapeHtml(items.length ? "Ranked by relevance" : "No relevant records found")],
    ])}
    ${resultItems(items.slice(0, 6), (item) => `
      <strong>${escapeHtml(item.title || item.source_name || item.citation || item.id || "Record")}</strong>
      <div class="note">${escapeHtml(short(item.text || item.snippet || "", 240))}</div>
      <div class="case-meta">${escapeHtml(item.record_id || item.id || "record")} • ${escapeHtml(item.citation || item.source_name || "source")}</div>
    `, "No matching records found.")}
  `;
}

function renderChatResultPanel(reply, citations, context = {}) {
  const model = context?.model || {};
  const traceId = context?.trace_id || context?.truth_spine?.trace_id || "";
  return `
    ${resultRows([
      ["Supported facts", escapeHtml((citations || []).length ? `${citations.length} cited source(s)` : "No cited sources returned")],
      ["User allegations", "Preserved as user-provided unless supported by evidence."],
      ["Legal analysis", escapeHtml(reply ? "Generated for attorney review" : "No answer generated")],
      ["Unresolved uncertainty", escapeHtml((context?.warnings || []).join("; ") || "Review citations before use")],
      ["Trace ID", escapeHtml(traceId || "n/a")],
      ["Model", escapeHtml(model.model_id || context?.model_id || "n/a")],
    ])}
    <div class="action-result-item"><strong>Answer</strong><pre class="action-result-pre">${escapeHtml(reply || "No answer returned.")}</pre></div>
    ${resultItems((citations || []).slice(0, 6), (item) => `
      <strong>${escapeHtml(item.citation || item.source_name || item.title || "Citation")}</strong>
      <div class="note">${escapeHtml(short(item.text || item.snippet || item.source_url || "", 220))}</div>
      ${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Open source</a>` : ""}
    `, "No citations returned.")}
  `;
}

function renderTimelineResultPanel(items) {
  return `
    ${resultRows([
      ["Chronology entries", escapeHtml((items || []).length)],
      ["Conflicts", escapeHtml(state.analysis?.anomalies?.length || 0)],
      ["Date certainty", "Uncertain or stale dates remain flagged in source cards when available."],
    ])}
    ${resultItems((items || []).slice(0, 8), (item) => `
      <strong>${escapeHtml(item.title || item.event_type || "Event")}</strong>
      <div class="note">${escapeHtml(short(item.summary || "", 220))}</div>
      <div class="case-meta">${escapeHtml(fmtTime(item.timestamp))} • ${escapeHtml(item.citation || item.source_name || "source")}</div>
    `, "No chronology entries available.")}
  `;
}

function renderContradictionsResultPanel(data) {
  const anomalies = data?.anomalies || state.analysis?.anomalies || [];
  return `
    ${resultRows([
      ["Conflicting statements", escapeHtml(anomalies.length)],
      ["Confidence", escapeHtml(anomalies.length ? "Ranked by severity" : "No contradictions detected")],
      ["Unresolved issues", escapeHtml(anomalies.length ? "Attorney review required" : "None flagged")],
    ])}
    ${resultItems(anomalies, (item) => `
      <strong>${escapeHtml(item.label || "Potential inconsistency")}</strong>
      <div class="note">${escapeHtml(item.summary || "")}</div>
      <div class="case-meta">severity ${escapeHtml(Number(item.severity ?? 0).toFixed(2))}</div>
    `, "No contradictions detected yet.")}
  `;
}

function renderTraceResultPanel(items) {
  return `
    ${resultRows([
      ["Trace records", escapeHtml((items || []).length)],
      ["Truth Spine", escapeHtml((items || []).length ? "References available in trace list" : "No trace references yet")],
      ["TrailLink", "Source path shown when emitted by backend trace records."],
    ])}
    ${resultItems((items || []).slice(0, 8), (item) => `
      <strong>${escapeHtml(item.title || item.event_type || "trace")}</strong>
      <div class="note">${escapeHtml(short(item.summary || "", 220))}</div>
      <div class="case-meta">${escapeHtml(item.trace_id || "trace")} • ${escapeHtml(item.case_id || "unassigned")} • ${escapeHtml(fmtTime(item.timestamp))}</div>
    `, "No provenance records available.")}
  `;
}

function renderCases(items) {
  state.cases = items || [];
  if (!state.activeCaseId && state.cases.length) {
    state.activeCaseId = state.cases[0].case_id;
  }
  els["case-list"].innerHTML = (state.cases.length ? state.cases : [{ case_id: "unassigned", title: "Unassigned Matters", status: "active", tags: ["ingest"] }]).map((item) => {
    const active = item.case_id === state.activeCaseId ? "active" : "";
    return `
      <button class="case-item ${active}" data-case-id="${escapeHtml(item.case_id)}">
        <div class="case-title">
          <span>${escapeHtml(item.title || item.case_id)}</span>
          <span class="timeline-pill">${escapeHtml(item.status || "active")}</span>
        </div>
        <div class="case-meta">${escapeHtml(item.case_id)} • ${escapeHtml((item.tags || []).join(" / "))}</div>
      </button>
    `;
  }).join("");
  els["case-list"].querySelectorAll("[data-case-id]").forEach((btn) => btn.addEventListener("click", () => {
    state.activeCaseId = btn.getAttribute("data-case-id");
    state.analysis = null;
    setActionPanel("matter-selection-result", "loading", `<div class="note">Loading selected matter...</div>`);
    refreshWorkspace({ showPanel: true });
  }));
}

function renderEvidence(items) {
  const rows = items || [];
  els["evidence-list"].innerHTML = rows.length ? rows.map((item) => `
    <div class="evidence-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.title || item.source_name || item.id || "Evidence")}</strong>
        <span class="timeline-pill">${escapeHtml(Number(item.final_score ?? 0).toFixed(3))}</span>
      </div>
      <div class="note">${escapeHtml(short(item.text, 220))}</div>
      <div class="case-meta">${escapeHtml(item.citation || item.source_name || "")} • ${fmtTime(item.timestamp)}</div>
    </div>
  `).join("") : `<div class="note">No evidence yet. Upload a document or run a search.</div>`;
  updateInvestorSummary();
}

function renderQueue(items) {
  const rows = items || [];
  els["queue-list"].innerHTML = rows.length ? rows.slice(0, 4).map((item, index) => `
    <div class="queue-item">
      <div class="stack-row">
        <strong>${index + 1}. ${escapeHtml(item.title || item.source_name || item.event_type || "Activity")}</strong>
        <span class="timeline-pill">${escapeHtml(item.event_type || item.source_type || "record")}</span>
      </div>
      <div class="note">${escapeHtml(short(item.summary || item.text, 160))}</div>
      <div class="case-meta">${escapeHtml(item.case_id || "unassigned")} • ${fmtTime(item.timestamp)}</div>
    </div>
  `).join("") : `<div class="note">No ingest or processing activity yet.</div>`;
  updateInvestorSummary();
}

function renderTimeline(items) {
  state.timeline = items || [];
  els["timeline-list"].innerHTML = state.timeline.length ? state.timeline.map((item) => `
    <div class="timeline-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.title || item.event_type || "Event")}</strong>
        <span class="timeline-pill">${escapeHtml(item.event_type || "event")}</span>
      </div>
      <div class="note">${escapeHtml(short(item.summary || "", 220))}</div>
      <div class="case-meta">${escapeHtml(item.citation || "")} • ${fmtTime(item.timestamp)}</div>
    </div>
  `).join("") : `<div class="note">Timeline will appear after ingest or chat activity.</div>`;
  renderGuideMe();
  updateInvestorSummary();
}

function renderCitations(items) {
  state.citations = items || [];
  els["citation-list"].innerHTML = state.citations.length ? state.citations.map((item) => `
    <div class="citation-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.citation || item.source_name || item.title || "Citation")}</strong>
        <span class="timeline-pill">${escapeHtml(item.source_class || item.result_type || (Number.isFinite(Number(item.final_score)) ? Number(item.final_score).toFixed(3) : "source"))}</span>
      </div>
      <div class="note">${escapeHtml(short(item.text || item.snippet || item.source_url || "", 160))}</div>
      ${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Open source</a>` : ""}
    </div>
  `).join("") : `<div class="note">No grounded citations yet.</div>`;
  renderGuideMe();
  updateInvestorSummary();
}

function renderTraces(items) {
  state.traces = items || [];
  els["trace-list"].innerHTML = state.traces.length ? state.traces.map((item) => `
    <div class="trace-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.title || item.event_type || "trace")}</strong>
        <span class="timeline-pill">${escapeHtml(fmtTime(item.timestamp))}</span>
      </div>
      <div class="note">${escapeHtml(short(item.summary || "", 180))}</div>
      <div class="case-meta">${escapeHtml(item.trace_id || "trace")} • ${escapeHtml(item.case_id || "unassigned")}</div>
    </div>
  `).join("") : `<div class="note">Trace panel is idle.</div>`;
  updateInvestorSummary();
}

function renderGyro(data) {
  state.are = data;
  if (!els["gyro-prefix"] || !els["gyro-items"]) return;
  els["gyro-prefix"].textContent = data?.visor || data?.prefix || "No visor output yet.";
  const items = data?.items || [];
  els["gyro-items"].innerHTML = items.length ? items.map((item) => `
    <div class="evidence-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.source || item.axis || "memory")}</strong>
        <span class="timeline-pill">${escapeHtml(item.gyro_score ?? item.final_score ?? "")}</span>
      </div>
      <div class="note">${escapeHtml(short(item.text || "", 180))}</div>
    </div>
  `).join("") : `<div class="note">No rail items yet.</div>`;
}

function renderCourtProfiles(items) {
  state.courtProfiles = items || [];
  if (els["court-profile-select"]) {
    const current = els["court-profile-select"].value || state.matter?.court_profile_id || "federal_district_civil";
    els["court-profile-select"].innerHTML = state.courtProfiles.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    els["court-profile-select"].value = current;
  }
  if (els["court-profile-list"]) {
    els["court-profile-list"].innerHTML = state.courtProfiles.length ? state.courtProfiles.map((item) => `
      <div class="hint-card">
        <div class="stack-row">
          <strong>${escapeHtml(item.name)}</strong>
          <span class="timeline-pill">${escapeHtml(item.id)}</span>
        </div>
        <div class="note">${escapeHtml(item.scope || "")}</div>
      </div>
    `).join("") : `<div class="note">No court profiles loaded.</div>`;
  }
}

function renderCourtProfileReport(report) {
  if (!els["court-profile-report"]) return;
  if (!report) {
    els["court-profile-report"].innerHTML = `<div class="note">No profile report available.</div>`;
    return;
  }
  const missing = report.missing_fields || [];
  const localNotes = report.local_rules_notes || [];
  const sourceFiles = report.source_files || [];
  els["court-profile-report"].innerHTML = `
    <div class="hint-card">
      <div class="stack-row">
        <strong>${escapeHtml(report.profile?.name || "Court Profile")}</strong>
        <span class="timeline-pill">${report.ready ? "ready" : "review"}</span>
      </div>
      <div class="note" style="margin-top: 10px;">${escapeHtml((report.notes || []).join(" "))}</div>
      <div class="note" style="margin-top: 10px;">Missing fields: ${escapeHtml(missing.length ? missing.join(", ") : "none")}</div>
      <div class="note" style="margin-top: 10px;">Local notes: ${escapeHtml(localNotes.length ? localNotes.join(" ") : "none")}</div>
      <div class="note" style="margin-top: 10px;">Source files: ${escapeHtml(sourceFiles.length ? sourceFiles.join(", ") : "none")}</div>
    </div>
  `;
}

function renderCourtRulesStatus(message, count = null) {
  if (!els["court-rules-status"]) return;
  const suffix = count === null ? "" : ` • ${count} profile(s) updated`;
  els["court-rules-status"].textContent = `${message || "Ready"}${suffix}`;
}

function renderTemplates(items) {
  state.templates = items || [];
  if (els["draft-template-select"]) {
    const current = els["draft-template-select"].value || "motion_to_compel";
    els["draft-template-select"].innerHTML = state.templates.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.title)}</option>`).join("");
    els["draft-template-select"].value = current;
  }
  if (els["template-list"]) {
    els["template-list"].innerHTML = state.templates.length ? state.templates.map((item) => `
      <div class="hint-card">
        <div class="stack-row">
          <strong>${escapeHtml(item.title)}</strong>
          <span class="timeline-pill">${escapeHtml(item.category || "template")}</span>
        </div>
        <div class="note">${escapeHtml(item.purpose || "")}</div>
      </div>
    `).join("") : `<div class="note">No filing templates loaded.</div>`;
  }
}

function renderMatter(bundle) {
  if (!bundle) return;
  const matter = bundle.matter || bundle;
  state.matter = matter;
  const profile = bundle.court_profile || {};
  const firm = bundle.firm_profile || state.firmProfiles.find((item) => item.id === matter.firm_profile_id) || {};
  const authority = bundle.authority || state.authority || {};
  const courtName = matter.court_name || profile.name || "Federal Court";
  if (els["matter-title"]) els["matter-title"].value = matter.title || "";
  if (els["matter-court"]) els["matter-court"].value = courtName || "";
  if (els["matter-plaintiff"]) els["matter-plaintiff"].value = matter.plaintiff || "";
  if (els["matter-defendant"]) els["matter-defendant"].value = matter.defendant || "";
  if (els["matter-practice"]) els["matter-practice"].value = matter.practice_area || "";
  if (els["matter-notes"]) els["matter-notes"].value = matter.notes || "";
  if (els["billing-increment"]) els["billing-increment"].value = String(matter.billing_increment_minutes || 15);
  if (els["billing-rate"]) els["billing-rate"].value = String(matter.billing_rate || 0);
  if (els["court-profile-select"]) els["court-profile-select"].value = matter.court_profile_id || "federal_district_civil";
  if (els["matter-status"]) els["matter-status"].textContent = `${matter.jurisdiction || "Federal"} / ${matter.court_profile_id || "profile"}`;
  if (els["matter-summary-left"]) {
    els["matter-summary-left"].textContent = `${matter.title || "Unassigned matter"} • ${courtName} • ${matter.plaintiff || "Plaintiff"} v. ${matter.defendant || "Defendant"}${firm.name ? ` • ${firm.name}` : ""}`;
  }
  if (els["active-matter-chip"]) {
    els["active-matter-chip"].textContent = `matter: ${matter.case_id || "unassigned"}`;
  }
  if (els["billing-summary"]) {
    els["billing-summary"].textContent = `Billing increment: ${matter.billing_increment_minutes || 15} minutes • Rate: ${matter.billing_rate || 0}`;
  }
  if (els["firm-profile-select"] && matter.firm_profile_id) {
    els["firm-profile-select"].value = matter.firm_profile_id;
  }
  if (els["authority-firm-profile"] && matter.firm_profile_id) {
    els["authority-firm-profile"].value = matter.firm_profile_id;
  }
  if (els["authority-summary"] && authority?.responsibility_stamp) {
    els["authority-summary"].textContent = authority.responsibility_stamp;
  }
  if (els["docket-status"]) {
    const docketSummary = bundle.docket_summary || {};
    els["docket-status"].textContent = docketSummary.count
      ? `Docket: ${docketSummary.count} entries • ${Object.keys(docketSummary.event_types || {}).join(", ") || "events"}`
      : "No docket events loaded.";
  }
  renderCourtProfileReport(bundle.court_profile_report || null);
}

function renderAnalysis(data) {
  state.analysis = data;
  if (!data) return;
  const scenarios = data.scenarios || [];
  const anomalies = data.anomalies || [];
  const filings = data.filing_suggestions || [];
  const billing = data.billing || {};
  if (els["theory-output"]) {
    els["theory-output"].textContent = scenarios.length ? scenarios[0].summary : "No theory available yet.";
  }
  if (els["anomaly-list"]) {
    els["anomaly-list"].innerHTML = anomalies.length ? anomalies.map((item) => `
      <div class="hint-card">
        <div class="stack-row">
          <strong>${escapeHtml(item.label || "anomaly")}</strong>
          <span class="timeline-pill">${escapeHtml(Number(item.severity ?? 0).toFixed(2))}</span>
        </div>
        <div class="note">${escapeHtml(item.summary || "")}</div>
      </div>
    `).join("") : `<div class="note">No anomalies detected yet.</div>`;
  }
  if (els["filing-list"]) {
    els["filing-list"].innerHTML = filings.length ? filings.map((item) => `
      <div class="hint-card">
        <div class="stack-row">
          <strong>${escapeHtml(item.title || item.template_id || "Filing")}</strong>
          <span class="timeline-pill">${escapeHtml(item.template_id || "")}</span>
        </div>
        <div class="note">${escapeHtml(item.reason || "")}</div>
      </div>
    `).join("") : `<div class="note">No filing suggestions yet.</div>`;
  }
  if (els["draft-output"]) {
    const packet = data.packet || {};
    const sections = packet.sections || [];
    els["draft-output"].textContent = [
      `Court Profile: ${packet.court_profile?.name || "n/a"}`,
      `Template: ${packet.template?.title || "n/a"}`,
      `Sensitive Findings: ${packet.sensitivity?.count ?? 0}`,
      `Estimated Hours: ${billing.estimated_hours ?? "n/a"}`,
      `Estimated Value: ${billing.estimated_value ?? "n/a"}`,
      "",
      sections.length ? sections.join("\n\n---\n\n") : "No draft packet yet.",
    ].join("\n");
  }
  if (els["billing-summary"]) {
    els["billing-summary"].textContent = `Estimated ${billing.estimated_hours ?? 0} hours • $${billing.estimated_value ?? 0} value • ${billing.increment_minutes ?? 15}-minute increment`;
  }
  renderGuideMe();
  updateInvestorSummary();
}

function renderAnswer(reply, citations, context = {}) {
  state.answer = reply || "";
  const railResults = context?.recognition_rail?.results || [];
  const webResults = context?.public_web_search?.results || [];
  const regulationResults = context?.public_regulatory_lookup?.results || [];
  const model = context?.model || {};
  if (els["answer-status"]) {
    els["answer-status"].textContent = reply ? "Grounded Answer Ready" : "Idle";
  }
  if (els["answer-sources"]) {
    const count = (citations || []).length;
    const railUsed = Boolean(context?.recognition_rail?.used);
    const webUsed = Boolean(context?.public_web_search?.used);
    const regulationUsed = Boolean(context?.public_regulatory_lookup?.used);
    const total = count + railResults.length + webResults.length + regulationResults.length;
    const lanes = [];
    if (railUsed) lanes.push("CourtListener");
    if (webUsed) lanes.push("Public Web");
    if (regulationUsed) lanes.push("Regulations");
    const modelMode = model.mode ? ` • ${model.mode}` : "";
    els["answer-sources"].textContent = `${total} source${total === 1 ? "" : "s"}${lanes.length ? ` • ${lanes.join(" / ")}` : ""}${modelMode}`;
  }
  els["answer-panel"].innerHTML = `
    <div class="answer ${reply ? "" : "answer-empty"}">${escapeHtml(reply || "Awaiting a grounded question.")}</div>
    ${model.model_id ? `<div class="note mt-2">Model: ${escapeHtml(model.model_id)} • ${escapeHtml(model.mode || "adaptive")} • context ${escapeHtml(model.context_size || "n/a")}</div>` : ""}
    ${context?.recognition_rail?.used ? '<div class="mt-3 text-[11px] uppercase tracking-[0.24em] text-amber-300/70">Recognition Rail prefetch engaged</div>' : ""}
    ${context?.public_web_search?.used ? '<div class="mt-3 text-[11px] uppercase tracking-[0.24em] text-amber-300/70">Public Web research engaged</div>' : ""}
    ${context?.public_regulatory_lookup?.used ? '<div class="mt-3 text-[11px] uppercase tracking-[0.24em] text-amber-300/70">Public regulation lookup engaged</div>' : ""}
    ${railResults.length ? `
      <div class="rail-results">
        ${railResults.slice(0, 5).map((item) => `
          <div class="rail-result">
            <strong>${escapeHtml(item.title || "CourtListener result")}</strong>
            <div class="note">${escapeHtml([item.court, item.date_filed, item.docket_number].filter(Boolean).join(" • "))}</div>
            <div class="note">${escapeHtml(short(item.snippet || "", 220))}</div>
            ${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Open CourtListener source</a>` : ""}
          </div>
        `).join("")}
      </div>
    ` : context?.recognition_rail && !context.recognition_rail.used ? `<div class="note">${escapeHtml(courtListenerStatusMessage(context.recognition_rail))}</div>` : ""}
    ${webResults.length || regulationResults.length ? `
      <div class="rail-results">
        ${regulationResults.slice(0, 3).map((item) => `
          <div class="rail-result">
            <strong>${escapeHtml(item.title || item.citation || "Public regulation")}</strong>
            <div class="note">${escapeHtml(short(item.snippet || item.text || "", 260))}</div>
            ${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Open regulation source</a>` : ""}
          </div>
        `).join("")}
        ${webResults.slice(0, 5).map((item) => `
          <div class="rail-result">
            <strong>${escapeHtml(item.title || "Public web result")}</strong>
            <div class="note">${escapeHtml(short(item.snippet || item.text || "", 220))}</div>
            ${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">Open public web source</a>` : ""}
          </div>
        `).join("")}
      </div>
    ` : ""}
    <div class="citation-badges" style="margin-top: 14px;">
  ${(citations || []).slice(0, 6).map((item) => `<span class="badge">${escapeHtml(item.citation || item.source_name || "source")}</span>`).join("")}
  ${railResults.slice(0, 6).map((item) => `<span class="badge">${escapeHtml(item.title || item.source_url || "CourtListener")}</span>`).join("")}
  ${regulationResults.slice(0, 3).map((item) => `<span class="badge">${escapeHtml(item.citation || item.title || "Regulation")}</span>`).join("")}
  ${webResults.slice(0, 6).map((item) => `<span class="badge">${escapeHtml(item.title || item.source_url || "Public Web")}</span>`).join("")}
    </div>
  `;
}

function courtListenerStatusMessage(rail) {
  const reason = rail?.reason || "";
  if (reason.startsWith("courtlistener_http_") || reason === "courtlistener_error") {
    return "CourtListener could not be reached right now. Try again shortly or verify the citation manually.";
  }
  if (reason === "courtlistener_prefetch") {
    return "CourtListener returned no matching public results.";
  }
  return "";
}

async function fetchCases() {
  const data = await json("/cases");
  return data.items || [];
}

async function fetchMatter() {
  const data = await json(`/matter?case_id=${encodeURIComponent(state.activeCaseId || "")}`);
  return data;
}

async function fetchCourtProfiles() {
  const data = await json("/court-profiles");
  return data.items || [];
}

async function fetchTemplates() {
  const data = await json("/filing-templates");
  return data.items || [];
}

async function fetchTraces() {
  const data = await json(`/traces?case_id=${encodeURIComponent(state.activeCaseId || "")}&limit=40`);
  return data.items || [];
}

async function loadCourtRules() {
  const path = els["court-rules-path"]?.value || "web/rules";
  const data = await json("/court-rules/load", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
  renderCourtRulesStatus(`Loaded ${data.result?.loaded ?? 0} rule pack(s) from ${path}`, (data.result?.updated_profiles || []).length);
  const profiles = await fetchCourtProfiles();
  renderCourtProfiles(profiles);
  const bundle = await fetchMatter();
  renderMatter(bundle);
  renderCourtProfileReport(bundle.court_profile_report || null);
  setActionPanel("court-rules-result", "success", resultRows([
    ["Status", "Court rules loaded."],
    ["Source", escapeHtml(path)],
    ["Rule packs", escapeHtml(data.result?.loaded ?? 0)],
    ["Profiles updated", escapeHtml((data.result?.updated_profiles || []).length)],
  ]));
  scrollActionPanel("court-rules-result");
}

async function importDocket() {
  const input = els["docket-input"];
  const file = input?.files?.[0];
  const pasted = els["docket-text"]?.value || "";
  const caseId = state.activeCaseId || null;
  const courtName = state.matter?.court_name || els["matter-court"]?.value || "Federal Court";
  const sourceName = file ? file.name : "pasted-docket";
  let payload = { case_id: caseId, court_name: courtName, source_name: sourceName };
  if (file) {
    const text = await readFile(file, "text");
    payload.text = text;
  } else if (pasted.trim()) {
    payload.text = pasted;
  } else {
    els["docket-status"].textContent = "Paste a docket export or choose a file first.";
    setActionPanel("docket-result", "error", errorPanelMessage("Paste a docket export or choose a docket file before importing."));
    scrollActionPanel("docket-result");
    return false;
  }
  const data = await json("/docket/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  els["docket-status"].textContent = `Imported ${data.result?.recorded || 0} docket entries from ${sourceName}.`;
  if (input) input.value = "";
  if (els["docket-text"]) els["docket-text"].value = "";
  await refreshWorkspace();
  setActionPanel("docket-result", "success", resultRows([
    ["Status", "Docket imported."],
    ["Source", escapeHtml(sourceName)],
    ["Entries", escapeHtml(data.result?.recorded || 0)],
    ["Matter", escapeHtml(caseId || "unassigned")],
  ]));
  scrollActionPanel("docket-result");
  return data;
}

function collectMatterPayload() {
  return {
    case_id: state.activeCaseId || null,
    title: els["matter-title"]?.value || state.activeCaseId || "Unassigned Matter",
    court_profile_id: els["court-profile-select"]?.value || "federal_district_civil",
    firm_profile_id: els["authority-firm-profile"]?.value || els["firm-profile-select"]?.value || state.matter?.firm_profile_id || null,
    court_name: els["matter-court"]?.value || "Federal Court",
    jurisdiction: "Federal",
    matter_type: "civil",
    practice_area: els["matter-practice"]?.value || "Litigation",
    plaintiff: els["matter-plaintiff"]?.value || "",
    defendant: els["matter-defendant"]?.value || "",
    billing_increment_minutes: Number(els["billing-increment"]?.value || 15),
    billing_rate: Number(els["billing-rate"]?.value || 0),
    confidentiality_level: "Privileged",
    notes: els["matter-notes"]?.value || "",
    prepared_by_id: els["authority-prepared-by"]?.value || null,
    reviewed_by_id: els["authority-reviewed-by"]?.value || null,
    approved_by_id: els["authority-approved-by"]?.value || null,
    signed_by_id: els["authority-signed-by"]?.value || null,
    filed_by_id: els["authority-filed-by"]?.value || null,
  };
}

async function saveMatter() {
  const data = await json("/matter", { method: "POST", body: JSON.stringify(collectMatterPayload()) });
  renderMatter(data.bundle || data.matter || {});
  await refreshWorkspace();
  setActionPanel("matter-result", "success", resultRows([
    ["Status", "Matter saved."],
    ["Selected matter", escapeHtml(state.matter?.title || state.activeCaseId || "unassigned")],
    ["Matter ID", escapeHtml(state.matter?.case_id || state.activeCaseId || "unassigned")],
    ["Court", escapeHtml(state.matter?.court_name || "n/a")],
  ]));
  scrollActionPanel("matter-result");
}

async function loadDefaultMatter() {
  const bundle = await fetchMatter();
  const profiles = await fetchCourtProfiles();
  const templates = await fetchTemplates();
  renderCourtProfiles(profiles);
  renderTemplates(templates);
  renderMatter(bundle);
}

async function runAnalysis() {
  const query = els["chat-input"].value.trim() || els["search-input"].value.trim() || (state.matter?.title || "legal intelligence");
  const data = await json("/analyze", {
    method: "POST",
    body: JSON.stringify({ query, case_id: state.activeCaseId || null, top_k: 10 }),
  });
  renderAnalysis(data);
  renderCitations(data.records || []);
  renderEvidence(data.records || []);
  const timelineData = await json("/timeline", { method: "POST", body: JSON.stringify({ case_id: state.activeCaseId || null, limit: 100 }) });
  renderTimeline(timelineData.items || []);
  const traces = await fetchTraces();
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  els["matter-status"].textContent = "Analysis complete";
  setActionPanel("matter-result", "success", resultRows([
    ["Status", "Analysis complete."],
    ["Records reviewed", escapeHtml((data.records || []).length)],
    ["Timeline events", escapeHtml((timelineData.items || []).length)],
    ["Contradictions", escapeHtml((data.anomalies || []).length)],
    ["Packet status", escapeHtml(data.packet ? "Preview ready" : "Ready to draft")],
  ]));
  setActionPanel("contradictions-result", "success", renderContradictionsResultPanel(data));
  setActionPanel("timeline-result", "success", renderTimelineResultPanel(timelineData.items || []));
  scrollActionPanel("matter-result");
}

async function runDraft() {
  const templateId = els["draft-template-select"]?.value || "motion_to_compel";
  const query = els["chat-input"].value.trim() || els["search-input"].value.trim() || "discovery dispute";
  const data = await json("/draft", {
    method: "POST",
    body: JSON.stringify({ template_id: templateId, case_id: state.activeCaseId || null, query }),
  });
  renderAnalysis({ ...(state.analysis || {}), packet: data.packet });
  const traces = await fetchTraces();
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  els["draft-output"].textContent = data.draft_text || "Draft generated.";
  setActionPanel("packet-result", "success", resultRows([
    ["Status", "Attorney-review packet preview generated."],
    ["Template", escapeHtml(templateId)],
    ["Sections", escapeHtml((data.packet?.sections || []).length)],
    ["Source count", escapeHtml((data.packet?.source_record_ids || data.packet?.sources || []).length || (state.citations || []).length)],
    ["Review requirement", "Attorney review required before use."],
  ]));
  scrollActionPanel("packet-result");
}

async function exportDraft() {
  const templateId = els["draft-template-select"]?.value || "motion_to_compel";
  const query = els["chat-input"].value.trim() || els["search-input"].value.trim() || "discovery dispute";
  const format = els["export-format"]?.value || "markdown";
  const redact = Boolean(els["redact-export"]?.checked);
  if (format === "docx") {
    const response = await fetch(apiPath("/export_packet_docx"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
      body: JSON.stringify({
        template_id: templateId,
        case_id: state.activeCaseId || null,
        query,
        format,
        redact,
      }),
    });
    if (!response.ok) {
      throw new Error(publicErrorMessage(response.status, await response.text()));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const filename = `${state.activeCaseId || "unassigned"}_${templateId}.docx`;
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    els["draft-output"].textContent = "DOCX export generated.";
    setActionPanel("export-result", "success", resultRows([
      ["Status", "DOCX export generated."],
      ["Filename", escapeHtml(filename)],
      ["Format", "DOCX"],
      ["File size", escapeHtml(`${blob.size} bytes`)],
    ]));
    scrollActionPanel("export-result");
    return;
  }
  if (format === "pdf") {
    const response = await fetch(apiPath("/export_packet_pdf"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/pdf" },
      body: JSON.stringify({
        template_id: templateId,
        case_id: state.activeCaseId || null,
        query,
        format,
        redact,
      }),
    });
    if (!response.ok) {
      throw new Error(publicErrorMessage(response.status, await response.text()));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const filename = `${state.activeCaseId || "unassigned"}_${templateId}.pdf`;
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    els["draft-output"].textContent = "PDF export generated.";
    setActionPanel("export-result", "success", resultRows([
      ["Status", "PDF export generated."],
      ["Filename", escapeHtml(filename)],
      ["Format", "PDF"],
      ["File size", escapeHtml(`${blob.size} bytes`)],
    ]));
    scrollActionPanel("export-result");
    return;
  }
  const data = await json("/export_packet", {
    method: "POST",
    body: JSON.stringify({
      template_id: templateId,
      case_id: state.activeCaseId || null,
      query,
      format,
      redact,
    }),
  });
  const blob = new Blob([data.markdown || ""], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = data.filename || "claire_veritas_packet.md";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  els["draft-output"].textContent = data.markdown || "Export generated.";
  setActionPanel("export-result", "success", `
    ${resultRows([
      ["Status", "Packet export generated."],
      ["Filename", escapeHtml(data.filename || "claire_veritas_packet.md")],
      ["Format", escapeHtml(format.toUpperCase())],
      ["Review requirement", "Attorney review required before use."],
    ])}
    <div class="action-result-item"><strong>Preview</strong><pre class="action-result-pre">${escapeHtml(data.markdown || "Export generated.")}</pre></div>
  `);
  scrollActionPanel("export-result");
}

async function refreshWorkspace({ showPanel = false } = {}) {
  const caseId = state.activeCaseId || "";
  const searchQuery = els["search-input"].value.trim() || "legal intelligence";
  const [healthData, timeline, cases, matter, profiles, templates, traces, search, gyro, firmProfiles, staffDirectory, authority] = await Promise.all([
    json("/health"),
    json("/timeline", { method: "POST", body: JSON.stringify({ case_id: caseId || null, limit: 100 }) }),
    fetchCases(),
    fetchMatter(),
    fetchCourtProfiles(),
    fetchTemplates(),
    fetchTraces(),
    json("/search", { method: "POST", body: JSON.stringify({ query: searchQuery, case_id: caseId || null, top_k: 8 }) }),
    json("/recognition-rail/debug"),
    json("/firm-profiles"),
    json("/staff-directory"),
    json(`/authority?case_id=${encodeURIComponent(caseId || "")}`),
  ]);
  renderHealth(healthData);
  renderTimeline(timeline.items || []);
  renderCases(cases);
  renderFirmProfiles(firmProfiles.items || []);
  renderStaffDirectory(staffDirectory.items || []);
  renderAuthority(authority);
  renderMatter(matter);
  renderCourtProfiles(profiles);
  renderTemplates(templates);
  renderCourtProfileReport((matter && matter.court_profile_report) || state.matter?.court_profile_report || null);
  els["case-filter"].textContent = caseId || "all matters";
  const items = search.items || [];
  state.searchResults = items;
  renderEvidence(items);
  renderCitations(items);
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  renderGyro(gyro);
  if (els["ingest-summary"]) {
    els["ingest-summary"].textContent = state.ingestActivity.length
      ? `${state.ingestActivity.length} recent processing event(s) in ${caseId || "all matters"}. Latest: ${state.ingestActivity[0].title || state.ingestActivity[0].event_type}.`
      : "No recent ingest or processing events recorded.";
  }
  if (!state.analysis) {
    renderAnalysis(await json("/analyze", { method: "POST", body: JSON.stringify({ query: searchQuery, case_id: caseId || null, top_k: 8 }) }));
  }
  renderGuideMe();
  if (showPanel) {
    setActionPanel("health-result", "success", renderHealthResult(healthData));
    setActionPanel("matter-selection-result", "success", renderMatterSelectionResult(matter));
    setActionPanel("timeline-result", "success", renderTimelineResultPanel(timeline.items || []));
    setActionPanel("trace-result", "success", renderTraceResultPanel(traces));
    scrollActionPanel("health-result");
  }
}

async function runChat() {
  const message = els["chat-input"].value.trim();
  if (!message) {
    setActionPanel("chat-result", "error", errorPanelMessage("Enter a question before asking Veritas."));
    scrollActionPanel("chat-result");
    return false;
  }
  if (els["answer-status"]) {
    els["answer-status"].textContent = "Thinking";
  }
  if (els["answer-sources"]) {
    els["answer-sources"].textContent = "Gathering sources";
  }
  els["answer-panel"].innerHTML = `<div class="note">Thinking against grounded material...</div>`;
  const data = await json("/chat", {
    method: "POST",
    body: JSON.stringify({ message, case_id: state.activeCaseId || null, mode: state.chatMode, top_k: 8, temperature: 0.2, max_tokens: 700 }),
  });
  syncCreatorSession(data.creator_session, data.mode || state.chatMode);
  renderAnswer(data.reply, data.citations || [], data);
  setActionPanel("chat-result", "success", renderChatResultPanel(data.reply, data.citations || [], data));
  renderCitations([...(data.citations || []), ...(data.recognition_rail?.results || [])]);
  const traces = await fetchTraces();
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  els["chat-input"].value = "";
  updateInvestorSummary();
  scrollActionPanel("chat-result");
  return data;
}

async function runSearch() {
  const query = els["search-input"].value.trim();
  if (!query) {
    setActionPanel("search-result", "error", errorPanelMessage("Enter a search query first."));
    scrollActionPanel("search-result");
    return false;
  }
  const data = await json("/search", { method: "POST", body: JSON.stringify({ query, case_id: state.activeCaseId || null, top_k: 10 }) });
  state.searchResults = data.items || [];
  renderEvidence(data.items || []);
  renderCitations(data.items || []);
  updateInvestorSummary();
  setActionPanel("search-result", "success", renderSearchResultPanel(query, data));
  scrollActionPanel("search-result");
  return data;
}

async function ingestSelectedFile() {
  const input = els["upload-input"];
  const files = Array.from(input.files || []);
  if (!files.length) {
    setActionPanel("file-ingest-result", "error", errorPanelMessage("Choose at least one file before ingesting."));
    scrollActionPanel("file-ingest-result");
    return;
  }
  let totalChunks = 0;
  let totalFailures = 0;
  const fileResults = [];
  for (const file of files) {
    try {
      const isText = /\.(txt|md|csv|json|log|html?|xml|yml|yaml)$/i.test(file.name) || (file.type || "").startsWith("text/");
      const payload = { file_name: file.name, mime_type: file.type || "application/octet-stream", case_id: state.activeCaseId || null, case_title: state.activeCaseId || file.name, source_type: "upload", metadata: { size: file.size } };
      const content = await readFile(file, isText ? "text" : "dataurl");
      if (isText) payload.text = content; else payload.content_b64 = content.split(",")[1] || "";
      const data = await json("/ingest", { method: "POST", body: JSON.stringify(payload) });
      totalChunks += Number(data.result?.chunks || 0);
      if ((data.result?.archive_members_failed || []).length) {
        totalFailures += data.result.archive_members_failed.length;
      }
      fileResults.push({ file, data, status: "Indexed" });
    } catch (error) {
      totalFailures += 1;
      fileResults.push({ file, error, status: "Error" });
    }
  }
  els["upload-name"].textContent = `${files.length} item(s) ingested • ${totalChunks} chunk(s) indexed${totalFailures ? ` • ${totalFailures} warning(s)` : ""}`;
  if (els["ingest-status"]) {
    els["ingest-status"].textContent = `Active matter ${state.activeCaseId || "unassigned"} received ${files.length} new upload(s).`;
  }
  input.value = "";
  await refreshWorkspace();
  setActionPanel("file-ingest-result", totalFailures ? "error" : "success", `
    ${resultRows([
      ["Selected filename", escapeHtml(files.map((file) => file.name).join(", "))],
      ["Upload progress", "Complete"],
      ["Ingest status", escapeHtml(`${files.length} item(s), ${totalChunks} chunk(s), ${totalFailures} warning/error(s)`)],
      ["Matter", escapeHtml(state.activeCaseId || "unassigned")],
    ])}
    ${resultItems(fileResults, (item) => `
      <strong>${escapeHtml(item.file.name)}</strong>
      <div class="note">File type: ${escapeHtml(item.file.type || "application/octet-stream")} • ${escapeHtml(item.status)}</div>
      <div class="case-meta">${item.error ? escapeHtml(item.error.message || item.error) : `Record chunks: ${escapeHtml(item.data?.result?.chunks || 0)}`}</div>
    `)}
  `);
  scrollActionPanel("file-ingest-result");
}

function readFile(file, mode) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    if (mode === "text") reader.readAsText(file);
    else reader.readAsDataURL(file);
  });
}

async function runOcr() {
  const input = els["ocr-input"];
  const file = input.files?.[0];
  if (!file) {
    setActionPanel("ocr-result", "error", errorPanelMessage("Choose an image before running OCR."));
    scrollActionPanel("ocr-result");
    return;
  }
  const dataUrl = await readFile(file, "dataurl");
  const result = await json("/ocr", { method: "POST", body: JSON.stringify({ file_name: file.name, mime_type: file.type || "application/octet-stream", content_b64: dataUrl.split(",")[1] || "" }) });
  els["ocr-output"].textContent = result.text || result.message || "OCR unavailable.";
  if (result.text && els["paste-evidence"]) {
    els["paste-evidence"].value = result.text;
  }
  setActionPanel("ocr-result", result.text ? "success" : "error", resultRows([
    ["Selected filename", escapeHtml(file.name)],
    ["File type", escapeHtml(file.type || "application/octet-stream")],
    ["Extracted text status", escapeHtml(result.text ? "Text extracted and copied to paste evidence." : (result.message || "OCR unavailable"))],
    ["Characters", escapeHtml((result.text || "").length)],
  ]));
  scrollActionPanel("ocr-result");
}

async function runCorpusIngest() {
  if (!state.health?.capabilities?.local_folder_import) {
    if (els["ingest-status"]) {
      els["ingest-status"].textContent = "Folder ingest is local-desktop only in this hosted demo. Use file upload, ZIP upload, or pasted evidence.";
    }
    setActionPanel("folder-ingest-result", "error", resultRows([
      ["Status", "Coming in Pilot for hosted public demo."],
      ["Reason", "Folder ingest is local-desktop only. Use file upload, ZIP upload, or pasted evidence."],
    ]));
    scrollActionPanel("folder-ingest-result");
    return;
  }
  const path = els["corpus-path"]?.value?.trim();
  if (!path) {
    setActionPanel("folder-ingest-result", "error", errorPanelMessage("Enter an authorized local folder path first."));
    scrollActionPanel("folder-ingest-result");
    return;
  }
  const data = await json("/load_corpus", {
    method: "POST",
    body: JSON.stringify({ path, case_id: state.activeCaseId || null }),
  });
  const result = data.result || {};
  if (els["ingest-status"]) {
    els["ingest-status"].textContent = `Corpus ingest complete from ${path} • ${result.files_processed || 0}/${result.files_discovered || 0} file(s) processed • ${result.loaded_chunks || 0} chunk(s) indexed.`;
  }
  if (els["upload-name"]) {
    els["upload-name"].textContent = `${result.archives_expanded || 0} archive(s) expanded • ${Math.min((result.skipped || []).length, 50)} skipped item(s) reported.`;
  }
  await refreshWorkspace();
  setActionPanel("folder-ingest-result", "success", resultRows([
    ["Status", "Folder ingest complete."],
    ["Path", escapeHtml(path)],
    ["Files processed", escapeHtml(`${result.files_processed || 0}/${result.files_discovered || 0}`)],
    ["Chunks indexed", escapeHtml(result.loaded_chunks || 0)],
    ["Warnings", escapeHtml((result.skipped || []).length)],
  ]));
  scrollActionPanel("folder-ingest-result");
}

async function runPasteEvidence() {
  const text = els["paste-evidence"]?.value?.trim();
  if (!text) {
    setActionPanel("paste-ingest-result", "error", errorPanelMessage("Paste evidence text before ingesting."));
    scrollActionPanel("paste-ingest-result");
    return;
  }
  const title = state.activeCaseId || "pasted-evidence";
  const data = await json("/ingest", {
    method: "POST",
    body: JSON.stringify({
      text,
      file_name: `${title}.txt`,
      mime_type: "text/plain",
      case_id: state.activeCaseId || null,
      case_title: title,
      source_type: "pasted_evidence",
      metadata: { origin: "manual_paste" },
    }),
  });
  els["paste-evidence"].value = "";
  if (els["ingest-status"]) {
    els["ingest-status"].textContent = `Pasted evidence ingested into ${state.activeCaseId || "unassigned"} • ${data.result?.chunks || 0} chunk(s).`;
  }
  if (els["ingest-summary"]) {
    els["ingest-summary"].textContent = `Evidence item count updated. Source status: captured. Chronology status: ready for analysis. Next recommended action: build chronology or search the active matter.`;
  }
  await refreshWorkspace();
  setActionPanel("paste-ingest-result", "success", resultRows([
    ["Status", "Pasted evidence ingested."],
    ["File type", "text/plain"],
    ["Record IDs", escapeHtml(data.result?.record_id || data.result?.ids?.join(", ") || "Recorded by backend")],
    ["Chunks", escapeHtml(data.result?.chunks || 0)],
    ["Matter", escapeHtml(state.activeCaseId || "unassigned")],
  ]));
  scrollActionPanel("paste-ingest-result");
}

function wire() {
  document.querySelectorAll("[data-clear-result]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      clearActionPanel(button.getAttribute("data-clear-result"));
    });
  });
  document.getElementById("run-chat")?.addEventListener("click", (event) => withAction(event.currentTarget, "chat-result", "Generating grounded answer...", runChat));
  document.getElementById("run-chat-top")?.addEventListener("click", (event) => withAction(event.currentTarget, "health-result", "Generating grounded answer...", async () => {
    const data = await runChat();
    setActionPanel("health-result", data === false ? "error" : "success", resultRows([["Grounded Answer", data === false ? "Enter a question in Ask Veritas / Chat first." : "Completed. Result is visible in Ask Veritas / Chat."]]));
  }));
  document.getElementById("run-search")?.addEventListener("click", (event) => withAction(event.currentTarget, "search-result", "Searching active matter...", runSearch));
  document.getElementById("run-search-top")?.addEventListener("click", (event) => withAction(event.currentTarget, "health-result", "Searching active matter...", async () => {
    const data = await runSearch();
    setActionPanel("health-result", data === false ? "error" : "success", resultRows([["Search", data === false ? "Enter a search query first." : "Completed. Result is visible in Search."]]));
  }));
  document.getElementById("front-door-go")?.addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", "Routing request...", () => routeFrontDoorRequest(els["front-door-input"]?.value || "")));
  document.getElementById("front-door-clear")?.addEventListener("click", () => {
    if (els["front-door-input"]) els["front-door-input"].value = "";
    setFrontDoorStatus("Ready", "Type a legal task or choose a quick action.");
    setActionPanel("front-door-result", "", "No result yet.");
    els["front-door-input"]?.focus();
  });
  [
    ["front-door-new-matter", "Create a new matter."],
    ["front-door-open-matter", "Open an existing matter."],
    ["front-door-upload", "Add evidence to this matter."],
    ["front-door-search", "Search this matter."],
    ["front-door-timeline", "Build a timeline."],
    ["front-door-contradictions", "Find contradictions."],
    ["front-door-citation", "Research a citation."],
    ["front-door-draft", "Draft a report from admitted evidence."],
  ].forEach(([id, prompt]) => {
    document.getElementById(id)?.addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", "Routing request...", () => routeFrontDoorRequest(prompt)));
  });
  document.getElementById("start-matter")?.addEventListener("click", (event) => withAction(event.currentTarget, "demo-matter-result", "Opening matter creation...", async () => {
    document.getElementById("new-case")?.click();
    setActionPanel("demo-matter-result", "success", resultRows([["Start a Matter", "Matter creation opened. Complete the prompt to create a matter."]]));
  }));
  document.getElementById("load-demo-matter")?.addEventListener("click", (event) => withAction(event.currentTarget, "demo-matter-result", "Loading Harbor Point Commercial Dispute...", async () => {
    setFrontDoorStatus("Loading Demo Matter", "Loading Harbor Point Commercial Dispute through the evidence, docket, trace, and analysis pipeline.");
    const data = await json("/demo-matter", { method: "POST", body: JSON.stringify({}) });
    state.lastDemoSeed = data;
    state.activeCaseId = data.case_id || "harbor-point-commercial-dispute";
    state.analysis = data.analysis || null;
    if (els["search-input"]) {
      els["search-input"].value = "termination notice cure period expired delivery receipt";
    }
    if (els["chat-input"]) {
      els["chat-input"].value = "What evidence supports the allegation that the termination notice was sent before the cure period expired?";
    }
    await refreshWorkspace();
    renderAnalysis(data.analysis || state.analysis);
    setFrontDoorStatus("Demo Matter Loaded", "Harbor Point Commercial Dispute is loaded. Ask the sample grounded question or preview an attorney packet.");
    setActionPanel("demo-matter-result", "success", renderDemoMatterResult(data));
    scrollActionPanel("demo-matter-result");
  }));
  document.getElementById("run-ingest")?.addEventListener("click", (event) => withAction(event.currentTarget, "file-ingest-result", "Uploading and ingesting selected evidence...", ingestSelectedFile));
  document.getElementById("run-corpus")?.addEventListener("click", (event) => withAction(event.currentTarget, "folder-ingest-result", "Loading authorized evidence folder...", runCorpusIngest));
  document.getElementById("run-paste")?.addEventListener("click", (event) => withAction(event.currentTarget, "paste-ingest-result", "Ingesting pasted evidence...", runPasteEvidence));
  document.getElementById("run-ocr")?.addEventListener("click", (event) => withAction(event.currentTarget, "ocr-result", "Running OCR...", runOcr));
  els["upload-input"]?.addEventListener("change", () => {
    const files = Array.from(els["upload-input"]?.files || []);
    setActionPanel("file-ingest-result", files.length ? "success" : "", resultRows([
      ["Selected filename", escapeHtml(files.map((file) => file.name).join(", ") || "None")],
      ["File type", escapeHtml(files.map((file) => file.type || "application/octet-stream").join(", ") || "n/a")],
      ["Upload progress", files.length ? "Ready to upload." : "No result yet."],
    ]));
    scrollActionPanel("file-ingest-result");
  });
  els["ocr-input"]?.addEventListener("change", () => {
    const file = els["ocr-input"]?.files?.[0];
    setActionPanel("ocr-result", file ? "success" : "", resultRows([
      ["Selected filename", escapeHtml(file?.name || "None")],
      ["File type", escapeHtml(file?.type || "n/a")],
      ["Extracted text status", file ? "Ready for OCR." : "No result yet."],
    ]));
    scrollActionPanel("ocr-result");
  });
  els["docket-input"]?.addEventListener("change", () => {
    const file = els["docket-input"]?.files?.[0];
    setActionPanel("docket-result", file ? "success" : "", resultRows([
      ["Selected filename", escapeHtml(file?.name || "None")],
      ["File type", escapeHtml(file?.type || "text/plain")],
      ["Import status", file ? "Ready to import." : "No result yet."],
    ]));
    scrollActionPanel("docket-result");
  });
  document.getElementById("refresh-workspace")?.addEventListener("click", (event) => withAction(event.currentTarget, "health-result", "Refreshing status and workspace data...", () => refreshWorkspace({ showPanel: true })));
  document.getElementById("save-matter")?.addEventListener("click", (event) => withAction(event.currentTarget, "matter-result", "Saving matter...", saveMatter));
  document.getElementById("save-firm-profile")?.addEventListener("click", (event) => withAction(event.currentTarget, "firm-result", "Saving firm profile...", saveFirmProfile));
  document.getElementById("save-staff-member")?.addEventListener("click", (event) => withAction(event.currentTarget, "staff-result", "Saving staff member...", saveStaffMember));
  document.getElementById("save-authority-stamp")?.addEventListener("click", (event) => withAction(event.currentTarget, "authority-result", "Saving responsibility stamp...", saveAuthorityStamp));
  document.getElementById("firm-profile-select")?.addEventListener("change", () => renderFirmProfiles(state.firmProfiles));
  document.getElementById("authority-firm-profile")?.addEventListener("change", () => {
    if (state.matter) {
      state.matter.firm_profile_id = els["authority-firm-profile"].value || "";
      els["matter-status"].textContent = `${state.matter.jurisdiction || "Federal"} / ${state.matter.court_profile_id || "profile"}`;
    }
  });
  ["authority-prepared-by", "authority-reviewed-by", "authority-approved-by", "authority-signed-by", "authority-filed-by"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      if (els["authority-summary"]) {
        const current = {
          prepared_by: els["authority-prepared-by"]?.value || "Unassigned",
          reviewed_by: els["authority-reviewed-by"]?.value || "Unassigned",
          approved_by: els["authority-approved-by"]?.value || "Unassigned",
          signed_by: els["authority-signed-by"]?.value || "Unassigned",
          filed_by: els["authority-filed-by"]?.value || "Unassigned",
        };
        els["authority-summary"].textContent = [
          `Prepared by: ${current.prepared_by}`,
          `Reviewed by: ${current.reviewed_by}`,
          `Approved by: ${current.approved_by}`,
          `Signed by: ${current.signed_by}`,
          `Filed by: ${current.filed_by}`,
        ].join(" • ");
      }
    });
  });
  document.getElementById("load-court-profile")?.addEventListener("click", (event) => withAction(event.currentTarget, "matter-result", "Loading federal civil defaults...", async () => {
    if (els["court-profile-select"]) {
      els["court-profile-select"].value = "federal_district_civil";
    }
    if (els["matter-court"]) {
      els["matter-court"].value = "Federal District Court";
    }
    if (state.matter) {
      state.matter.court_profile_id = "federal_district_civil";
    }
    await saveMatter();
  }));
  document.getElementById("run-analysis")?.addEventListener("click", (event) => withAction(event.currentTarget, "matter-result", "Analyzing record...", runAnalysis));
  document.getElementById("run-draft")?.addEventListener("click", (event) => withAction(event.currentTarget, "packet-result", "Generating attorney-review packet preview...", runDraft));
  document.getElementById("find-contradictions")?.addEventListener("click", (event) => withAction(event.currentTarget, "contradictions-result", "Finding contradictions...", async () => {
    await runAnalysis();
    setActionPanel("contradictions-result", "success", renderContradictionsResultPanel(state.analysis));
  }));
  document.getElementById("export-draft")?.addEventListener("click", (event) => withAction(event.currentTarget, "export-result", "Generating export...", exportDraft));
  document.getElementById("load-court-rules")?.addEventListener("click", (event) => withAction(event.currentTarget, "court-rules-result", "Loading court rules...", loadCourtRules));
  document.getElementById("import-docket")?.addEventListener("click", (event) => withAction(event.currentTarget, "docket-result", "Importing docket...", importDocket));
  document.getElementById("build-timeline")?.addEventListener("click", (event) => withAction(event.currentTarget, "timeline-result", "Building chronology...", async () => {
    await runAnalysis();
    setActionPanel("timeline-result", "success", renderTimelineResultPanel(state.timeline || []));
    scrollActionPanel("timeline-result");
  }));
  document.getElementById("refresh-timeline")?.addEventListener("click", (event) => withAction(event.currentTarget, "timeline-result", "Refreshing chronology...", async () => {
    const data = await json("/timeline", { method: "POST", body: JSON.stringify({ case_id: state.activeCaseId || null, limit: 100 }) });
    renderTimeline(data.items || []);
    setActionPanel("timeline-result", "success", renderTimelineResultPanel(data.items || []));
    scrollActionPanel("timeline-result");
  }));
  document.getElementById("view-trace")?.addEventListener("click", (event) => withAction(event.currentTarget, "trace-result", "Loading provenance trace...", async () => {
    const traces = await fetchTraces();
    renderTraces(traces);
    setActionPanel("trace-result", "success", renderTraceResultPanel(traces));
    scrollActionPanel("trace-result");
  }));
  document.getElementById("refresh-trace")?.addEventListener("click", (event) => withAction(event.currentTarget, "trace-result", "Refreshing provenance trace...", async () => {
    const traces = await fetchTraces();
    renderTraces(traces);
    setActionPanel("trace-result", "success", renderTraceResultPanel(traces));
    scrollActionPanel("trace-result");
  }));
  document.getElementById("refresh-matters")?.addEventListener("click", (event) => withAction(event.currentTarget, "matter-selection-result", "Refreshing matters...", async () => {
    const cases = await fetchCases();
    renderCases(cases);
    setActionPanel("matter-selection-result", "success", resultRows([
      ["Status", "Matter list refreshed."],
      ["Matter count", escapeHtml(cases.length)],
      ["Selected matter", escapeHtml(state.activeCaseId || "unassigned")],
    ]));
    scrollActionPanel("matter-selection-result");
  }));
  document.getElementById("new-case")?.addEventListener("click", (event) => withAction(event.currentTarget, "matter-selection-result", "Opening new matter prompt...", async () => {
    const raw = window.prompt("New matter name or id", state.activeCaseId || "");
    if (!raw) {
      setActionPanel("matter-selection-result", "error", errorPanelMessage("New matter creation canceled."));
      return false;
    }
    state.activeCaseId = slugify(raw);
    state.analysis = null;
    els["case-filter"].textContent = state.activeCaseId;
    if (els["matter-title"]) {
      els["matter-title"].value = raw;
    }
    await saveMatter();
    setActionPanel("matter-selection-result", "success", renderMatterSelectionResult({ matter: state.matter }));
    scrollActionPanel("matter-selection-result");
  }));
  [
    ["open-ops-window", "ops"],
    ["open-investigation-window", "investigation"],
    ["open-output-window", "output"],
  ].forEach(([id, view]) => {
    document.getElementById(id)?.addEventListener("click", (event) => withAction(event.currentTarget, "health-result", `Opening ${surfaceLabel(view)}...`, async () => {
      window.open(surfaceUrl(view), "_blank", "popup=yes,width=1500,height=980");
      setActionPanel("health-result", "success", resultRows([["Surface", escapeHtml(surfaceLabel(view))], ["Status", "Window open requested. Allow popups if the browser blocks it."]]));
      scrollActionPanel("health-result");
    }));
  });
  document.getElementById("toggle-draft-panel")?.addEventListener("click", () => {
    state.draftPanelOpen = !state.draftPanelOpen;
    renderDraftPanel();
    setActionPanel("packet-result", "success", resultRows([["Draft panel", state.draftPanelOpen ? "Expanded" : "Collapsed"]]));
    scrollActionPanel("packet-result");
  });
  els["chat-mode-legal"]?.addEventListener("click", () => {
    setChatMode("legal");
    setActionPanel("chat-result", "success", resultRows([["Mode", "Legal Mode"], ["Status", "Grounded legal matter context selected."]]));
    scrollActionPanel("chat-result");
  });
  els["chat-mode-creator"]?.addEventListener("click", () => {
    const ok = setChatMode("creator");
    setActionPanel("chat-result", ok ? "success" : "error", resultRows([
      ["Mode", ok ? "Creator Mode" : "Creator Mode Locked"],
      ["Status", ok ? "Creator continuity selected." : "Enter the configured unlock phrase once in the conversation shell to unlock it."],
    ]));
    scrollActionPanel("chat-result");
  });
  els["conversation-shell"]?.addEventListener("click", (event) => {
    if (!(event.target instanceof HTMLElement)) return;
    if (event.target.closest("button, a, select, input, textarea, label")) return;
    els["chat-input"]?.focus();
  });
  els["chat-input"].addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); withAction(null, "chat-result", "Generating grounded answer...", runChat); } });
  els["search-input"].addEventListener("keydown", (event) => { if (event.key === "Enter") withAction(null, "search-result", "Searching active matter...", runSearch); });
  els["front-door-input"]?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      withAction(null, "front-door-result", "Routing request...", () => routeFrontDoorRequest(els["front-door-input"]?.value || ""));
    }
  });
  els["court-profile-select"].addEventListener("change", () => {
    if (state.matter) {
      state.matter.court_profile_id = els["court-profile-select"].value;
      els["matter-status"].textContent = `${state.matter.jurisdiction || "Federal"} / ${state.matter.court_profile_id || "profile"}`;
    }
  });
  els["draft-template-select"].addEventListener("change", () => {
    els["matter-status"].textContent = `Template: ${els["draft-template-select"].value || "motion_to_compel"}`;
  });
  els["export-format"].addEventListener("change", () => {
    els["matter-status"].textContent = `Export: ${els["export-format"].value || "markdown"}`;
  });
  els["court-rules-path"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") withAction(null, "court-rules-result", "Loading court rules...", loadCourtRules);
  });
  els["corpus-path"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") withAction(null, "folder-ingest-result", "Loading authorized evidence folder...", runCorpusIngest);
  });
  els["docket-text"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) withAction(null, "docket-result", "Importing docket...", importDocket);
  });
  els["paste-evidence"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) withAction(null, "paste-ingest-result", "Ingesting pasted evidence...", runPasteEvidence);
  });
  els["billing-increment"].addEventListener("change", () => {
    if (state.matter) state.matter.billing_increment_minutes = Number(els["billing-increment"].value || 15);
  });
  els["billing-rate"].addEventListener("change", () => {
    if (state.matter) state.matter.billing_rate = Number(els["billing-rate"].value || 0);
  });
}

async function init() {
  bind();
  state.creatorUnlocked = localStorage.getItem(CREATOR_UNLOCK_STORAGE_KEY) === "true";
  state.chatMode = normalizeChatMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY) || "legal");
  if (!state.creatorUnlocked && state.chatMode === "creator") {
    state.chatMode = "legal";
  }
  const view = new URLSearchParams(window.location.search).get("view");
  if (view && ["ops", "investigation", "output"].includes(view)) {
    state.surfaceView = view;
  }
  renderSurface();
  renderDraftPanel();
  renderChatMode();
  setFrontDoorStatus("Ready", "Type a legal task or choose a quick action.");
  wire();
  renderHealth(await json("/health"));
  renderCases(await fetchCases());
  await loadDefaultMatter();
  await refreshWorkspace();
  els["chat-input"]?.focus();
}

window.addEventListener("DOMContentLoaded", init);
(() => {
  const LICENSE_BANNER_ID = "claire-license-banner";
  const LICENSE_MODAL_ID = "claire-license-modal";

  const state = {
    license: null,
    readOnly: false,
  };

  const ensureBanner = () => {
    let banner = document.getElementById(LICENSE_BANNER_ID);
    if (banner) return banner;
    banner = document.createElement("div");
    banner.id = LICENSE_BANNER_ID;
    banner.className =
      "fixed top-0 inset-x-0 z-50 hidden items-center justify-between gap-4 border-b border-amber-500/30 bg-black/95 px-4 py-3 text-xs text-amber-100 shadow-2xl shadow-black/50 backdrop-blur";
    banner.innerHTML = `
      <div class="flex items-center gap-3">
        <span class="inline-flex h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.75)]"></span>
        <div>
          <div class="font-semibold tracking-[0.24em] uppercase">Evaluation License</div>
          <div id="claire-license-banner-copy" class="text-[11px] text-amber-100/70">Verifying local license state...</div>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button id="claire-license-activate-btn" class="rounded-full border border-amber-500/30 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100 hover:bg-amber-500/10">Activate License</button>
        <button id="claire-license-readonly-btn" class="rounded-full border border-slate-700 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-200 hover:bg-slate-800">Continue Read-Only</button>
      </div>
    `;
    document.body.appendChild(banner);
    document.body.style.paddingTop = "0px";
    return banner;
  };

  const ensureModal = () => {
    let modal = document.getElementById(LICENSE_MODAL_ID);
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = LICENSE_MODAL_ID;
    modal.className =
      "fixed inset-0 z-[60] hidden items-center justify-center bg-black/80 px-4 backdrop-blur-sm";
    modal.innerHTML = `
      <div class="w-full max-w-2xl rounded-3xl border border-rose-500/30 bg-slate-950 p-6 shadow-2xl shadow-black/70">
        <div class="mb-4 flex items-start justify-between gap-4 border-b border-white/5 pb-4">
          <div>
        <div class="text-[11px] font-semibold uppercase tracking-[0.28em] text-amber-300/80">Professional License Activation</div>
            <h3 class="mt-2 text-2xl font-semibold text-white">CLAIRE // VERITAS LEGAL</h3>
            <p class="mt-2 text-sm leading-6 text-slate-300">Evaluation access is local and offline-safe. Your evidence remains available in read-only mode if the evaluation period expires.</p>
          </div>
          <button id="claire-license-close" class="text-slate-400 hover:text-white">✕</button>
        </div>
        <label class="block text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">License Token</label>
        <textarea id="claire-license-token" rows="6" class="mt-2 w-full rounded-2xl border border-white/10 bg-black/60 p-4 text-sm text-white outline-none ring-0 placeholder:text-slate-600" placeholder="Paste your activation token here"></textarea>
        <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div class="text-xs text-slate-500">Future-ready for manual activation today, Gumroad or Stripe hooks later.</div>
          <div class="flex gap-2">
            <button id="claire-license-submit" class="rounded-full bg-amber-500 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-black hover:bg-amber-400">Activate License</button>
            <button id="claire-license-skip" class="rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white hover:bg-white/5">Continue Read-Only</button>
          </div>
        </div>
        <div id="claire-license-status" class="mt-4 rounded-2xl border border-white/5 bg-white/5 px-4 py-3 text-sm text-slate-300"></div>
      </div>
    `;
    document.body.appendChild(modal);
    return modal;
  };

  const showModal = (message) => {
    const modal = ensureModal();
    const status = modal.querySelector("#claire-license-status");
    if (status && message) status.textContent = message;
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  };

  const hideModal = () => {
    const modal = document.getElementById(LICENSE_MODAL_ID);
    if (!modal) return;
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  };

  const setReadOnly = (readOnly) => {
    state.readOnly = readOnly;
    document.body.dataset.claireReadOnly = readOnly ? "true" : "false";
  };

  const updateBanner = () => {
    const banner = ensureBanner();
    const copy = banner.querySelector("#claire-license-banner-copy");
    const activateBtn = banner.querySelector("#claire-license-activate-btn");
    const readOnlyBtn = banner.querySelector("#claire-license-readonly-btn");
    if (!state.license) {
      banner.classList.remove("hidden");
      banner.classList.add("flex");
      if (copy) copy.textContent = "Checking evaluation state...";
      return;
    }
    banner.classList.remove("hidden");
    banner.classList.add("flex");
      if (copy) {
      const hours = Math.floor((state.license.remaining_seconds || 0) / 3600);
      const mins = Math.floor(((state.license.remaining_seconds || 0) % 3600) / 60);
        copy.textContent = state.license.expired
          ? "Evaluation expired. Evidence remains available in read-only mode."
          : `Evaluation active. ${hours}h ${mins}m remaining.`;
    }
    if (activateBtn) {
      activateBtn.onclick = () => showModal("Activate your professional evaluation license to continue full workspace access.");
    }
    if (readOnlyBtn) {
      readOnlyBtn.onclick = () => {
        setReadOnly(true);
        hideModal();
      };
    }
  };

  const fetchLicense = async () => {
    try {
      const response = await fetch(apiPath("/license/status"), { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`license status ${response.status}`);
      const data = await response.json();
      state.license = data;
      setReadOnly(Boolean(data.expired) || !Boolean(data.licensed));
      updateBanner();
      if (data.expired) {
        showModal("The evaluation period has expired. Continue read-only or activate a professional license.");
      }
    } catch (error) {
      state.license = { expired: false, licensed: false, remaining_seconds: 0 };
      setReadOnly(false);
      updateBanner();
    }
  };

  const submitActivation = async () => {
    const modal = ensureModal();
    const tokenEl = modal.querySelector("#claire-license-token");
    const statusEl = modal.querySelector("#claire-license-status");
    const token = tokenEl ? tokenEl.value.trim() : "";
    if (!token) {
      if (statusEl) statusEl.textContent = "Enter a license token first.";
      return;
    }
    try {
      const response = await fetch(apiPath("/license/activate"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ token, provider: "manual" }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Activation failed");
      state.license = payload.status;
      setReadOnly(false);
      if (statusEl) statusEl.textContent = "License activated. Workspace access restored.";
      updateBanner();
      setTimeout(hideModal, 600);
    } catch (error) {
      if (statusEl) statusEl.textContent = String(error.message || error);
    }
  };

  const wireModal = () => {
    const modal = ensureModal();
    const closeBtn = modal.querySelector("#claire-license-close");
    const skipBtn = modal.querySelector("#claire-license-skip");
    const submitBtn = modal.querySelector("#claire-license-submit");
    if (closeBtn) closeBtn.onclick = hideModal;
    if (skipBtn) skipBtn.onclick = () => {
      setReadOnly(true);
      hideModal();
    };
    if (submitBtn) submitBtn.onclick = submitActivation;
    modal.addEventListener("click", (event) => {
      if (event.target === modal) hideModal();
    });
  };

  const boot = () => {
    ensureBanner();
    ensureModal();
    wireModal();
    fetchLicense();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
