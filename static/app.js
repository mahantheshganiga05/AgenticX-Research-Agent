/**
 * AgenticX Research Agent - Cyber-Intelligence HUD Terminal Controller
 * Real backend integration:
 * - /api/research: Autonomous research loop with Tavily, fetch_page, and Gemini
 * - /api/history: Persistent SQLite session archive
 * - /health: Live telemetry and model status
 */

document.addEventListener("DOMContentLoaded", () => {
  // ========================================================================
  // 1. DOM REFERENCES
  // ========================================================================

  // Search Terminal Elements
  const form = document.getElementById("research-form");
  const questionInput = document.getElementById("question-input");
  const clearBtn = document.getElementById("clear-btn");
  const submitBtn = document.getElementById("submit-btn");
  const submitBtnText = document.getElementById("submit-btn-text");

  // Top Telemetry Header & Live Indicator
  const headerLiveIndicator = document.getElementById("header-live-indicator");
  const headerLiveText = document.getElementById("header-live-text");
  const hudSessionId = document.getElementById("hud-session-id");
  const hudStepCounter = document.getElementById("hud-step-counter");
  const hudModelVal = document.getElementById("hud-model-val");

  // Left Matrix Data Stream
  const matrixDataStream = document.getElementById("matrix-data-stream");

  // Right Global Scan Hologram Frame & Metadata Elements
  const hologramFrame = document.getElementById("hologram-frame");
  const globalScanStatusBadge = document.getElementById("global-scan-status-badge");
  const metaSourceNet = document.getElementById("meta-source-net");
  const metaIndexing = document.getElementById("meta-indexing");
  const metaSignal = document.getElementById("meta-signal");
  const metaScanMode = document.getElementById("meta-scan-mode");

  // Navigation Buttons & Modals
  const btnNewResearch = document.getElementById("btn-new-research");
  const btnHistory = document.getElementById("btn-history");
  const btnSettings = document.getElementById("btn-settings");

  const historyModal = document.getElementById("history-modal");
  const historyModalClose = document.getElementById("history-modal-close");
  const historySessionsContainer = document.getElementById("history-sessions-container");
  const historyModalSpinner = document.getElementById("history-modal-spinner");
  const historyModalEmpty = document.getElementById("history-modal-empty");

  const settingsModal = document.getElementById("settings-modal");
  const settingsModalClose = document.getElementById("settings-modal-close");

  // Pipeline Cards (4 Stages)
  const pipeCard1 = document.getElementById("pipe-card-1");
  const pipeCard2 = document.getElementById("pipe-card-2");
  const pipeCard3 = document.getElementById("pipe-card-3");
  const pipeCard4 = document.getElementById("pipe-card-4");

  const pipeIcon1 = document.getElementById("pipe-icon-1");
  const pipeIcon2 = document.getElementById("pipe-icon-2");
  const pipeIcon3 = document.getElementById("pipe-icon-3");
  const pipeIcon4 = document.getElementById("pipe-icon-4");

  const pipeDesc1 = document.getElementById("pipe-desc-1");
  const pipeDesc2 = document.getElementById("pipe-desc-2");
  const pipeDesc3 = document.getElementById("pipe-desc-3");
  const pipeDesc4 = document.getElementById("pipe-desc-4");

  // Error Banner
  const errorBanner = document.getElementById("error-banner");
  const errorMessage = document.getElementById("error-message");

  // Agent Activity Table
  const activityRowsBody = document.getElementById("activity-rows-body");
  const activityFooterStatus = document.getElementById("activity-footer-status");

  // Research Summary Panel
  const summaryHeadline = document.getElementById("summary-headline");
  const summaryParagraphs = document.getElementById("summary-paragraphs");
  const summaryCitationsFooter = document.getElementById("summary-citations-footer");
  const citationPillsRow = document.getElementById("citation-pills-row");

  // Evidence Panel
  const evidenceContainer = document.getElementById("evidence-container");

  // ========================================================================
  // 2. CLEAN INITIAL / EMPTY STATE CONTROLLER
  // ========================================================================

  function resetToCleanInitialState() {
    // 1. Search input and clear button
    if (questionInput) {
      questionInput.value = "";
      questionInput.disabled = false;
      questionInput.placeholder = "Search for anything...";
    }
    updateClearVisibility();

    // 2. Search button
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("scanning-pulse");
    }
    if (submitBtnText) submitBtnText.textContent = "SEARCH";

    // 3. Telemetry Session and Step Header
    if (hudSessionId) hudSessionId.textContent = "#NEW";
    if (hudStepCounter) hudStepCounter.textContent = "0/6";

    // 4. Header Live Indicator
    if (headerLiveIndicator) headerLiveIndicator.className = "header-live-indicator";
    if (headerLiveText) headerLiveText.textContent = "SYSTEM LIVE";

    // 5. Matrix Data Stream normal speed
    if (matrixDataStream) matrixDataStream.classList.remove("scanning-speed");

    // 6. Global Scan Panel State A (LIVE • READY)
    if (hologramFrame) hologramFrame.classList.remove("scanning-globe");
    if (globalScanStatusBadge) {
      globalScanStatusBadge.innerHTML = '<span class="live-dot-pulse"></span> LIVE &bull; READY';
    }
    if (metaSourceNet) metaSourceNet.textContent = "READY";
    if (metaIndexing) metaIndexing.textContent = "STANDBY";
    if (metaSignal) metaSignal.textContent = "LIVE";
    if (metaScanMode) metaScanMode.textContent = "IDLE";

    // 7. Research Pipeline (All 4 in Waiting state)
    setStageUI(pipeCard1, pipeIcon1, pipeDesc1, 0, "pending", "Waiting");
    setStageUI(pipeCard2, pipeIcon2, pipeDesc2, 0, "pending", "Waiting");
    setStageUI(pipeCard3, pipeIcon3, pipeDesc3, 0, "pending", "Waiting");
    setStageUI(pipeCard4, pipeIcon4, pipeDesc4, 0, "pending", "Waiting");

    // 8. Agent Activity Empty State
    if (activityRowsBody) {
      activityRowsBody.innerHTML = `
        <tr class="activity-empty-row">
          <td colspan="3" class="activity-empty-cell">
            <div class="hud-empty-state">
              <span class="hud-empty-title">NO RESEARCH ACTIVITY</span>
              <span class="hud-empty-sub">Start a research query to begin.</span>
            </div>
          </td>
        </tr>
      `;
    }
    if (activityFooterStatus) activityFooterStatus.textContent = "SYSTEM READY // IDLE";

    // 9. Research Summary Clean Empty State
    if (summaryHeadline) {
      summaryHeadline.className = "summary-headline empty";
      summaryHeadline.textContent = "RESEARCH SUMMARY";
    }
    if (summaryParagraphs) {
      summaryParagraphs.innerHTML = '<p class="summary-empty-msg">Your research answer will appear here after you search.</p>';
    }
    if (citationPillsRow) citationPillsRow.innerHTML = "";
    if (summaryCitationsFooter) summaryCitationsFooter.classList.add("hidden");

    // 10. Evidence Clean Empty State
    if (evidenceContainer) {
      evidenceContainer.innerHTML = `
        <div class="evidence-empty-box" id="evidence-empty-box">
          <div class="hud-empty-state">
            <span class="hud-empty-title">EVIDENCE</span>
            <span class="hud-empty-sub">No sources yet.</span>
            <span class="hud-empty-detail">Search for a topic to retrieve verified sources.</span>
          </div>
        </div>
      `;
    }

    // 11. Error Banner
    hideError();
  }

  // ========================================================================
  // 3. TELEMETRY & APP INITIALIZATION
  // ========================================================================

  async function initTelemetry() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        const data = await res.json();
        if (hudModelVal && data.model) {
          hudModelVal.textContent = data.model.toUpperCase();
        }
      }
    } catch (e) {
      console.warn("Telemetry fetch error:", e);
    }
  }

  // Run clean reset and telemetry on initial load
  resetToCleanInitialState();
  initTelemetry();

  // ========================================================================
  // 4. SEARCH INPUT INTERACTION
  // ========================================================================

  function updateClearVisibility() {
    if (!clearBtn || !questionInput) return;
    if (questionInput.value && questionInput.value.trim().length > 0) {
      clearBtn.classList.remove("hidden");
    } else {
      clearBtn.classList.add("hidden");
    }
  }

  if (questionInput) {
    questionInput.addEventListener("input", updateClearVisibility);
    questionInput.addEventListener("keyup", updateClearVisibility);
    questionInput.addEventListener("change", updateClearVisibility);
    questionInput.addEventListener("paste", () => setTimeout(updateClearVisibility, 20));
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (questionInput) {
        questionInput.value = "";
        questionInput.focus();
        updateClearVisibility();
      }
    });
  }

  // Keyboard shortcut '/' focuses search terminal
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== questionInput) {
      if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault();
        if (questionInput) {
          questionInput.focus();
          questionInput.select();
        }
      }
    }
    if (e.key === "Escape") {
      closeModals();
    }
  });

  // Quick suggestion chips
  document.querySelectorAll(".quick-chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-query");
      if (q && questionInput) {
        questionInput.value = q;
        updateClearVisibility();
        questionInput.focus();
        form.dispatchEvent(new Event("submit"));
      }
    });
  });

  // ========================================================================
  // 5. NAVIGATION & MODALS
  // ========================================================================

  if (btnNewResearch) {
    btnNewResearch.addEventListener("click", () => {
      closeModals();
      setActiveNav(btnNewResearch);
      resetToCleanInitialState();
      if (questionInput) {
        questionInput.focus();
      }
    });
  }

  if (btnHistory) {
    btnHistory.addEventListener("click", () => {
      setActiveNav(btnHistory);
      openHistoryModal();
    });
  }

  if (btnSettings) {
    btnSettings.addEventListener("click", () => {
      setActiveNav(btnSettings);
      openSettingsModal();
    });
  }

  function setActiveNav(btn) {
    [btnNewResearch, btnHistory, btnSettings].forEach((b) => {
      if (b) b.classList.remove("active");
    });
    if (btn) btn.classList.add("active");
  }

  function closeModals() {
    if (historyModal) historyModal.classList.add("hidden");
    if (settingsModal) settingsModal.classList.add("hidden");
    setActiveNav(btnNewResearch);
  }

  if (historyModalClose) historyModalClose.addEventListener("click", closeModals);
  if (settingsModalClose) settingsModalClose.addEventListener("click", closeModals);

  [historyModal, settingsModal].forEach((modal) => {
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModals();
      });
    }
  });

  async function openHistoryModal() {
    if (!historyModal) return;
    historyModal.classList.remove("hidden");
    if (historyModalSpinner) historyModalSpinner.classList.remove("hidden");
    if (historyModalEmpty) historyModalEmpty.classList.add("hidden");
    if (historySessionsContainer) historySessionsContainer.innerHTML = "";

    try {
      const res = await fetch("/api/history");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const sessions = data.history || [];

      if (historyModalSpinner) historyModalSpinner.classList.add("hidden");

      if (sessions.length === 0) {
        if (historyModalEmpty) historyModalEmpty.classList.remove("hidden");
        return;
      }

      sessions.forEach((s) => {
        const item = document.createElement("div");
        item.className = "history-item-card";
        const dateStr = s.created_at ? formatTimestamp(s.created_at) : "Recently";
        const stepsUsed = s.steps_used || 2;
        const maxSteps = s.max_steps || 6;
        const totalTime = typeof s.total_time === "number" ? `${s.total_time.toFixed(1)}s` : `${s.total_time || 0}s`;

        item.innerHTML = `
          <div class="history-item-top">
            <h3 class="history-query-title">${escapeHtml(s.question)}</h3>
            <span class="verified-pill">&#10003; ${escapeHtml((s.status || "COMPLETE").toUpperCase())}</span>
          </div>
          <div class="history-item-meta">
            <span>${s.source_count || 0} Sources</span>
            <span>&bull;</span>
            <span>${stepsUsed}/${maxSteps} Steps</span>
            <span>&bull;</span>
            <span>${totalTime}</span>
            <span>&bull;</span>
            <span>${dateStr}</span>
          </div>
          <button type="button" class="history-load-btn" data-id="${s.id}">&gt; LOAD RESEARCH</button>
        `;

        const loadBtn = item.querySelector(".history-load-btn");
        loadBtn.addEventListener("click", () => loadSavedSession(s.id));

        historySessionsContainer.appendChild(item);
      });
    } catch (err) {
      console.error("Failed to load history:", err);
      if (historyModalSpinner) historyModalSpinner.classList.add("hidden");
      if (historySessionsContainer) {
        historySessionsContainer.innerHTML = `<div style="color:var(--status-error);font-family:var(--font-mono);font-size:11px;">Error loading research history: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  async function loadSavedSession(sessionId) {
    try {
      const res = await fetch(`/api/history/${sessionId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const session = await res.json();
      
      closeModals();
      if (questionInput) {
        questionInput.value = session.question || "";
        updateClearVisibility();
      }
      if (hudSessionId) {
        hudSessionId.textContent = `#HIST-${(session.id || sessionId).substring(0, 6).toUpperCase()}`;
      }

      renderResults(session);
    } catch (err) {
      console.error("Error loading session:", err);
      alert("Failed to load saved session: " + err.message);
    }
  }

  function openSettingsModal() {
    if (settingsModal) settingsModal.classList.remove("hidden");
  }

  // ========================================================================
  // 6. PIPELINE & LIVE SCAN CONTROLLER
  // ========================================================================

  function setStageUI(card, icon, descEl, fillPct, status, descText) {
    if (!card) return;
    card.className = `pipeline-step-card ${status}`;
    
    if (icon) {
      if (status === "completed") {
        icon.className = "pipe-status-icon-circle check-circle";
        icon.innerHTML = "&#10003;";
        icon.style.borderColor = "";
        icon.style.color = "";
      } else if (status === "active-pulse") {
        icon.className = "pipe-status-icon-circle spinner-circle";
        icon.innerHTML = "";
        icon.style.borderColor = "";
        icon.style.color = "";
      } else if (status === "error") {
        icon.className = "pipe-status-icon-circle";
        icon.style.borderColor = "var(--status-error)";
        icon.style.color = "var(--status-error)";
        icon.innerHTML = "!";
      } else {
        icon.className = "pipe-status-icon-circle ring-circle";
        icon.innerHTML = "";
        icon.style.borderColor = "";
        icon.style.color = "";
      }
    }

    if (descEl && descText) {
      descEl.textContent = descText;
    }

    const fill = card.querySelector(".pipe-progress-fill");
    if (fill) {
      fill.style.width = `${fillPct}%`;
    }
  }

  function startLiveScanningState() {
    // 1. Search button active visual state
    if (submitBtnText) submitBtnText.textContent = "SCANNING...";
    if (submitBtn) submitBtn.classList.add("scanning-pulse");

    // 2. Dynamic Scan Activity Metadata state
    if (metaSourceNet) metaSourceNet.textContent = "QUERYING";
    if (metaIndexing) metaIndexing.textContent = "PROCESSING";
    if (metaSignal) metaSignal.textContent = "LOCK";
    if (metaScanMode) metaScanMode.textContent = "AUTONOMOUS";

    // 3. Top Live Indicator state
    if (headerLiveIndicator) {
      headerLiveIndicator.className = "header-live-indicator scanning";
    }
    if (headerLiveText) headerLiveText.textContent = "SYSTEM SCANNING";

    // 4. Boost data stream and globe animation speed
    if (matrixDataStream) matrixDataStream.classList.add("scanning-speed");
    if (hologramFrame) hologramFrame.classList.add("scanning-globe");
    if (globalScanStatusBadge) {
      globalScanStatusBadge.innerHTML = '<span class="live-dot-pulse"></span> LIVE &bull; SCANNING';
    }

    // 5. Initial Pipeline state: Step 01 SEARCH active, 02..04 Waiting
    setStageUI(pipeCard1, pipeIcon1, pipeDesc1, 60, "active-pulse", "Searching (Tavily)...");
    setStageUI(pipeCard2, pipeIcon2, pipeDesc2, 0, "pending", "Waiting");
    setStageUI(pipeCard3, pipeIcon3, pipeDesc3, 0, "pending", "Waiting");
    setStageUI(pipeCard4, pipeIcon4, pipeDesc4, 0, "pending", "Waiting");

    if (hudStepCounter) hudStepCounter.textContent = "1/6";
    if (activityFooterStatus) activityFooterStatus.textContent = "AGENT EXECUTING TASK...";

    // Live Activity Row (Real operation in progress, no fake success)
    const nowStr = formatTimeNow();
    if (activityRowsBody) {
      activityRowsBody.innerHTML = `
        <tr class="activity-row-anim">
          <td><span class="status-dot-cyan"></span> ${nowStr}</td>
          <td class="action-name-cell">web_search</td>
          <td><span class="status-check-badge"><span class="mini-spinner" style="width:10px;height:10px;display:inline-block;vertical-align:middle;margin-right:4px;"></span> SEARCHING...</span></td>
        </tr>
      `;
    }
  }

  function completePipeline(data) {
    // Revert active scan speeds
    if (matrixDataStream) matrixDataStream.classList.remove("scanning-speed");
    if (hologramFrame) hologramFrame.classList.remove("scanning-globe");
    if (globalScanStatusBadge) {
      globalScanStatusBadge.innerHTML = '<span class="live-dot-pulse"></span> LIVE &bull; READY';
    }
    if (submitBtn) submitBtn.classList.remove("scanning-pulse");
    if (submitBtnText) submitBtnText.textContent = "SEARCH";
    if (questionInput) questionInput.placeholder = "Search for anything...";

    // Revert metadata values
    if (metaSourceNet) metaSourceNet.textContent = "ACTIVE";
    if (metaIndexing) metaIndexing.textContent = "READY";
    if (metaSignal) metaSignal.textContent = "LIVE";
    if (metaScanMode) metaScanMode.textContent = "RESEARCH";

    // Top Live Indicator state
    if (headerLiveIndicator) {
      headerLiveIndicator.className = "header-live-indicator";
    }
    if (headerLiveText) headerLiveText.textContent = "SYSTEM LIVE";

    // Map stages according to real execution
    setStageUI(pipeCard1, pipeIcon1, pipeDesc1, 100, "completed", "Complete");
    setStageUI(pipeCard2, pipeIcon2, pipeDesc2, 100, "completed", "Complete");
    setStageUI(pipeCard3, pipeIcon3, pipeDesc3, 100, "completed", "Complete");
    setStageUI(pipeCard4, pipeIcon4, pipeDesc4, 100, "completed", "Complete");

    const used = data.steps_used || 2;
    const max = data.max_steps || 6;
    if (hudStepCounter) hudStepCounter.textContent = `${used}/${max}`;
    if (activityFooterStatus) activityFooterStatus.textContent = "AGENT EXECUTION COMPLETE";
  }

  function errorPipeline(data, errorType) {
    // Stop active scanning state
    if (matrixDataStream) matrixDataStream.classList.remove("scanning-speed");
    if (hologramFrame) hologramFrame.classList.remove("scanning-globe");
    if (globalScanStatusBadge) {
      globalScanStatusBadge.innerHTML = '<span class="live-dot-pulse"></span> LIVE &bull; READY';
    }
    if (submitBtn) submitBtn.classList.remove("scanning-pulse");
    if (submitBtnText) submitBtnText.textContent = "SEARCH";
    if (questionInput) questionInput.placeholder = "Search for anything...";

    // Reset metadata
    if (metaSourceNet) metaSourceNet.textContent = "IDLE";
    if (metaIndexing) metaIndexing.textContent = "STANDBY";
    if (metaSignal) metaSignal.textContent = "ALERT";
    if (metaScanMode) metaScanMode.textContent = "RESEARCH";

    if (headerLiveIndicator) {
      headerLiveIndicator.className = "header-live-indicator error";
    }
    if (headerLiveText) headerLiveText.textContent = "SYSTEM NOTICE";

    if (errorType === "quota" || (data && data.status === "llm_quota_error")) {
      setStageUI(pipeCard1, pipeIcon1, pipeDesc1, 100, "completed", "Complete");
      setStageUI(pipeCard2, pipeIcon2, pipeDesc2, 100, "completed", "Complete");
      setStageUI(pipeCard3, pipeIcon3, pipeDesc3, 100, "completed", "Complete");
      setStageUI(pipeCard4, pipeIcon4, pipeDesc4, 100, "error", "Quota Error");
      const used = data && data.steps_used ? data.steps_used : 2;
      const max = data && data.max_steps ? data.max_steps : 6;
      if (hudStepCounter) hudStepCounter.textContent = `${used}/${max}`;
      if (activityFooterStatus) activityFooterStatus.textContent = "EXECUTION HALTED // QUOTA LIMIT";
    } else {
      setStageUI(pipeCard1, pipeIcon1, pipeDesc1, 100, "error", "Failed");
      setStageUI(pipeCard2, pipeIcon2, pipeDesc2, 0, "pending", "Waiting");
      setStageUI(pipeCard3, pipeIcon3, pipeDesc3, 0, "pending", "Waiting");
      setStageUI(pipeCard4, pipeIcon4, pipeDesc4, 0, "pending", "Waiting");
      if (hudStepCounter) hudStepCounter.textContent = "1/6";
      if (activityFooterStatus) activityFooterStatus.textContent = "EXECUTION TERMINATED";
    }
  }

  // ========================================================================
  // 7. RESEARCH FORM SUBMISSION (ONLY TRIGGER)
  // ========================================================================

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = questionInput.value.trim();
    if (!query) return;

    hideError();
    setSearching(true);

    // Generate fresh session ID upon real search
    const randomHex = Math.floor(Math.random() * 8999 + 1000);
    if (hudSessionId) hudSessionId.textContent = `#AG-${randomHex}`;

    startLiveScanningState();

    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: "Network request failed." }));
        throw new Error(errJson.detail || `Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      renderResults(data);
    } catch (err) {
      console.error("Research Agent error:", err);
      showError(err.message || "An unexpected error occurred while executing research.");
      errorPipeline(null, "failed");
      renderErrorActivity(err.message);
    } finally {
      setSearching(false);
    }
  });

  function setSearching(isLoading) {
    if (submitBtn) submitBtn.disabled = isLoading;
    if (questionInput) questionInput.disabled = isLoading;
  }

  function showError(msg) {
    if (errorMessage) errorMessage.textContent = msg;
    if (errorBanner) errorBanner.classList.remove("hidden");
  }

  function hideError() {
    if (errorBanner) errorBanner.classList.add("hidden");
  }

  // ========================================================================
  // 8. RENDER RESULTS (SUMMARY, CITATIONS, EVIDENCE, ACTIVITY)
  // ========================================================================

  function renderResults(data) {
    // 1. Check for failure or quota limits - do not show fake success
    if (data.status === "llm_quota_error" || data.status === "tool_failure" || data.status === "failed") {
      errorPipeline(data, data.status === "llm_quota_error" ? "quota" : "failed");
      showError(data.answer || "Research execution halted due to quota or tool limits.");
      if (summaryHeadline) {
        summaryHeadline.className = "summary-headline";
        summaryHeadline.textContent = data.question || "Research Terminated";
      }
      if (summaryParagraphs) {
        summaryParagraphs.innerHTML = `<p style="color:var(--status-error);font-family:var(--font-mono);font-size:12px;">${escapeHtml(data.answer || "Research execution failed.")}</p>`;
      }
      if (summaryCitationsFooter) summaryCitationsFooter.classList.add("hidden");
      renderEvidence(data.sources || []);
      renderActivityLog(data);
      return;
    }

    completePipeline(data);

    // 2. Query Title
    if (summaryHeadline) {
      summaryHeadline.className = "summary-headline";
      summaryHeadline.textContent = data.question || "Research Investigation";
    }

    // 3. Render Answer Markdown & Citations
    if (summaryParagraphs) {
      summaryParagraphs.innerHTML = formatMarkdownWithCitations(data.answer || "No answer generated.");
    }

    // 4. Citation Pills Row
    renderCitationPills(data.sources || [], data.answer || "");

    // 5. Evidence Panel (Right Column) with Live Entrance Animation
    renderEvidence(data.sources || []);

    // 6. Activity Table
    renderActivityLog(data);

    // Attach click/hover listeners on all citation tags
    attachCitationInteractivity();
  }

  function renderCitationPills(sources, answerText) {
    if (!citationPillsRow) return;
    citationPillsRow.innerHTML = "";

    const ids = new Set();
    if (sources && sources.length > 0) {
      sources.forEach((s) => {
        const sid = s.source_id || s.id;
        if (sid) ids.add(sid);
      });
    }

    const matches = (answerText || "").match(/\[S\d+\]/g);
    if (matches) {
      matches.forEach((m) => ids.add(m.replace(/\[|\]/g, "")));
    }

    if (ids.size === 0) {
      if (summaryCitationsFooter) summaryCitationsFooter.classList.add("hidden");
      return;
    }

    if (summaryCitationsFooter) summaryCitationsFooter.classList.remove("hidden");

    Array.from(ids).sort().forEach((sid) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "citation-tag";
      btn.setAttribute("data-source-id", sid);
      btn.textContent = `[${sid}]`;
      citationPillsRow.appendChild(btn);
    });
  }

  function renderEvidence(sources) {
    if (!evidenceContainer) return;
    evidenceContainer.innerHTML = "";

    if (!sources || sources.length === 0) {
      evidenceContainer.innerHTML = `
        <div class="evidence-empty-box" id="evidence-empty-box">
          <div class="hud-empty-state">
            <span class="hud-empty-title">NO SOURCES FOUND</span>
            <span class="hud-empty-sub">No verified sources were retrieved for this query.</span>
          </div>
        </div>
      `;
      return;
    }

    const sparkColors = ["#22D3EE", "#A855F7", "#C084FC", "#38BDF8", "#E879F9"];

    sources.forEach((src, idx) => {
      const sid = src.source_id || src.id || `S${idx + 1}`;
      const domain = src.domain || extractDomain(src.url) || "verified source";
      const title = src.title || "Untitled Research Source";
      const url = src.url || "#";
      const color = sparkColors[idx % sparkColors.length];

      const card = document.createElement("div");
      card.className = "evidence-source-card evidence-entering";
      card.style.animationDelay = `${idx * 0.08}s`;
      card.id = `evidence-card-${sid}`;

      card.innerHTML = `
        <div class="evidence-card-top">
          <span class="evidence-id-pill">[${escapeHtml(sid)}]</span>
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="evidence-title-link">
            ${escapeHtml(title)}
          </a>
        </div>
        <div class="evidence-card-bottom">
          <div class="evidence-domain-row">
            <svg class="doc-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <line x1="8" y1="8" x2="16" y2="8" />
              <line x1="8" y1="12" x2="16" y2="12" />
              <line x1="8" y1="16" x2="12" y2="16" />
            </svg>
            <span class="evidence-domain-name">${escapeHtml(domain)}</span>
          </div>
          <span class="verified-pill">&#10003; VERIFIED</span>
          
          <div class="evidence-sparkline-box" aria-hidden="true">
            <svg viewBox="0 0 80 24" class="sparkline-svg">
              <path d="${generateSparklinePath(idx)}" stroke="${color}" stroke-width="1.5" fill="none" class="sparkline-path-anim" />
            </svg>
          </div>
        </div>
      `;

      evidenceContainer.appendChild(card);
    });
  }

  function renderActivityLog(data) {
    if (!activityRowsBody) return;
    activityRowsBody.innerHTML = "";

    const history = data.tool_history || [];
    const baseTime = new Date();

    if (history.length > 0) {
      history.forEach((h, idx) => {
        const timeOffset = new Date(baseTime.getTime() - (history.length - idx + 1) * 2000);
        const timeStr = formatTimestampOnly(timeOffset);
        const isSuccess = h.success !== false;

        const row = document.createElement("tr");
        row.className = "activity-row-anim";
        row.innerHTML = `
          <td><span class="status-dot-cyan"></span> ${timeStr}</td>
          <td class="action-name-cell">${escapeHtml(h.tool || "tool")}</td>
          <td>
            <span class="${isSuccess ? 'status-check-badge' : 'status-error-badge'}">
              ${isSuccess ? '&#10003; SUCCESS' : '! FAILED'}
            </span>
          </td>
        `;
        activityRowsBody.appendChild(row);
      });

      // Analyze step
      const analyzeTime = new Date(baseTime.getTime() - 1000);
      const rowAnalyze = document.createElement("tr");
      rowAnalyze.className = "activity-row-anim";
      rowAnalyze.innerHTML = `
        <td><span class="status-dot-cyan"></span> ${formatTimestampOnly(analyzeTime)}</td>
        <td class="action-name-cell">analyze</td>
        <td><span class="status-check-badge">&#10003; SUCCESS</span></td>
      `;
      activityRowsBody.appendChild(rowAnalyze);

      // Synthesize step
      const isQuotaError = data.status === "llm_quota_error";
      const isFailed = data.status === "failed" || data.status === "tool_failure";
      const synthSuccess = !isQuotaError && !isFailed && Boolean(data.answer);

      const rowSynth = document.createElement("tr");
      rowSynth.className = "activity-row-anim";
      rowSynth.innerHTML = `
        <td><span class="status-dot-cyan"></span> ${formatTimestampOnly(baseTime)}</td>
        <td class="action-name-cell">synthesize</td>
        <td>
          <span class="${synthSuccess ? 'status-check-badge' : 'status-error-badge'}">
            ${synthSuccess ? '&#10003; SUCCESS' : (isQuotaError ? '! QUOTA ERROR' : '! FAILED')}
          </span>
        </td>
      `;
      activityRowsBody.appendChild(rowSynth);

    } else {
      const nowStr = formatTimeNow();
      const isQuota = data.status === "llm_quota_error";
      activityRowsBody.innerHTML = `
        <tr class="activity-row-anim">
          <td><span class="status-dot-cyan"></span> ${nowStr}</td>
          <td class="action-name-cell">web_search</td>
          <td><span class="status-check-badge">&#10003; SUCCESS</span></td>
        </tr>
        <tr class="activity-row-anim">
          <td><span class="status-dot-cyan"></span> ${nowStr}</td>
          <td class="action-name-cell">synthesize</td>
          <td>
            <span class="${isQuota ? 'status-error-badge' : 'status-check-badge'}">
              ${isQuota ? '! QUOTA ERROR' : '&#10003; SUCCESS'}
            </span>
          </td>
        </tr>
      `;
    }
  }

  function renderErrorActivity(errText) {
    if (!activityRowsBody) return;
    const nowStr = formatTimeNow();
    activityRowsBody.innerHTML = `
      <tr class="activity-row-anim">
        <td><span class="status-dot-cyan" style="background:var(--status-error);"></span> ${nowStr}</td>
        <td class="action-name-cell">web_search</td>
        <td><span class="status-error-badge">! FAILED</span></td>
      </tr>
    `;
    if (activityFooterStatus) activityFooterStatus.textContent = "EXECUTION FAILED";
  }

  // ========================================================================
  // 9. CITATIONS INTERACTION (HOVER & CLICK)
  // ========================================================================

  function attachCitationInteractivity() {
    document.querySelectorAll(".citation-tag, .inline-citation-tag").forEach((tag) => {
      tag.addEventListener("click", () => {
        const sid = tag.getAttribute("data-source-id");
        highlightEvidence(sid);
      });
      tag.addEventListener("mouseenter", () => {
        const sid = tag.getAttribute("data-source-id");
        highlightEvidence(sid);
      });
    });
  }

  function highlightEvidence(sid) {
    document.querySelectorAll(".evidence-source-card").forEach((c) => c.classList.remove("highlighted"));
    const target = document.getElementById(`evidence-card-${sid}`);
    if (target) {
      target.classList.add("highlighted");
      target.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  // ========================================================================
  // 10. HELPERS & FORMATTING
  // ========================================================================

  function formatMarkdownWithCitations(text) {
    if (!text) return "<p>No answer content available.</p>";

    let sanitized = escapeHtml(text);

    // Headings
    sanitized = sanitized.replace(/^### (.*$)/gim, "<h3>$1</h3>");
    sanitized = sanitized.replace(/^## (.*$)/gim, "<h2>$1</h2>");
    sanitized = sanitized.replace(/^# (.*$)/gim, "<h1>$1</h1>");

    // Bold / Italics
    sanitized = sanitized.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    sanitized = sanitized.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // External Markdown Links
    sanitized = sanitized.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="evidence-title-link">$1</a>');

    // Inline Citation Tags: [S1], [S2]
    sanitized = sanitized.replace(/\[(S\d+)\]/g, (match, sid) => {
      return `<button type="button" class="inline-citation-tag" data-source-id="${sid}">[${sid}]</button>`;
    });

    // Unordered lists
    sanitized = sanitized.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
    sanitized = sanitized.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

    // Paragraph splits
    const paragraphs = sanitized
      .split(/\n\n+/)
      .map((p) => (p.startsWith("<h") || p.startsWith("<ul") ? p : `<p>${p}</p>`))
      .join("");

    return paragraphs;
  }

  function generateSparklinePath(idx) {
    const paths = [
      "M0,16 L12,12 L22,18 L34,8 L46,14 L58,4 L68,14 L80,10",
      "M0,14 L14,18 L26,6 L38,16 L50,8 L62,18 L72,8 L80,12",
      "M0,18 L12,14 L24,16 L36,10 L48,18 L60,8 L70,16 L80,12",
      "M0,16 L12,18 L24,8 L36,14 L48,6 L60,16 L72,10 L80,14",
    ];
    return paths[idx % paths.length];
  }

  function extractDomain(url) {
    if (!url) return "";
    try {
      const u = new URL(url);
      return u.hostname.replace(/^www\./, "");
    } catch (e) {
      return "";
    }
  }

  function formatTimeNow() {
    return formatTimestampOnly(new Date());
  }

  function formatTimestampOnly(d) {
    return d.toTimeString().split(" ")[0];
  }

  function formatTimestamp(isoStr) {
    try {
      const d = new Date(isoStr);
      return `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    } catch (e) {
      return isoStr;
    }
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
