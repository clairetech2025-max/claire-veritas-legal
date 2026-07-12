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
  templates: [],
  analysis: null,
  ingestActivity: [],
  surfaceView: "all",
  draftPanelOpen: true,
  chatMode: "legal",
  creatorUnlocked: false,
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
    "draft-panel",
    "toggle-draft-panel",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

async function json(url, opts = {}) {
  const res = await fetch(apiPath(url), { headers: { "Content-Type": "application/json", ...(opts.headers || {}) }, ...opts });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return await res.json();
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

function setFrontDoorStatus(status, message) {
  if (els["front-door-status"]) {
    els["front-door-status"].textContent = status;
  }
  if (els["front-door-response"]) {
    els["front-door-response"].textContent = message;
  }
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
    ? "Model Connected"
    : modelReason === "missing_server_and_model"
      ? "Model Assets Missing"
      : modelReason === "missing_server"
        ? "Model Server Missing"
        : modelReason === "missing_model"
          ? "Model File Missing"
          : "Model Offline";
  setChip(els["backend-chip"], data?.backend?.status === "online" ? "Backend Online" : "Backend Unknown", data?.backend?.status === "online" ? "ok" : "warn");
  setChip(els["health-chip"], modelLabel, data?.llm_connected ? "ok" : "warn");
  setChip(els["ocr-chip"], data?.capabilities?.ocr ? "OCR Ready" : "OCR Offline", data?.capabilities?.ocr ? "ok" : "warn");
  setChip(els["index-chip"], data?.index?.indexed ? "Index Ready" : "Index Empty", data?.index?.indexed ? "ok" : "warn");
  const licensed = Boolean(data?.license?.licensed) && !Boolean(data?.license?.expired);
  setChip(els["license-chip"], licensed ? "License Active" : "Evaluation", licensed ? "ok" : "warn");
  els["model-chip"].textContent = `${data?.model_id || "local"} @ ${data?.api_url || "n/a"}`;
  const memory = data?.memory || {};
  els["memory-metrics"].innerHTML = `
    <div class="metric-card"><span>Documents</span><strong>${memory.documents ?? 0}</strong></div>
    <div class="metric-card"><span>Cases</span><strong>${memory.cases ?? 0}</strong></div>
    <div class="metric-card"><span>Matters</span><strong>${memory.matters ?? 0}</strong></div>
    <div class="metric-card"><span>Evidence</span><strong>${memory.evidence ?? 0}</strong></div>
    <div class="metric-card"><span>Filings</span><strong>${memory.filings ?? 0}</strong></div>
    <div class="metric-card"><span>Trace</span><strong>${memory.traces ?? 0}</strong></div>
  `;
  const workflow = data?.index?.workflow || {};
  if (els["workflow-strip"]) {
    const stages = [
      ["Ingest", workflow.ingest, memory.documents ?? 0],
      ["Index", workflow.index, memory.evidence ?? 0],
      ["Query", workflow.query, memory.traces ?? 0],
      ["Trace", workflow.trace, memory.traces ?? 0],
      ["Timeline", workflow.timeline, state.timeline.length || 0],
    ];
    els["workflow-strip"].innerHTML = stages.map(([label, ready, count]) => `
      <div class="workflow-stage ${ready ? "active ready" : ""}">
        <strong>${escapeHtml(label)}</strong>
        <span>${ready ? "ready" : "pending"} • ${escapeHtml(count)}</span>
      </div>
    `).join("");
  }
  if (els["processing-summary"]) {
    const capabilities = data?.capabilities || {};
    const modelSummary = data?.llm_connected
      ? "Model: connected"
      : modelReason === "missing_server_and_model"
        ? "Model: missing llama-server.exe and GGUF model"
        : modelReason === "missing_server"
          ? "Model: missing llama-server.exe"
          : modelReason === "missing_model"
            ? "Model: missing GGUF model"
            : "Model: service offline";
    els["processing-summary"].textContent =
      `${modelSummary} • OCR: ${capabilities.ocr ? "ready" : "unavailable"} • PDF export: ${capabilities.pdf_export ? "ready" : "missing dependency"} • DOCX export: ${capabilities.docx_export ? "ready" : "missing dependency"}`;
  }
  renderGuideMe();
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
    refreshWorkspace();
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
}

function renderCitations(items) {
  state.citations = items || [];
  els["citation-list"].innerHTML = state.citations.length ? state.citations.map((item) => `
    <div class="citation-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.citation || item.source_name || "Citation")}</strong>
        <span class="timeline-pill">${escapeHtml(Number(item.final_score ?? 0).toFixed(3))}</span>
      </div>
      <div class="note">${escapeHtml(short(item.text || "", 160))}</div>
    </div>
  `).join("") : `<div class="note">No grounded citations yet.</div>`;
  renderGuideMe();
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
    els["matter-summary-left"].textContent = `${matter.title || "Unassigned matter"} • ${courtName} • ${matter.plaintiff || "Plaintiff"} v. ${matter.defendant || "Defendant"}`;
  }
  if (els["active-matter-chip"]) {
    els["active-matter-chip"].textContent = `matter: ${matter.case_id || "unassigned"}`;
  }
  if (els["billing-summary"]) {
    els["billing-summary"].textContent = `Billing increment: ${matter.billing_increment_minutes || 15} minutes • Rate: ${matter.billing_rate || 0}`;
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
}

function renderAnswer(reply, citations, context = {}) {
  state.answer = reply || "";
  if (els["answer-status"]) {
    els["answer-status"].textContent = reply ? "Grounded Answer Ready" : "Idle";
  }
  if (els["answer-sources"]) {
    const count = (citations || []).length;
    const railUsed = Boolean(context?.recognition_rail?.used);
    els["answer-sources"].textContent = railUsed
      ? `${count} source${count === 1 ? "" : "s"} • Recognition Rail`
      : `${count} source${count === 1 ? "" : "s"}`;
  }
  els["answer-panel"].innerHTML = `
    <div class="answer ${reply ? "" : "answer-empty"}">${escapeHtml(reply || "Awaiting a grounded question.")}</div>
    ${context?.recognition_rail?.used ? '<div class="mt-3 text-[11px] uppercase tracking-[0.24em] text-amber-300/70">Recognition Rail prefetch engaged</div>' : ""}
    <div class="citation-badges" style="margin-top: 14px;">
  ${(citations || []).slice(0, 6).map((item) => `<span class="badge">${escapeHtml(item.citation || item.source_name || "source")}</span>`).join("")}
    </div>
  `;
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
    return;
  }
  const data = await json("/docket/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  els["docket-status"].textContent = `Imported ${data.result?.recorded || 0} docket entries from ${sourceName}.`;
  if (input) input.value = "";
  if (els["docket-text"]) els["docket-text"].value = "";
  await refreshWorkspace();
}

function collectMatterPayload() {
  return {
    case_id: state.activeCaseId || null,
    title: els["matter-title"]?.value || state.activeCaseId || "Unassigned Matter",
    court_profile_id: els["court-profile-select"]?.value || "federal_district_civil",
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
  };
}

async function saveMatter() {
  const data = await json("/matter", { method: "POST", body: JSON.stringify(collectMatterPayload()) });
  renderMatter(data.bundle || data.matter || {});
  await refreshWorkspace();
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
  const traces = await fetchTraces();
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  els["matter-status"].textContent = "Analysis complete";
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
      throw new Error(await response.text());
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
      throw new Error(await response.text());
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
}

async function refreshWorkspace() {
  const caseId = state.activeCaseId || "";
  const searchQuery = els["search-input"].value.trim() || "legal intelligence";
  const [healthData, timeline, cases, matter, profiles, templates, traces, search, gyro] = await Promise.all([
    json("/health"),
    json("/timeline", { method: "POST", body: JSON.stringify({ case_id: caseId || null, limit: 100 }) }),
    fetchCases(),
    fetchMatter(),
    fetchCourtProfiles(),
    fetchTemplates(),
    fetchTraces(),
    json("/search", { method: "POST", body: JSON.stringify({ query: searchQuery, case_id: caseId || null, top_k: 8 }) }),
    json("/recognition-rail/debug"),
  ]);
  renderHealth(healthData);
  renderTimeline(timeline.items || []);
  renderCases(cases);
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
}

async function runChat() {
  const message = els["chat-input"].value.trim();
  if (!message) return;
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
  renderCitations(data.citations || []);
  const traces = await fetchTraces();
  renderTraces(traces);
  state.ingestActivity = traces.filter((item) => ["ingest", "docket_import", "analysis", "draft"].includes(item.event_type || ""));
  renderQueue(state.ingestActivity);
  els["chat-input"].value = "";
  els["answer-panel"]?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runSearch() {
  const query = els["search-input"].value.trim();
  if (!query) return;
  const data = await json("/search", { method: "POST", body: JSON.stringify({ query, case_id: state.activeCaseId || null, top_k: 10 }) });
  renderEvidence(data.items || []);
  renderCitations(data.items || []);
}

async function ingestSelectedFile() {
  const input = els["upload-input"];
  const files = Array.from(input.files || []);
  if (!files.length) return;
  let totalChunks = 0;
  let totalFailures = 0;
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
    } catch (error) {
      totalFailures += 1;
    }
  }
  els["upload-name"].textContent = `${files.length} item(s) ingested • ${totalChunks} chunk(s) indexed${totalFailures ? ` • ${totalFailures} warning(s)` : ""}`;
  if (els["ingest-status"]) {
    els["ingest-status"].textContent = `Active matter ${state.activeCaseId || "unassigned"} received ${files.length} new upload(s).`;
  }
  input.value = "";
  await refreshWorkspace();
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
  if (!file) return;
  const dataUrl = await readFile(file, "dataurl");
  const result = await json("/ocr", { method: "POST", body: JSON.stringify({ file_name: file.name, mime_type: file.type || "application/octet-stream", content_b64: dataUrl.split(",")[1] || "" }) });
  els["ocr-output"].textContent = result.text || result.message || "OCR unavailable.";
  if (result.text && els["paste-evidence"]) {
    els["paste-evidence"].value = result.text;
  }
}

async function runCorpusIngest() {
  const path = els["corpus-path"]?.value?.trim();
  if (!path) return;
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
}

async function runPasteEvidence() {
  const text = els["paste-evidence"]?.value?.trim();
  if (!text) return;
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
  await refreshWorkspace();
}

function wire() {
  ["run-chat", "run-chat-top"].forEach((id) => document.getElementById(id).addEventListener("click", runChat));
  ["run-search", "run-search-top"].forEach((id) => document.getElementById(id).addEventListener("click", runSearch));
  document.getElementById("front-door-go")?.addEventListener("click", () => routeFrontDoorRequest(els["front-door-input"]?.value || ""));
  document.getElementById("front-door-clear")?.addEventListener("click", () => {
    if (els["front-door-input"]) els["front-door-input"].value = "";
    setFrontDoorStatus("Ready", "Type a legal task or choose a quick action.");
    els["front-door-input"]?.focus();
  });
  document.getElementById("front-door-new-matter")?.addEventListener("click", () => routeFrontDoorRequest("Create a new matter."));
  document.getElementById("front-door-open-matter")?.addEventListener("click", () => routeFrontDoorRequest("Open an existing matter."));
  document.getElementById("front-door-upload")?.addEventListener("click", () => routeFrontDoorRequest("Add evidence to this matter."));
  document.getElementById("front-door-search")?.addEventListener("click", () => routeFrontDoorRequest("Search this matter."));
  document.getElementById("front-door-timeline")?.addEventListener("click", () => routeFrontDoorRequest("Build a timeline."));
  document.getElementById("front-door-contradictions")?.addEventListener("click", () => routeFrontDoorRequest("Find contradictions."));
  document.getElementById("front-door-citation")?.addEventListener("click", () => routeFrontDoorRequest("Research a citation."));
  document.getElementById("front-door-draft")?.addEventListener("click", () => routeFrontDoorRequest("Draft a report from admitted evidence."));
  document.getElementById("run-ingest").addEventListener("click", ingestSelectedFile);
  document.getElementById("run-corpus").addEventListener("click", runCorpusIngest);
  document.getElementById("run-paste").addEventListener("click", runPasteEvidence);
  document.getElementById("run-ocr").addEventListener("click", runOcr);
  document.getElementById("refresh-workspace").addEventListener("click", refreshWorkspace);
  document.getElementById("save-matter").addEventListener("click", saveMatter);
  document.getElementById("load-court-profile").addEventListener("click", async () => {
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
  });
  document.getElementById("run-analysis").addEventListener("click", runAnalysis);
  document.getElementById("run-draft").addEventListener("click", runDraft);
  document.getElementById("export-draft").addEventListener("click", exportDraft);
  document.getElementById("load-court-rules").addEventListener("click", loadCourtRules);
  document.getElementById("import-docket").addEventListener("click", importDocket);
  document.getElementById("new-case").addEventListener("click", async () => {
    const raw = window.prompt("New matter name or id", state.activeCaseId || "");
    if (!raw) return;
    state.activeCaseId = slugify(raw);
    state.analysis = null;
    els["case-filter"].textContent = state.activeCaseId;
    if (els["matter-title"]) {
      els["matter-title"].value = raw;
    }
    await saveMatter();
  });
  document.getElementById("open-ops-window").addEventListener("click", () => window.open(surfaceUrl("ops"), "_blank", "popup=yes,width=1500,height=980"));
  document.getElementById("open-investigation-window").addEventListener("click", () => window.open(surfaceUrl("investigation"), "_blank", "popup=yes,width=1500,height=980"));
  document.getElementById("open-output-window").addEventListener("click", () => window.open(surfaceUrl("output"), "_blank", "popup=yes,width=1500,height=980"));
  document.getElementById("toggle-draft-panel").addEventListener("click", () => {
    state.draftPanelOpen = !state.draftPanelOpen;
    renderDraftPanel();
  });
  els["chat-mode-legal"]?.addEventListener("click", () => setChatMode("legal"));
  els["chat-mode-creator"]?.addEventListener("click", () => setChatMode("creator"));
  els["conversation-shell"]?.addEventListener("click", (event) => {
    if (!(event.target instanceof HTMLElement)) return;
    if (event.target.closest("button, a, select, input, textarea, label")) return;
    els["chat-input"]?.focus();
  });
  els["chat-input"].addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); runChat(); } });
  els["search-input"].addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
  els["front-door-input"]?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      routeFrontDoorRequest(els["front-door-input"]?.value || "");
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
    if (event.key === "Enter") loadCourtRules();
  });
  els["corpus-path"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") runCorpusIngest();
  });
  els["docket-text"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) importDocket();
  });
  els["paste-evidence"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) runPasteEvidence();
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
