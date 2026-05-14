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
    <div class="metric-card"><span>Evidence</span><strong>${memory.evidence ?? 0}</strong></div>
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

async function refreshWorkspace() {
  const caseId = state.activeCaseId || "";
  renderHealth(await json("/health"));
  const timeline = await json("/timeline", { method: "POST", body: JSON.stringify({ case_id: caseId || null, limit: 100 }) });
  renderTimeline(timeline.items || []);
  const cases = await fetchCases();
  renderCases(cases);
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
  document.getElementById("new-case").addEventListener("click", async () => {
    state.activeCaseId = (els["chat-input"].value || `matter-${Date.now()}`).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    els["case-filter"].textContent = state.activeCaseId;
    await refreshWorkspace();
  });
  els["chat-input"].addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); runChat(); } });
  els["search-input"].addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
}

async function init() {
  bind();
  wire();
  renderHealth(await json("/health"));
  renderCases(await fetchCases());
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
