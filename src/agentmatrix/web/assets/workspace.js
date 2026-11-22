"use strict";

const form = document.querySelector("#question-form");
const question = document.querySelector("#question");
const runButton = document.querySelector("#run-button");
const runLabel = document.querySelector("#run-label");
const serviceStatus = document.querySelector("#service-status");
const serviceLabel = document.querySelector("#service-label");
const answerPanel = document.querySelector("#answer-panel");
const emptyAnswer = document.querySelector("#empty-answer");
const loading = document.querySelector("#loading");
const elapsed = document.querySelector("#elapsed");
const runError = document.querySelector("#run-error");
const answerText = document.querySelector("#answer-text");
const copyAnswer = document.querySelector("#copy-answer");
const announcement = document.querySelector("#announcement");
const sourceCount = document.querySelector("#source-count");
const sourceList = document.querySelector("#source-list");
const runDetails = document.querySelector("#run-details");
const addPolicies = document.querySelector("#add-policies");
const policyFiles = document.querySelector("#policy-files");
const policyList = document.querySelector("#policy-list");
const policyScope = document.querySelector("#policy-scope");
const policyError = document.querySelector("#policy-error");
const examples = document.querySelector("#examples");
const sourceCards = new Map();
const policyStorageKey = "agentmatrix.policies.v1";
const maxPolicies = 8;
const maxPolicyFileBytes = 2 * 1024 * 1024;

let currentAnswer = "";
let policies = readPolicies();

function readPolicies() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(policyStorageKey) || "[]");
    if (Array.isArray(saved)) {
      return saved.filter((policy) => typeof policy?.title === "string" && typeof policy.text === "string")
        .slice(0, maxPolicies);
    }
  } catch {
    // Storage can be unavailable in some browser configurations.
  }
  return [];
}

function providerLabel(mode) {
  return { ollama: "Ollama", deterministic: "Deterministic mode", langchain: "LangChain" }[mode] || "AgentMatrix";
}

async function refreshServiceStatus() {
  try {
    const response = await fetch("/ready", { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error("Service is unavailable.");
    const status = await response.json();
    serviceStatus.dataset.state = "ready";
    serviceLabel.textContent = status.model
      ? `${providerLabel(status.mode)} · ${status.model}`
      : `${providerLabel(status.mode)} ready`;
  } catch {
    serviceStatus.dataset.state = "offline";
    serviceLabel.textContent = "Model unavailable";
  }
}

function textElement(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

function setBusy(busy) {
  runButton.disabled = busy;
  addPolicies.disabled = busy || policies.length >= maxPolicies;
  policyList.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

function renderPolicies() {
  const count = policies.length;
  policyScope.textContent = count
    ? `Searching ${count} uploaded ${count === 1 ? "policy" : "policies"} in this tab.`
    : "Searching the three sample policies.";
  examples.hidden = count > 0;
  question.placeholder = count
    ? "Ask a question about your uploaded policies…"
    : "Ask about incident response, tool permissions, or evidence…";
  policyList.hidden = count === 0;
  policyList.replaceChildren();
  policies.forEach((policy, index) => {
    const item = document.createElement("li");
    const remove = textElement("button", "Remove", "remove-policy");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${policy.title}`);
    remove.addEventListener("click", () => {
      policies.splice(index, 1);
      savePolicies([]);
      (policyList.querySelectorAll("button")[index] || addPolicies).focus();
    });
    item.append(textElement("span", policy.title), remove);
    policyList.append(item);
  });
  setBusy(false);
}

function showPolicyErrors(messages) {
  policyError.textContent = messages.join("\n");
  policyError.hidden = !messages.length;
}

function savePolicies(errors) {
  try {
    if (policies.length) sessionStorage.setItem(policyStorageKey, JSON.stringify(policies));
    else sessionStorage.removeItem(policyStorageKey);
  } catch {
    errors.push("Your policies are ready to search. Upload them again after refreshing this page.");
  }
  renderPolicies();
  showPolicyErrors(errors);
  resetRun();
  renderSources([], "Run a question to see matching policies and their excerpts.");
}

addPolicies.addEventListener("click", () => policyFiles.click());
policyFiles.addEventListener("change", async () => {
  const files = Array.from(policyFiles.files);
  policyFiles.value = "";
  if (!files.length) return;

  setBusy(true);
  policyScope.textContent = "Reading your policy files…";
  showPolicyErrors([]);
  const errors = [];
  const previousCount = policies.length;
  for (const file of files) {
    if (policies.length >= maxPolicies) {
      errors.push("The library can hold up to 8 files. Remove a policy to add another.");
      break;
    }
    if (file.size > maxPolicyFileBytes) {
      errors.push(`${file.name} — Choose a file up to 2 MB.`);
      continue;
    }
    try {
      const url = `/v1/policies/extract?${new URLSearchParams({ filename: file.name })}`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
        signal: AbortSignal.timeout(30000),
      });
      const extracted = await response.json().catch(() => null);
      if (!response.ok || !extracted?.text) {
        throw new Error(typeof extracted?.detail === "string" ? extracted.detail : "Could not read this file.");
      }
      if (policies.some((policy) => policy.title === extracted.title && policy.text === extracted.text)) {
        errors.push(`${file.name} — Already in this library.`);
        continue;
      }
      policies.push(extracted);
    } catch (error) {
      errors.push(`${file.name} — ${error.message}`);
    }
  }
  if (policies.length > previousCount) {
    savePolicies(errors);
  } else {
    renderPolicies();
    showPolicyErrors(errors);
  }
});

function renderSources(evidence = [], message = "No matching policy sources were found.") {
  sourceCards.clear();
  sourceList.replaceChildren();
  sourceCount.hidden = evidence.length === 0;
  sourceCount.textContent = evidence.length;

  if (evidence.length === 0) {
    sourceList.append(textElement("p", message, "side-empty"));
    return;
  }

  for (const source of evidence) {
    const card = document.createElement("details");
    const summary = document.createElement("summary");
    const body = document.createElement("div");
    card.className = "source";
    body.className = "source-body";
    card.open = sourceCards.size === 0;

    summary.append(textElement("span", source.title || source.id, "source-title"));
    const metadata = textElement("div", "", "source-meta");
    metadata.append(textElement("span", source.id));
    if (Number.isFinite(source.score)) {
      metadata.append(textElement("span", `Keyword match ${source.score.toFixed(2)}`));
      const meter = document.createElement("meter");
      meter.min = 0;
      meter.max = 1;
      meter.value = source.score;
      meter.setAttribute("aria-label", "Keyword overlap");
      metadata.append(meter);
    }
    body.append(textElement("p", source.text), metadata);
    card.append(summary, body);
    sourceList.append(card);
    sourceCards.set(source.id.toLowerCase(), card);
  }
}

function appendInline(container, text) {
  const spans = text.split(/(\*\*[^*\n]+\*\*|\[(?:kb-\d+|policy-\d+-\d+)\])/gi);
  for (const span of spans) {
    if (span.startsWith("**") && span.endsWith("**")) {
      const strong = document.createElement("strong");
      appendInline(strong, span.slice(2, -2));
      container.append(strong);
      continue;
    }

    const id = span.match(/^\[((?:kb-\d+|policy-\d+-\d+))\]$/i)?.[1];
    const card = id && sourceCards.get(id.toLowerCase());
    if (card) {
      const citation = textElement("button", id, "citation");
      citation.type = "button";
      citation.setAttribute("aria-label", `Inspect source ${id}`);
      citation.addEventListener("click", () => {
        card.open = true;
        card.querySelector("summary").focus();
      });
      container.append(citation);
    } else {
      container.append(document.createTextNode(span));
    }
  }
}

function renderAnswer(answer) {
  answerText.replaceChildren();
  let list = null;

  for (const line of answer.split(/\r?\n/)) {
    const text = line.trim();
    if (!text) {
      list = null;
      continue;
    }

    const bullet = text.match(/^[-*]\s+(.+)/);
    if (bullet) {
      if (!list) {
        list = document.createElement("ul");
        answerText.append(list);
      }
      const item = document.createElement("li");
      appendInline(item, bullet[1]);
      list.append(item);
    } else {
      list = null;
      const paragraph = document.createElement("p");
      appendInline(paragraph, text);
      answerText.append(paragraph);
    }
  }
}

function renderRunDetails(result) {
  document.querySelector("#run-provider").textContent = providerLabel(result.mode);
  document.querySelector("#run-latency").textContent = Number.isFinite(result.latency_ms)
    ? `${(result.latency_ms / 1000).toFixed(1)} s` : "—";
  const policy = result.policy_events?.find((event) => event.type === "prompt_injection")
    || result.policy_events?.find((event) => event.type === "precheck");
  document.querySelector("#run-policy").textContent = policy?.action || "—";
  document.querySelector("#run-trace").textContent = result.trace_id || "—";
  runDetails.hidden = false;
}

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.dataset.question;
    question.setCustomValidity("");
    question.focus();
  });
});

question.addEventListener("input", () => question.setCustomValidity(""));
question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && !runButton.disabled) {
    event.preventDefault();
    form.requestSubmit();
  }
});

function resetRun() {
  currentAnswer = "";
  copyAnswer.hidden = true;
  copyAnswer.textContent = "Copy answer";
  answerText.replaceChildren();
  answerText.hidden = true;
  emptyAnswer.hidden = false;
  runError.hidden = true;
  runDetails.hidden = true;
  runDetails.open = false;
  announcement.textContent = "";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (runButton.disabled) return;
  const task = question.value.trim();
  if (task.length < 3) {
    question.setCustomValidity("Enter a question with at least 3 characters.");
    question.reportValidity();
    return;
  }

  resetRun();
  emptyAnswer.hidden = true;
  renderSources([], "Waiting for the sources from this run.");
  setBusy(true);
  runLabel.textContent = "Running…";
  loading.hidden = false;
  answerPanel.setAttribute("aria-busy", "true");
  announcement.textContent = "AgentMatrix is generating an answer.";
  elapsed.textContent = "0 s";
  const start = performance.now();
  const clock = setInterval(() => {
    elapsed.textContent = `${Math.floor((performance.now() - start) / 1000)} s`;
  }, 1000);

  try {
    const response = await fetch("/v1/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, policies }),
      signal: AbortSignal.timeout(200000),
    });
    if (response.status === 401) {
      throw new Error("Sign in again in the browser, then retry your question.");
    }
    const result = await response.json().catch(() => null);
    if (!response.ok || !result || typeof result.answer !== "string") {
      const detail = result?.detail;
      throw new Error(typeof detail === "string" ? detail : "The request did not complete. Try again.");
    }

    currentAnswer = result.answer;
    renderSources(result.evidence);
    renderAnswer(currentAnswer || "The agent returned an empty answer.");
    renderRunDetails(result);
    answerText.hidden = false;
    copyAnswer.hidden = !currentAnswer;
    announcement.textContent = "Answer ready. Review the answer and its retrieved evidence below.";
  } catch (error) {
    runError.textContent = error?.name === "TimeoutError"
      ? "The request took too long. Try a shorter question or run it again."
      : error?.name === "TypeError"
        ? "Could not reach AgentMatrix. Check the connection and try again."
        : error.message;
    runError.hidden = false;
    renderSources([], "Evidence will appear after a successful run.");
    announcement.textContent = "";
    refreshServiceStatus();
  } finally {
    clearInterval(clock);
    loading.hidden = true;
    setBusy(false);
    runLabel.textContent = "Run agent";
    answerPanel.setAttribute("aria-busy", "false");
  }
});

copyAnswer.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(currentAnswer);
    copyAnswer.textContent = "Copied";
    announcement.textContent = "Answer copied to the clipboard.";
  } catch {
    announcement.textContent = "Clipboard unavailable. Select the answer text to copy it.";
    copyAnswer.textContent = "Copy unavailable";
    answerText.focus();
  }
});

renderPolicies();
refreshServiceStatus();
