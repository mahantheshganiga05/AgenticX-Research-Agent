/**
 * AgenticX Research Agent - Frontend Controller
 * Handles user interactions, API requests, dynamic citation linking, and audit view.
 */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("research-form");
  const questionInput = document.getElementById("question-input");
  const submitBtn = document.getElementById("submit-btn");
  const exampleChips = document.getElementById("example-chips");

  const statusPanel = document.getElementById("status-panel");
  const statusText = document.getElementById("status-text");
  const statusSub = document.getElementById("status-sub");
  const stepCounterBadge = document.getElementById("step-counter-badge");

  const errorBanner = document.getElementById("error-banner");
  const errorTitle = document.getElementById("error-title");
  const errorMessage = document.getElementById("error-message");

  const resultsContainer = document.getElementById("results-container");
  const answerContent = document.getElementById("answer-content");
  const responseStatusBadge = document.getElementById("response-status-badge");
  const responseStepsBadge = document.getElementById("response-steps-badge");

  const activityTimeline = document.getElementById("activity-timeline");
  const activityCount = document.getElementById("activity-count");

  const sourcesList = document.getElementById("sources-list");
  const sourcesCount = document.getElementById("sources-count");

  const rawJsonViewer = document.getElementById("raw-json-viewer");

  // Handle example chips
  if (exampleChips) {
    exampleChips.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      const query = chip.getAttribute("data-query");
      if (query) {
        questionInput.value = query;
        questionInput.focus();
        form.dispatchEvent(new Event("submit"));
      }
    });
  }

  // Handle form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = questionInput.value.trim();
    if (!query) return;

    setLoading(true, query);

    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: "Network error occurred." }));
        throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      renderResults(data);
    } catch (err) {
      console.error("Research error:", err);
      showError("Research Request Failed", err.message || "An unexpected error occurred. Check server logs.");
    } finally {
      setLoading(false);
    }
  });

  function setLoading(isLoading, query = "") {
    if (isLoading) {
      submitBtn.disabled = true;
      statusPanel.classList.remove("hidden");
      errorBanner.classList.add("hidden");
      resultsContainer.classList.add("hidden");

      statusText.textContent = "Agent is planning and investigating...";
      statusSub.textContent = `Running autonomous research loop (capped at 6 steps)`;
      stepCounterBadge.textContent = "Step 1 / 6";
    } else {
      submitBtn.disabled = false;
      statusPanel.classList.add("hidden");
    }
  }

  function showError(title, msg) {
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function renderResults(data) {
    errorBanner.classList.add("hidden");
    resultsContainer.classList.remove("hidden");

    // 1. Meta badges
    responseStatusBadge.textContent = data.status.replace(/_/g, " ");
    responseStatusBadge.className = `status-chip ${data.status}`;
    responseStepsBadge.textContent = `${data.steps_used} / ${data.max_steps} Steps`;

    // 2. Render Tool Activity
    activityTimeline.innerHTML = "";
    if (data.tool_history && data.tool_history.length > 0) {
      activityCount.textContent = `${data.tool_history.length} Actions`;
      data.tool_history.forEach((step) => {
        const stepEl = document.createElement("div");
        stepEl.className = "timeline-step";

        const statusClass = step.success ? "success" : "failed";
        const toolClass = step.tool.toLowerCase();

        stepEl.innerHTML = `
          <div class="step-number">#${step.step}</div>
          <div class="step-content">
            <div class="step-header">
              <span class="tool-badge ${toolClass}">${escapeHtml(step.tool)}</span>
              <span class="step-status ${statusClass}">${step.success ? "Success" : "Failed"}</span>
            </div>
            <div class="step-summary">${escapeHtml(step.summary || "")}</div>
          </div>
        `;
        activityTimeline.appendChild(stepEl);
      });
    } else {
      activityCount.textContent = "0 Actions";
      activityTimeline.innerHTML = `<div class="step-summary">No tools were recorded.</div>`;
    }

    // 3. Render Sources Registry
    sourcesList.innerHTML = "";
    if (data.sources && data.sources.length > 0) {
      sourcesCount.textContent = `${data.sources.length} Sources`;
      data.sources.forEach((src) => {
        const card = document.createElement("div");
        card.className = "source-card";
        card.id = `source-card-${src.source_id}`;

        card.innerHTML = `
          <div class="source-header">
            <span class="source-id-badge">[${escapeHtml(src.source_id)}]</span>
            <span class="source-domain">${escapeHtml(src.domain || "Web")}</span>
          </div>
          <a href="${escapeHtml(src.url)}" target="_blank" rel="noopener noreferrer" class="source-title">
            ${escapeHtml(src.title || "Untitled")}
          </a>
          <p class="source-snippet">${escapeHtml(src.snippet || "No snippet available.")}</p>
        `;
        sourcesList.appendChild(card);
      });
    } else {
      sourcesCount.textContent = "0 Sources";
      sourcesList.innerHTML = `<div class="step-summary">No web sources collected.</div>`;
    }

    // 4. Render Answer with Interactive Citations
    const formattedHtml = formatAnswerMarkdown(data.answer);
    answerContent.innerHTML = formattedHtml;

    // Attach citation interactive highlights
    document.querySelectorAll(".citation-tag").forEach((tag) => {
      tag.addEventListener("click", () => {
        const sid = tag.getAttribute("data-source-id");
        highlightSource(sid);
      });
      tag.addEventListener("mouseenter", () => {
        const sid = tag.getAttribute("data-source-id");
        highlightSource(sid);
      });
    });

    // 5. Raw JSON Audit Log
    rawJsonViewer.textContent = JSON.stringify(data, null, 2);
  }

  function highlightSource(sourceId) {
    // Remove previous focus
    document.querySelectorAll(".source-card").forEach((c) => c.classList.remove("focused"));
    const targetCard = document.getElementById(`source-card-${sourceId}`);
    if (targetCard) {
      targetCard.classList.add("focused");
      targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function formatAnswerMarkdown(text) {
    if (!text) return "<p>No answer available.</p>";

    // Escape raw HTML first
    let sanitized = escapeHtml(text);

    // Convert Markdown headers
    sanitized = sanitized.replace(/^### (.*$)/gim, "<h3>$1</h3>");
    sanitized = sanitized.replace(/^## (.*$)/gim, "<h2>$1</h2>");
    sanitized = sanitized.replace(/^# (.*$)/gim, "<h1>$1</h1>");

    // Convert Markdown bold and italic
    sanitized = sanitized.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    sanitized = sanitized.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Convert Markdown links [Title](url)
    sanitized = sanitized.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Convert inline citations [S1], [S2] into interactive badges
    sanitized = sanitized.replace(/\[(S\d+)\]/g, (match, sid) => {
      return `<span class="citation-tag" data-source-id="${sid}">[${sid}]</span>`;
    });

    // Convert bullet lists
    sanitized = sanitized.replace(/^\s*-\s+(.*$)/gim, "<li>$1</li>");
    sanitized = sanitized.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

    // Convert newlines into paragraphs
    const paragraphs = sanitized
      .split(/\n\n+/)
      .map((p) => (p.startsWith("<h") || p.startsWith("<ul") ? p : `<p>${p}</p>`))
      .join("");

    return paragraphs;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
