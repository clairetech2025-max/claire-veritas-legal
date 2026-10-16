const state = {
  cases: [],
  activeCase: null,
  draft: {},
  step: 0,
  mode: "essential",
};

const STORAGE_KEY = "veritas-guided-last-case-id";
const API_BASE = "";

const essentialQuestions = [
  { key: "title", label: "Case title", question: "What should this case be called?", help: "Use a short working title.", required: true },
  { key: "case_number", label: "Case number", question: "What is the case number?", help: "Use the assigned number, or mark Not assigned yet.", required: true, allowNotAssigned: true },
  { key: "court_name", label: "Court or forum", question: "Which court or forum is handling it?", help: "Example: United States District Court.", required: true },
  { key: "jurisdiction", label: "Jurisdiction", question: "What jurisdiction governs it?", help: "Example: Federal, California, administrative, arbitration.", required: true },
  { key: "matter_type", label: "Case type", question: "What type of case is it?", help: "Example: civil, appeal, administrative, arbitration.", required: true },
  { key: "plaintiff", label: "Primary plaintiff or petitioner", question: "Who is the primary plaintiff or petitioner?", help: "Do not add extra parties yet.", required: true },
  { key: "defendant", label: "Primary defendant or respondent", question: "Who is the primary defendant or respondent?", help: "Do not add extra parties yet.", required: true },
  { key: "current_status", label: "Current status", question: "What is its current status?", help: "Example: intake, active, pending filing, discovery, appeal.", required: true },
];

const optionalQuestions = [
  { key: "filing_date", label: "Filing date", question: "What is the filing date?", help: "Skip if unknown.", optional: true },
  { key: "additional_parties", label: "Additional parties", question: "Are there additional parties?", help: "List names and roles, or skip.", optional: true },
  { key: "judge", label: "Judge", question: "Which judge or decision-maker is assigned?", help: "Skip if not assigned.", optional: true },
  { key: "counsel", label: "Counsel", question: "Who is counsel of record?", help: "List known counsel or skip.", optional: true },
  { key: "agencies", label: "Agencies", question: "Are any agencies involved?", help: "Skip if none.", optional: true },
  { key: "related_case_numbers", label: "Related case numbers", question: "Are there related case numbers?", help: "Skip if none.", optional: true },
  { key: "appeal_number", label: "Appeal number", question: "Is there an appeal number?", help: "Skip if none.", optional: true },
  { key: "administrative_number", label: "Administrative number", question: "Is there an administrative number?", help: "Skip if none.", optional: true },
  { key: "deadlines", label: "Deadlines", question: "What deadlines are known?", help: "Skip if none.", optional: true },
  { key: "description", label: "Description", question: "Briefly describe the case.", help: "One or two sentences is enough.", optional: true },
  { key: "desired_outcome", label: "Desired outcome", question: "What outcome are you working toward?", help: "Skip if undecided.", optional: true },
  { key: "confidentiality_level", label: "Confidentiality", question: "What confidentiality level applies?", help: "Example: Privileged, confidential, public demo.", optional: true },
  { key: "tags", label: "Tags", question: "Add any useful tags.", help: "Separate tags with commas, or skip.", optional: true },
];

const els = {};

function bind() {
  [
    "entry-screen", "entry-copy", "resume-last-case", "choose-another-case", "create-new-case",
    "open-existing-case", "entry-result", "case-picker", "intake-screen", "intake-heading",
    "intake-step", "live-preview", "active-question", "question-help", "guided-answer",
    "not-assigned-row", "not-assigned-check", "intake-back", "intake-skip", "intake-continue",
    "intake-result", "review-screen", "review-list", "review-back", "continue-details",
    "create-case-final", "review-result", "active-screen", "active-title", "active-summary",
    "active-status", "active-add-documents", "active-edit-case", "active-change-case",
    "active-ask-veritas", "active-review-evidence", "active-view-timeline",
    "active-view-contradictions", "active-view-parties", "active-view-financials",
    "active-view-filings", "active-build-report", "active-result",
    "front-door-input", "front-door-go", "front-door-clear", "front-door-new-matter",
    "front-door-open-matter", "front-door-upload", "front-door-search", "front-door-timeline",
    "front-door-contradictions", "front-door-citation", "front-door-draft",
    "front-door-status", "front-door-response", "front-door-result",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

function apiPath(url) {
  return typeof url === "string" && url.startsWith("/") ? `${API_BASE}${url}` : url;
}

async function json(url, opts = {}) {
  const res = await fetch(apiPath(url), { headers: { "Content-Type": "application/json", ...(opts.headers || {}) }, ...opts });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail?.message || body.detail || body.message || "";
    } catch {
      detail = await res.text();
    }
    throw new Error(String(detail || `Request failed (${res.status})`).replace(/\s+/g, " ").trim());
  }
  return await res.json();
}

function escapeHtml(text) {
  return String(text ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function slugify(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || `case-${Date.now()}`;
}

function showOnly(screenId) {
  ["entry-screen", "intake-screen", "review-screen", "active-screen"].forEach((id) => {
    if (els[id]) els[id].hidden = id !== screenId;
  });
}

function setActionPanel(panelId, status, html) {
  const panel = els[panelId] || document.getElementById(panelId);
  if (!panel) return;
  panel.classList.remove("loading", "success", "error");
  if (status) panel.classList.add(status);
  const body = panel.querySelector(".action-result-body") || panel;
  body.innerHTML = html || "No result yet.";
}

function clearActionPanel(panelId) {
  setActionPanel(panelId, "", "No result yet.");
}

function scrollActionPanel(panelId) {
  const panel = els[panelId] || document.getElementById(panelId);
  if (panel && window.matchMedia("(max-width: 700px)").matches) {
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

async function withAction(buttonOrId, panelId, loadingMessage, action) {
  const button = typeof buttonOrId === "string" ? document.getElementById(buttonOrId) : buttonOrId;
  if (button?.disabled) return null;
  if (button) {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  }
  setActionPanel(panelId, "loading", `<div class="note">${escapeHtml(loadingMessage)}</div>`);
  scrollActionPanel(panelId);
  try {
    return await action();
  } catch (error) {
    setActionPanel(panelId, "error", `<div class="note">${escapeHtml(error.message || error)}</div>`);
    scrollActionPanel(panelId);
    return null;
  } finally {
    if (button) {
      button.disabled = false;
      button.setAttribute("aria-busy", "false");
    }
  }
}

async function guidedStateAction(buttonOrId, panelId, loadingMessage, successHtml, action) {
  return withAction(buttonOrId, panelId, loadingMessage, async () => {
    const result = await action();
    if (successHtml) {
      setActionPanel(panelId, "success", typeof successHtml === "function" ? successHtml(result) : successHtml);
      scrollActionPanel(panelId);
    }
    return result;
  });
}

function currentQuestions() {
  return state.mode === "optional" ? optionalQuestions : essentialQuestions;
}

function currentQuestion() {
  return currentQuestions()[state.step];
}

function sourceTag(value) {
  if (!value) return "Needs review";
  return "User entered";
}

function previewFields({ includeOptional = state.mode === "optional", includeAll = false } = {}) {
  const fields = essentialQuestions.slice();
  optionalQuestions.forEach((item) => {
    if (includeAll || includeOptional || state.draft[item.key]) {
      fields.push(item);
    }
  });
  return fields;
}

function renderPreview(target = els["live-preview"], { includeEdit = false } = {}) {
  const fields = previewFields({ includeAll: includeEdit, includeOptional: state.mode === "optional" });
  target.innerHTML = fields.length ? fields.map((item) => {
    const value = state.draft[item.key] || "";
    return `
    <div class="guided-preview-item">
      <strong>${escapeHtml(item.label)}</strong>
      <div class="note">${escapeHtml(value || "Not answered yet.")}</div>
      <span class="guided-source-tag">${sourceTag(value)}</span>
      ${includeEdit ? `<button class="button mini guided-edit-field" data-edit-field="${escapeHtml(item.key)}" type="button">Edit Field</button>` : ""}
    </div>
  `;
  }).join("") : `<div class="note">The case record will build here as answers are entered.</div>`;
}

function renderQuestion() {
  const q = currentQuestion();
  if (!q) {
    renderReview();
    return;
  }
  showOnly("intake-screen");
  renderPreview();
  els["intake-heading"].textContent = state.mode === "optional" ? "Optional Case Details" : "Essential Case Details";
  els["intake-step"].textContent = state.mode === "optional"
    ? `Optional ${state.step + 1} / ${optionalQuestions.length}`
    : `Step ${state.step + 1} / ${essentialQuestions.length}`;
  els["active-question"].textContent = q.question;
  els["question-help"].textContent = q.help || "";
  els["guided-answer"].value = state.draft[q.key] || "";
  els["not-assigned-row"].hidden = !q.allowNotAssigned;
  els["not-assigned-check"].checked = q.allowNotAssigned && String(state.draft[q.key] || "").toLowerCase() === "not assigned yet";
  els["intake-skip"].hidden = !q.optional;
  setActionPanel("intake-result", "", "No result yet.");
  setTimeout(() => els["guided-answer"]?.focus(), 40);
}

function retainCurrentAnswer({ skip = false } = {}) {
  const q = currentQuestion();
  if (!q) return true;
  let value = skip ? "" : els["guided-answer"].value.trim();
  if (q.allowNotAssigned && els["not-assigned-check"].checked) {
    value = "Not assigned yet";
  }
  if (q.required && !value) {
    setActionPanel("intake-result", "error", `<div class="note">${escapeHtml(`${q.label} is required.`)}</div>`);
    scrollActionPanel("intake-result");
    return false;
  }
  if (value) state.draft[q.key] = value;
  else delete state.draft[q.key];
  renderPreview();
  setActionPanel("intake-result", "success", resultRows([
    ["Saved temporarily", escapeHtml(q.label)],
    ["Source", "User entered"],
  ]));
  return true;
}

function nextQuestion() {
  if (!retainCurrentAnswer()) return;
  const questions = currentQuestions();
  if (state.step < questions.length - 1) {
    state.step += 1;
    renderQuestion();
    return;
  }
  renderReview();
}

function backQuestion() {
  if (state.step > 0) {
    state.step -= 1;
    renderQuestion();
    return;
  }
  if (state.mode === "optional") {
    state.mode = "essential";
    state.step = essentialQuestions.length - 1;
    renderQuestion();
    return;
  }
  showEntry();
}

function skipQuestion() {
  if (!currentQuestion()?.optional) return;
  retainCurrentAnswer({ skip: true });
  if (state.step < optionalQuestions.length - 1) {
    state.step += 1;
    renderQuestion();
  } else {
    renderReview();
  }
}

function renderReview() {
  showOnly("review-screen");
  renderPreview(els["review-list"], { includeEdit: true });
  els["review-list"].querySelectorAll("[data-edit-field]").forEach((button) => {
    button.addEventListener("click", () => editField(button.getAttribute("data-edit-field")));
  });
  setActionPanel("review-result", "success", resultRows([
    ["Status", "The case is ready to create."],
    ["Permanent record", "Not created yet"],
  ]));
  scrollActionPanel("review-result");
}

function editField(key) {
  const essentialIndex = essentialQuestions.findIndex((item) => item.key === key);
  if (essentialIndex >= 0) {
    state.mode = "essential";
    state.step = essentialIndex;
  } else {
    state.mode = "optional";
    state.step = Math.max(0, optionalQuestions.findIndex((item) => item.key === key));
  }
  renderQuestion();
}

function buildMatterPayload() {
  const title = state.draft.title || "Untitled Case";
  const caseNumber = state.draft.case_number || "";
  const assignedNumber = caseNumber && caseNumber.toLowerCase() !== "not assigned yet";
  const caseId = assignedNumber ? slugify(caseNumber) : slugify(title);
  const optionalLines = optionalQuestions
    .filter((item) => state.draft[item.key] && !["counsel", "confidentiality_level"].includes(item.key))
    .map((item) => `${item.label}: ${state.draft[item.key]}`);
  return {
    case_id: caseId,
    create: true,
    case_number: caseNumber,
    title,
    court_name: state.draft.court_name || "",
    jurisdiction: state.draft.jurisdiction || "",
    matter_type: state.draft.matter_type || "",
    practice_area: state.draft.matter_type || "Litigation",
    plaintiff: state.draft.plaintiff || "",
    defendant: state.draft.defendant || "",
    current_status: state.draft.current_status || "Active",
    counsel: state.draft.counsel || "",
    confidentiality_level: state.draft.confidentiality_level || "Privileged",
    notes: optionalLines.join("\n"),
  };
}

async function createCase() {
  const payload = buildMatterPayload();
  const data = await json("/matter", { method: "POST", body: JSON.stringify(payload) });
  state.activeCase = data.matter || payload;
  localStorage.setItem(STORAGE_KEY, state.activeCase.case_id);
  await loadCases();
  renderActiveCase(state.activeCase);
  setActionPanel("active-result", "success", resultRows([
    ["Created case", escapeHtml(state.activeCase.title || state.activeCase.case_id)],
    ["Case number", escapeHtml(state.activeCase.case_number || "Not assigned yet")],
    ["Status", escapeHtml(state.activeCase.current_status || "Active")],
  ]));
  scrollActionPanel("active-result");
}

function renderActiveCase(matter) {
  state.activeCase = matter;
  showOnly("active-screen");
  els["active-title"].textContent = matter.title || matter.case_id || "Active Case";
  els["active-summary"].textContent = [
    matter.case_number || "Not assigned yet",
    matter.court_name || "Court/forum pending",
    matter.jurisdiction || "",
  ].filter(Boolean).join(" | ");
  els["active-status"].textContent = matter.current_status || matter.status || "Active";
}

async function resumeCase(caseId) {
  const data = await json(`/matter?case_id=${encodeURIComponent(caseId)}`);
  const matter = data.matter || {};
  localStorage.setItem(STORAGE_KEY, matter.case_id || caseId);
  renderActiveCase(matter);
  setActionPanel("active-result", "success", resultRows([
    ["Resumed case", escapeHtml(matter.title || matter.case_id || caseId)],
    ["Case number", escapeHtml(matter.case_number || "Not assigned yet")],
    ["Status", escapeHtml(matter.current_status || matter.status || "Active")],
  ]));
}

function showCasePicker() {
  els["case-picker"].hidden = false;
  els["case-picker"].innerHTML = state.cases.length ? state.cases.map((item) => `
    <button class="button guided-case-choice" type="button" data-case-id="${escapeHtml(item.case_id)}">
      <strong>${escapeHtml(item.title || item.case_id)}</strong>
      <div class="note">${escapeHtml(item.case_id)} | ${escapeHtml(item.status || "active")}</div>
    </button>
  `).join("") : `<div class="note">No existing cases found.</div>`;
  els["case-picker"].querySelectorAll("[data-case-id]").forEach((button) => {
    button.addEventListener("click", () => withAction(button, "entry-result", "Opening selected case...", () => resumeCase(button.getAttribute("data-case-id"))));
  });
  setActionPanel("entry-result", "success", resultRows([
    ["Existing cases", escapeHtml(state.cases.length)],
    ["Action", "Choose a case below."],
  ]));
}

function startNewCase() {
  state.draft = {};
  state.step = 0;
  state.mode = "essential";
  renderQuestion();
}

function showEntry() {
  showOnly("entry-screen");
  const lastCaseId = localStorage.getItem(STORAGE_KEY);
  const lastCase = state.cases.find((item) => item.case_id === lastCaseId) || state.cases[0] || null;
  els["case-picker"].hidden = true;
  if (lastCase) {
    els["entry-copy"].textContent = `Last case available: ${lastCase.title || lastCase.case_id}`;
    els["resume-last-case"].hidden = false;
    els["choose-another-case"].hidden = state.cases.length < 2;
    els["open-existing-case"].hidden = true;
    els["resume-last-case"].dataset.caseId = lastCase.case_id;
  } else {
    els["entry-copy"].textContent = "No prior case found. Create a new case or open an existing case.";
    els["resume-last-case"].hidden = true;
    els["choose-another-case"].hidden = true;
    els["open-existing-case"].hidden = false;
  }
  setActionPanel("entry-result", "", "No result yet.");
}

async function loadCases() {
  const data = await json("/cases");
  state.cases = data.items || [];
}

function activeToolMessage(label) {
  const isDocumentStep = label === "Add Documents";
  setActionPanel("active-result", "success", resultRows([
    ["Tool", escapeHtml(label)],
    ["Active case", escapeHtml(state.activeCase?.title || state.activeCase?.case_id || "Current case")],
    ["Status", isDocumentStep
      ? "Document workflow is the next milestone. No upload was started."
      : "This active-case tool is reserved for a later milestone. No action was run."],
  ]));
  scrollActionPanel("active-result");
}

function setFrontDoorMessage(label, detail, href = "") {
  const link = href ? `<a class="button mini" href="${href}">Open Tool</a>` : "";
  setActionPanel("front-door-result", "success", resultRows([
    ["Workflow stage", escapeHtml(label)],
    ["Next step", `${escapeHtml(detail)} ${link}`],
  ]));
  if (els["front-door-response"]) {
    els["front-door-response"].textContent = detail;
  }
  if (els["front-door-status"]) {
    els["front-door-status"].textContent = label;
  }
  scrollActionPanel("front-door-result");
}

// Where a question points in the workflow, if anywhere: [label, href] or null.
function workflowDestination(value) {
  if (/\b(upload|add (?:evidence|documents?)|attach)\b/.test(value)) return ["Upload Evidence", "/dashboard#ingest-summary"];
  if (/\b(timeline|chronology)\b/.test(value)) return ["Chronology", "/dashboard#timeline-result"];
  if (/\b(contradictions?|conflicts?|issues)\b/.test(value)) return ["Issues", "/dashboard#contradictions-result"];
  if (/\b(research|case law|citations?)\b/.test(value)) return ["Legal Research", "/dashboard#citation-list"];
  if (/\b(draft|packet|report|memo|export)\b/.test(value)) return ["Draft Report", "/dashboard#draft-panel"];
  return null;
}

function answerHtml(reply) {
  let text = String(reply || "").trim();
  let notice = "";
  const record = text.match(/^\[record answer\]\s*/);
  const stub = text.match(/^\[deterministic legal stub:[^\]]*\]\s*/);
  if (record) {
    text = text.slice(record[0].length);
    notice = `<div class="claire-answer-notice">Answered straight from the record: every line below is quoted from a cited document or computed by Veritas. No AI wrote it.</div>`;
  } else if (stub) {
    text = text.slice(stub[0].length);
    notice = `<div class="claire-answer-notice">Claire's reasoning model is not connected on this site yet, so this is a limited answer drawn only from the record.</div>`;
  }
  const blocks = escapeHtml(text).replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>").split(/\n{2,}/);
  const body = blocks.map((block) => {
    const lines = block.split("\n");
    if (lines.every((line) => /^\s*[-*•]\s+/.test(line))) {
      return `<ul>${lines.map((line) => `<li>${line.replace(/^\s*[-*•]\s+/, "")}</li>`).join("")}</ul>`;
    }
    return `<p>${lines.join("<br>")}</p>`;
  }).join("");
  return notice + `<div class="claire-answer-text">${body || "<p>No answer was returned.</p>"}</div>`;
}

async function askClaire() {
  const question = (els["front-door-input"]?.value || "").trim();
  if (!question) {
    setActionPanel("front-door-result", "error", `<div class="note">Type a question first, then select Ask Claire.</div>`);
    els["front-door-input"]?.focus();
    return;
  }
  // A first-time visitor has no matter open yet: answer from the most recent one (the sample matter on the demo site).
  const fallbackCase = state.cases.find((item) => item.case_id === localStorage.getItem(STORAGE_KEY)) || state.cases[0] || null;
  const caseId = state.activeCase?.case_id || fallbackCase?.case_id || null;
  const caseTitle = state.activeCase?.title || fallbackCase?.title || caseId;
  const data = await json("/chat", { method: "POST", body: JSON.stringify({ message: question, case_id: caseId, mode: "legal" }) });
  const sources = [...new Set((data.citations || []).map((item) => item.source_name || item.citation).filter(Boolean))].slice(0, 6);
  const destination = workflowDestination(question.toLowerCase());
  const scope = caseId ? `Answered from the record of: ${escapeHtml(caseTitle)}` : "No matter is open, so this answer is not based on a case record.";
  setActionPanel("front-door-result", "success", `
    <div class="claire-answer-question">You asked: ${escapeHtml(question)}</div>
    ${answerHtml(data.reply)}
    ${sources.length ? `<div class="claire-answer-sources"><strong>Sources:</strong> ${sources.map(escapeHtml).join("; ")}</div>` : ""}
    <div class="note">${scope}</div>
    ${destination ? `<a class="button mini" href="${destination[1]}">Go to ${escapeHtml(destination[0])}</a>` : ""}
  `);
  els["front-door-result"]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function routeFrontDoorIntent() {
  const value = (els["front-door-input"]?.value || "").toLowerCase();
  if (!value.trim()) {
    setFrontDoorMessage("Ready", "Tell Claire the legal task: add evidence, build timeline, research, or draft packet.");
    return;
  }
  if (value.includes("evidence") || value.includes("upload") || value.includes("document")) {
    setFrontDoorMessage("Evidence Intake", "Open the evidence intake tools in the advanced dashboard.", "/dashboard#ingest-summary");
  } else if (value.includes("timeline") || value.includes("chronology")) {
    setFrontDoorMessage("Timeline", "Open the chronology view for the active matter.", "/dashboard#timeline-result");
  } else if (value.includes("contradiction") || value.includes("conflict") || value.includes("issue")) {
    setFrontDoorMessage("Issues", "Open issue and contradiction review for attorney analysis.", "/dashboard#contradictions-result");
  } else if (value.includes("research") || value.includes("citation") || value.includes("case law")) {
    setFrontDoorMessage("Research", "Open legal research and citation tools.", "/dashboard#citation-list");
  } else if (value.includes("draft") || value.includes("packet") || value.includes("report") || value.includes("export")) {
    setFrontDoorMessage("Packet", "Open the attorney-review packet and export tools.", "/dashboard#draft-panel");
  } else {
    setFrontDoorMessage("Matter Setup", "Start by creating or opening the active matter record.");
    showEntry();
  }
}

function wire() {
  document.querySelectorAll("[data-clear-result]").forEach((button) => {
    button.addEventListener("click", () => clearActionPanel(button.getAttribute("data-clear-result")));
  });
  els["front-door-go"].addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", "Claire is reading the record and preparing an answer...", askClaire));
  // Enter asks; Shift+Enter starts a new line.
  els["front-door-input"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      els["front-door-go"].click();
    }
  });
  els["front-door-clear"].addEventListener("click", () => {
    els["front-door-input"].value = "";
    clearActionPanel("front-door-result");
  });
  els["front-door-new-matter"].addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", "Starting matter setup...", async () => {
    startNewCase();
    setFrontDoorMessage("Matter Setup", "Answer the intake questions below to create the matter record.");
  }));
  els["front-door-open-matter"].addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", "Loading matters...", async () => {
    showEntry();
    showCasePicker();
    setFrontDoorMessage("Matter Setup", "Choose an existing matter below.");
  }));
  [
    ["front-door-upload", "Evidence Intake", "Open upload, paste, OCR, and folder ingest tools.", "/dashboard#ingest-summary"],
    ["front-door-search", "Source Review", "Open grounded source search for the active matter.", "/dashboard#search-result"],
    ["front-door-timeline", "Timeline", "Open chronology reconstructed from evidence and filings.", "/dashboard#timeline-result"],
    ["front-door-contradictions", "Issues", "Open issue and contradiction review.", "/dashboard#contradictions-result"],
    ["front-door-citation", "Research", "Open public legal research and citation tools.", "/dashboard#citation-list"],
    ["front-door-draft", "Packet", "Open attorney-review packet drafting.", "/dashboard#draft-panel"],
  ].forEach(([id, label, detail, href]) => {
    els[id].addEventListener("click", (event) => withAction(event.currentTarget, "front-door-result", `Opening ${label}...`, async () => setFrontDoorMessage(label, detail, href)));
  });
  els["resume-last-case"].addEventListener("click", (event) => withAction(event.currentTarget, "entry-result", "Resuming last case...", () => resumeCase(event.currentTarget.dataset.caseId)));
  els["choose-another-case"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "entry-result", "Loading case choices...", null, async () => showCasePicker()));
  els["open-existing-case"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "entry-result", "Loading case choices...", null, async () => showCasePicker()));
  els["create-new-case"].addEventListener("click", (event) => withAction(event.currentTarget, "entry-result", "Starting guided intake...", async () => startNewCase()));
  els["intake-continue"].addEventListener("click", (event) => withAction(event.currentTarget, "intake-result", "Saving answer...", async () => nextQuestion()));
  els["intake-back"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "intake-result", "Restoring previous answer...", null, async () => backQuestion()));
  els["intake-skip"].addEventListener("click", (event) => withAction(event.currentTarget, "intake-result", "Skipping optional field...", async () => skipQuestion()));
  els["guided-answer"].addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      withAction(null, "intake-result", "Saving answer...", async () => nextQuestion());
    }
  });
  els["not-assigned-check"].addEventListener("change", () => {
    if (els["not-assigned-check"].checked) {
      els["guided-answer"].value = "Not assigned yet";
    }
  });
  els["review-back"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "review-result", "Returning to intake...", null, async () => {
    state.mode = "essential";
    state.step = essentialQuestions.length - 1;
    renderQuestion();
  }));
  els["continue-details"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "review-result", "Opening optional details...", null, async () => {
    state.mode = "optional";
    state.step = 0;
    renderQuestion();
  }));
  els["create-case-final"].addEventListener("click", (event) => withAction(event.currentTarget, "review-result", "Creating case record...", createCase));
  els["active-add-documents"].addEventListener("click", (event) => withAction(event.currentTarget, "active-result", "Opening document workflow status...", async () => activeToolMessage("Add Documents")));
  els["active-edit-case"].addEventListener("click", (event) => guidedStateAction(event.currentTarget, "active-result", "Opening case editor...", null, async () => {
    state.draft = { ...(state.activeCase || {}) };
    state.mode = "essential";
    state.step = 0;
    renderQuestion();
  }));
  els["active-change-case"].addEventListener("click", (event) => withAction(event.currentTarget, "active-result", "Preparing case switch...", async () => {
    showEntry();
    setActionPanel("entry-result", "success", resultRows([
      ["Active case preserved", escapeHtml(state.activeCase?.title || "Current case")],
      ["Action", "Choose another case or create a new one. Nothing changed yet."],
    ]));
    scrollActionPanel("entry-result");
  }));
  [
    ["active-ask-veritas", "Ask Veritas"],
    ["active-review-evidence", "Review Evidence"],
    ["active-view-timeline", "View Timeline"],
    ["active-view-contradictions", "View Contradictions"],
    ["active-view-parties", "View Parties"],
    ["active-view-financials", "View Financial Records"],
    ["active-view-filings", "View Filings"],
    ["active-build-report", "Build Report"],
  ].forEach(([id, label]) => {
    els[id].addEventListener("click", (event) => withAction(event.currentTarget, "active-result", `Opening ${label} status...`, async () => activeToolMessage(label)));
  });
}

async function init() {
  bind();
  wire();
  await withAction(null, "entry-result", "Loading case continuity...", async () => {
    await loadCases();
    showEntry();
  });
}

window.addEventListener("DOMContentLoaded", init);
