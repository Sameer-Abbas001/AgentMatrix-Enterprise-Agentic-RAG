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
const sourceCards = new Map();

let currentAnswer = "";

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
  const spans = text.split(/(\*\*[^*\n]+\*\*|\[kb-\d+\])/gi);
  for (const span of spans) {
    if (span.startsWith("**") && span.endsWith("**")) {
      container.append(textElement("strong", span.slice(2, -2)));
      continue;
    }

    const id = span.match(/^\[(kb-\d+)\]$/i)?.[1];
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (runButton.disabled) return;
  const task = question.value.trim();
  if (task.length < 3) {
    question.setCustomValidity("Enter a question with at least 3 characters.");
    question.reportValidity();
    return;
  }

  currentAnswer = "";
  copyAnswer.hidden = true;
  copyAnswer.textContent = "Copy answer";
  answerText.hidden = true;
  emptyAnswer.hidden = true;
  runError.hidden = true;
  runDetails.hidden = true;
  runDetails.open = false;
  renderSources([], "Waiting for the sources from this run.");
  runButton.disabled = true;
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
      body: JSON.stringify({ task }),
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
    runButton.disabled = false;
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

refreshServiceStatus();
