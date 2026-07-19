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

function previewFields() {
  return essentialQuestions.concat(optionalQuestions).filter((item) => state.draft[item.key]);
}

function renderPreview(target = els["live-preview"], { includeEdit = false } = {}) {
  const fields = previewFields();
  target.innerHTML = fields.length ? fields.map((item) => `
    <div class="guided-preview-item">
      <strong>${escapeHtml(item.label)}</strong>
      <div class="note">${escapeHtml(state.draft[item.key])}</div>
      <span class="guided-source-tag">${sourceTag(state.draft[item.key])}</span>
      ${includeEdit ? `<button class="button mini guided-edit-field" data-edit-field="${escapeHtml(item.key)}" type="button">Edit Field</button>` : ""}
    </div>
  `).join("") : `<div class="note">The case record will build here as answers are entered.</div>`;
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
  setActionPanel("active-result", "success", resultRows([
    ["Tool", escapeHtml(label)],
    ["Status", "Document workflow is the next milestone. The active case foundation is ready."],
  ]));
  scrollActionPanel("active-result");
}

function wire() {
  document.querySelectorAll("[data-clear-result]").forEach((button) => {
    button.addEventListener("click", () => clearActionPanel(button.getAttribute("data-clear-result")));
  });
  els["resume-last-case"].addEventListener("click", (event) => withAction(event.currentTarget, "entry-result", "Resuming last case...", () => resumeCase(event.currentTarget.dataset.caseId)));
  els["choose-another-case"].addEventListener("click", () => showCasePicker());
  els["open-existing-case"].addEventListener("click", () => showCasePicker());
  els["create-new-case"].addEventListener("click", (event) => withAction(event.currentTarget, "entry-result", "Starting guided intake...", async () => startNewCase()));
  els["intake-continue"].addEventListener("click", (event) => withAction(event.currentTarget, "intake-result", "Saving answer...", async () => nextQuestion()));
  els["intake-back"].addEventListener("click", () => backQuestion());
  els["intake-skip"].addEventListener("click", () => skipQuestion());
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
  els["review-back"].addEventListener("click", () => {
    state.mode = "essential";
    state.step = essentialQuestions.length - 1;
    renderQuestion();
  });
  els["continue-details"].addEventListener("click", () => {
    state.mode = "optional";
    state.step = 0;
    renderQuestion();
  });
  els["create-case-final"].addEventListener("click", (event) => withAction(event.currentTarget, "review-result", "Creating case record...", createCase));
  els["active-add-documents"].addEventListener("click", () => activeToolMessage("Add Documents"));
  els["active-edit-case"].addEventListener("click", () => {
    state.draft = { ...(state.activeCase || {}) };
    state.mode = "essential";
    state.step = 0;
    renderQuestion();
  });
  els["active-change-case"].addEventListener("click", () => {
    showEntry();
    setActionPanel("entry-result", "success", resultRows([
      ["Active case preserved", escapeHtml(state.activeCase?.title || "Current case")],
      ["Action", "Choose another case or create a new one. Nothing changed yet."],
    ]));
  });
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
    els[id].addEventListener("click", () => activeToolMessage(label));
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
