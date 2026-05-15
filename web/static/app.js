const state = {
  health: null,
  activeCaseId: null,
  searchResults: [],
  timeline: [],
  cases: [],
  citations: [],
  traces: [],
  answer: "",
  gyro: null,
  matter: null,
  courtProfiles: [],
  templates: [],
  analysis: null,
};

const els = {};

function bind() {
  [
    "health-chip",
    "model-chip",
    "case-list",
    "evidence-list",
    "queue-list",
    "timeline-list",
    "citation-list",
    "trace-list",
    "answer-panel",
    "memory-metrics",
    "upload-input",
    "upload-name",
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
  "billing-increment",
  "billing-rate",
    "matter-status",
    "matter-summary-left",
    "billing-summary",
    "analysis-list",
  "court-profile-list",
    "court-profile-report",
    "court-rules-status",
    "template-list",
    "theory-output",
    "anomaly-list",
    "filing-list",
    "draft-output",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

async function json(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json", ...(opts.headers || {}) }, ...opts });
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

function renderHealth(data) {
  state.health = data;
  const ok = data?.llm_connected ? "ok" : "warn";
  els["health-chip"].className = `status-chip ${ok}`;
  els["health-chip"].textContent = data?.llm_connected ? "Model Connected" : "Model Offline";
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
        <strong>${index + 1}. ${escapeHtml(item.title || item.source_name || "Matter")}</strong>
        <span class="timeline-pill">${escapeHtml(item.source_type || "record")}</span>
      </div>
      <div class="note">${escapeHtml(short(item.text, 160))}</div>
    </div>
  `).join("") : `<div class="note">Discovery queue is empty.</div>`;
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
}

function renderTraces(items) {
  state.traces = items || [];
  els["trace-list"].innerHTML = state.traces.length ? state.traces.map((item) => `
    <div class="trace-item">
      <div class="stack-row">
        <strong>${escapeHtml(item.event_type || "trace")}</strong>
        <span class="timeline-pill">${escapeHtml(fmtTime(item.timestamp))}</span>
      </div>
      <div class="note">${escapeHtml(short(item.summary || "", 180))}</div>
    </div>
  `).join("") : `<div class="note">Trace panel is idle.</div>`;
}

function renderGyro(data) {
  state.gyro = data;
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
  `).join("") : `<div class="note">No gyro items yet.</div>`;
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
  if (els["billing-summary"]) {
    els["billing-summary"].textContent = `Billing increment: ${matter.billing_increment_minutes || 15} minutes • Rate: ${matter.billing_rate || 0}`;
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
      `Estimated Hours: ${billing.estimated_hours ?? "n/a"}`,
      `Estimated Value: ${billing.estimated_value ?? "n/a"}`,
      "",
      sections.length ? sections.join("\n\n---\n\n") : "No draft packet yet.",
    ].join("\n");
  }
  if (els["billing-summary"]) {
    els["billing-summary"].textContent = `Estimated ${billing.estimated_hours ?? 0} hours • $${billing.estimated_value ?? 0} value • ${billing.increment_minutes ?? 15}-minute increment`;
  }
}

function renderAnswer(reply, citations) {
  state.answer = reply || "";
  els["answer-panel"].innerHTML = `
    <div class="answer">${escapeHtml(reply || "Awaiting a grounded question.")}</div>
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
  renderTraces([...(data.timeline || []), ...(state.traces || [])].slice(0, 12));
  renderCitations(data.records || []);
  renderEvidence(data.records || []);
  renderQueue(data.records || []);
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
  renderTraces((data.packet && data.packet.timeline) ? data.packet.timeline : state.traces);
  els["draft-output"].textContent = data.draft_text || "Draft generated.";
}

async function exportDraft() {
  const templateId = els["draft-template-select"]?.value || "motion_to_compel";
  const query = els["chat-input"].value.trim() || els["search-input"].value.trim() || "discovery dispute";
  const data = await json("/export_packet", {
    method: "POST",
    body: JSON.stringify({ template_id: templateId, case_id: state.activeCaseId || null, query, format: "markdown" }),
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
  renderHealth(await json("/health"));
  const timeline = await json("/timeline", { method: "POST", body: JSON.stringify({ case_id: caseId || null, limit: 100 }) });
  renderTimeline(timeline.items || []);
  const cases = await fetchCases();
  renderCases(cases);
  const matter = await fetchMatter();
  renderMatter(matter);
  const profiles = await fetchCourtProfiles();
  renderCourtProfiles(profiles);
  const templates = await fetchTemplates();
  renderTemplates(templates);
  renderCourtProfileReport((matter && matter.court_profile_report) || state.matter?.court_profile_report || null);
  els["case-filter"].textContent = caseId || "all matters";
  const searchQuery = els["search-input"].value.trim() || "legal intelligence";
  const search = await json("/search", { method: "POST", body: JSON.stringify({ query: searchQuery, case_id: caseId || null, top_k: 8 }) });
  const items = search.items || [];
  renderEvidence(items);
  renderQueue(items);
  renderCitations(items);
  renderTraces(timeline.items || []);
  const gyro = await json("/gyro_debug");
  renderGyro(gyro);
  if (!state.analysis) {
    renderAnalysis(await json("/analyze", { method: "POST", body: JSON.stringify({ query: searchQuery, case_id: caseId || null, top_k: 8 }) }));
  }
}

async function runChat() {
  const message = els["chat-input"].value.trim();
  if (!message) return;
  els["answer-panel"].innerHTML = `<div class="note">Thinking against grounded material...</div>`;
  const data = await json("/chat", {
    method: "POST",
    body: JSON.stringify({ message, case_id: state.activeCaseId || null, top_k: 8, temperature: 0.2, max_tokens: 700 }),
  });
  renderAnswer(data.reply, data.citations || []);
  renderCitations(data.citations || []);
  renderTraces((data.case_context && data.case_context.timeline) || []);
  renderGyro(data.gyro || null);
  els["chat-input"].value = "";
}

async function runSearch() {
  const query = els["search-input"].value.trim();
  if (!query) return;
  const data = await json("/search", { method: "POST", body: JSON.stringify({ query, case_id: state.activeCaseId || null, top_k: 10 }) });
  renderEvidence(data.items || []);
  renderQueue(data.items || []);
  renderCitations(data.items || []);
}

async function ingestSelectedFile() {
  const input = els["upload-input"];
  const file = input.files?.[0];
  if (!file) return;
  const isText = /\.(txt|md|csv|json|log|html?|xml|yml|yaml)$/i.test(file.name) || (file.type || "").startsWith("text/");
  const payload = { file_name: file.name, mime_type: file.type || "application/octet-stream", case_id: state.activeCaseId || null, case_title: state.activeCaseId || file.name, source_type: "upload", metadata: { size: file.size } };
  const content = await readFile(file, isText ? "text" : "dataurl");
  if (isText) payload.text = content; else payload.content_b64 = content.split(",")[1] || "";
  const data = await json("/ingest", { method: "POST", body: JSON.stringify(payload) });
  els["upload-name"].textContent = `${file.name} ingested (${data.result?.chunks || 0} chunks)`;
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
}

function wire() {
  ["run-chat", "run-chat-top"].forEach((id) => document.getElementById(id).addEventListener("click", runChat));
  ["run-search", "run-search-top"].forEach((id) => document.getElementById(id).addEventListener("click", runSearch));
  document.getElementById("run-ingest").addEventListener("click", ingestSelectedFile);
  document.getElementById("run-ocr").addEventListener("click", runOcr);
  document.getElementById("refresh-workspace").addEventListener("click", refreshWorkspace);
  document.getElementById("save-matter").addEventListener("click", saveMatter);
  document.getElementById("load-court-profile").addEventListener("click", async () => {
    const bundle = await fetchMatter();
    renderMatter(bundle);
  });
  document.getElementById("run-analysis").addEventListener("click", runAnalysis);
  document.getElementById("run-draft").addEventListener("click", runDraft);
  document.getElementById("export-draft").addEventListener("click", exportDraft);
  document.getElementById("load-court-rules").addEventListener("click", loadCourtRules);
  document.getElementById("new-case").addEventListener("click", async () => {
    state.activeCaseId = (els["chat-input"].value || `matter-${Date.now()}`).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    els["case-filter"].textContent = state.activeCaseId;
    await refreshWorkspace();
  });
  els["chat-input"].addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); runChat(); } });
  els["search-input"].addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
  els["court-profile-select"].addEventListener("change", () => {
    if (state.matter) {
      state.matter.court_profile_id = els["court-profile-select"].value;
      els["matter-status"].textContent = `${state.matter.jurisdiction || "Federal"} / ${state.matter.court_profile_id || "profile"}`;
    }
  });
  els["draft-template-select"].addEventListener("change", () => {
    els["matter-status"].textContent = `Template: ${els["draft-template-select"].value || "motion_to_compel"}`;
  });
  els["court-rules-path"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadCourtRules();
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
  wire();
  renderHealth(await json("/health"));
  renderCases(await fetchCases());
  await loadDefaultMatter();
  await refreshWorkspace();
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
      const response = await fetch("/license/status", { headers: { Accept: "application/json" } });
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
      const response = await fetch("/license/activate", {
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
