(function () {
  "use strict";

  const DEBOUNCE_MS = 600;

  const state = {
    decisions: [],
    selectedDecisionId: null,
    decideTargetOptionId: null,
    decisionTimers: new Map(),
    optionTimers: new Map(),
    saveIndicatorTimeout: null
  };

  // DOM Elements
  const decisionListEl = document.getElementById("decision-list");
  const newDecisionBtn = document.getElementById("new-decision-btn");
  const emptyStateEl = document.getElementById("empty-state");
  const decisionDetailEl = document.getElementById("decision-detail");
  const decisionTitleInput = document.getElementById("decision-title");
  const decisionNotesInput = document.getElementById("decision-notes");
  const decisionStatusBadge = document.getElementById("decision-status-badge");
  const saveIndicatorEl = document.getElementById("save-indicator");
  const deleteDecisionBtn = document.getElementById("delete-decision-btn");
  const decidedBannerEl = document.getElementById("decided-banner");
  const decidedOptionNameEl = document.getElementById("decided-option-name");
  const decidedReasonTextEl = document.getElementById("decided-reason-text");
  const reopenDecisionBtn = document.getElementById("reopen-decision-btn");
  const errorBannerEl = document.getElementById("error-banner");
  const addOptionBtn = document.getElementById("add-option-btn");
  const optionsEmptyEl = document.getElementById("options-empty");
  const optionsGridEl = document.getElementById("options-grid");

  // Modal Elements
  const decideModalEl = document.getElementById("decide-modal");
  const decideModalDescEl = document.getElementById("decide-modal-desc");
  const decideReasonInput = document.getElementById("decide-reason-input");
  const decideCancelBtn = document.getElementById("decide-cancel-btn");
  const decideConfirmBtn = document.getElementById("decide-confirm-btn");

  // Helpers
  function getSelectedDecision() {
    if (state.selectedDecisionId == null) return null;
    return state.decisions.find((d) => d.id === state.selectedDecisionId) || null;
  }

  function showError(message) {
    if (!message) {
      errorBannerEl.hidden = true;
      errorBannerEl.textContent = "";
      return;
    }
    errorBannerEl.textContent = message;
    errorBannerEl.hidden = false;
  }

  function setSaveStatus(status, customText) {
    if (state.saveIndicatorTimeout) {
      clearTimeout(state.saveIndicatorTimeout);
      state.saveIndicatorTimeout = null;
    }

    saveIndicatorEl.className = "save-indicator";
    if (status === "saving") {
      saveIndicatorEl.classList.add("is-saving");
      saveIndicatorEl.textContent = customText || "Kaydediliyor...";
    } else if (status === "saved") {
      saveIndicatorEl.classList.add("is-saved");
      saveIndicatorEl.textContent = customText || "Kaydedildi";
      state.saveIndicatorTimeout = setTimeout(() => {
        if (saveIndicatorEl.classList.contains("is-saved")) {
          saveIndicatorEl.textContent = "";
          saveIndicatorEl.className = "save-indicator";
        }
      }, 2500);
    } else if (status === "error") {
      saveIndicatorEl.classList.add("is-error");
      saveIndicatorEl.textContent = customText || "Kaydedilemedi";
    } else {
      saveIndicatorEl.textContent = "";
    }
  }

  async function apiRequest(path, options = {}) {
    const fetchOptions = {
      method: options.method || "GET",
      headers: {}
    };

    if (options.body !== undefined) {
      fetchOptions.headers["Content-Type"] = "application/json";
      fetchOptions.body = JSON.stringify(options.body);
    }

    const response = await fetch(path, fetchOptions);
    if (response.status === 204) {
      return null;
    }

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      const text = await response.text();
      try {
        data = text ? JSON.parse(text) : null;
      } catch (_err) {
        data = { error: text };
      }
    }

    if (!response.ok) {
      const errMsg = (data && data.error) ? data.error : `İstek başarısız oldu (${response.status})`;
      throw new Error(errMsg);
    }

    return data;
  }

  function normalizeDecision(raw) {
    return {
      id: raw.id,
      title: raw.title || "",
      notes: raw.notes || "",
      status: raw.status || "open",
      chosen_option_id: raw.chosen_option_id != null ? raw.chosen_option_id : null,
      decision_reason: raw.decision_reason || "",
      created_at: raw.created_at || "",
      decided_at: raw.decided_at || null,
      options: Array.isArray(raw.options) ? raw.options.map(normalizeOption) : []
    };
  }

  function normalizeOption(raw) {
    return {
      id: raw.id,
      decision_id: raw.decision_id,
      name: raw.name || "",
      gains: raw.gains || "",
      losses: raw.losses || "",
      risks: raw.risks || "",
      position: raw.position != null ? raw.position : 0
    };
  }

  function replaceDecisionInState(updatedRaw) {
    const index = state.decisions.findIndex((d) => d.id === updatedRaw.id);
    if (index === -1) return null;
    const existing = state.decisions[index];
    const normalized = normalizeDecision({
      ...existing,
      ...updatedRaw,
      options: Array.isArray(updatedRaw.options) ? updatedRaw.options : existing.options
    });
    state.decisions[index] = normalized;
    return normalized;
  }

  // Rendering: Left Sidebar Decision List
  function renderDecisionList() {
    decisionListEl.replaceChildren();

    if (state.decisions.length === 0) {
      const emptyMsg = document.createElement("div");
      emptyMsg.className = "decision-list-empty";
      emptyMsg.textContent = "Henüz kayıtlı bir karar yok.";
      decisionListEl.appendChild(emptyMsg);
      return;
    }

    state.decisions.forEach((decision) => {
      const itemBtn = document.createElement("button");
      itemBtn.type = "button";
      itemBtn.setAttribute("role", "listitem");
      itemBtn.className = "decision-item";
      itemBtn.dataset.decisionId = String(decision.id);
      if (decision.id === state.selectedDecisionId) {
        itemBtn.classList.add("is-active");
      }

      const topRow = document.createElement("div");
      topRow.className = "decision-item-top";

      const titleSpan = document.createElement("span");
      titleSpan.className = "decision-item-title";
      titleSpan.textContent = decision.title || "Adsız Karar";

      const badgeSpan = document.createElement("span");
      badgeSpan.className =
        "badge " + (decision.status === "decided" ? "badge-decided" : "badge-open");
      badgeSpan.textContent = decision.status === "decided" ? "Verilmiş" : "Açık";

      topRow.appendChild(titleSpan);
      topRow.appendChild(badgeSpan);

      const metaRow = document.createElement("div");
      metaRow.className = "decision-item-meta";

      const countSpan = document.createElement("span");
      const optCount = Array.isArray(decision.options) ? decision.options.length : 0;
      countSpan.textContent = `${optCount} seçenek`;

      metaRow.appendChild(countSpan);

      if (decision.status === "decided" && decision.chosen_option_id != null) {
        const chosenOpt = (decision.options || []).find(
          (o) => o.id === decision.chosen_option_id
        );
        if (chosenOpt) {
          const chosenSpan = document.createElement("span");
          chosenSpan.textContent = `✓ ${chosenOpt.name}`;
          metaRow.appendChild(chosenSpan);
        }
      }

      itemBtn.appendChild(topRow);
      itemBtn.appendChild(metaRow);

      itemBtn.addEventListener("click", () => {
        if (state.selectedDecisionId !== decision.id) {
          selectDecision(decision.id);
        }
      });

      decisionListEl.appendChild(itemBtn);
    });
  }

  // Update only header badges and decided banner without destroying option card inputs
  function renderDecisionHeaderState(decision) {
    const isDecided = decision.status === "decided";
    decisionStatusBadge.className =
      "badge " + (isDecided ? "badge-decided" : "badge-open");
    decisionStatusBadge.textContent = isDecided ? "Karar Verildi" : "Açık Karar";

    if (isDecided) {
      const chosenOption = (decision.options || []).find(
        (opt) => opt.id === decision.chosen_option_id
      );
      decidedOptionNameEl.textContent = chosenOption
        ? chosenOption.name
        : "Bir seçenek";
      if (decision.decision_reason && decision.decision_reason.trim()) {
        decidedReasonTextEl.textContent = `Neden: ${decision.decision_reason}`;
        decidedReasonTextEl.hidden = false;
      } else {
        decidedReasonTextEl.textContent = "Neden belirtilmedi.";
        decidedReasonTextEl.hidden = false;
      }
      decidedBannerEl.hidden = false;
    } else {
      decidedBannerEl.hidden = true;
      decidedOptionNameEl.textContent = "";
      decidedReasonTextEl.textContent = "";
    }
  }

  // Create a single Option Card DOM node
  function createOptionCardElement(decision, option) {
    const isChosen =
      decision.status === "decided" && decision.chosen_option_id === option.id;

    const card = document.createElement("article");
    card.className = "option-card" + (isChosen ? " is-chosen" : "");
    card.dataset.optionId = String(option.id);

    // Header: option name input + chosen badge
    const header = document.createElement("div");
    header.className = "option-card-header";

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "option-name-input";
    nameInput.placeholder = "Seçenek adı";
    nameInput.setAttribute("aria-label", "Seçenek adı");
    nameInput.value = option.name;

    header.appendChild(nameInput);

    if (isChosen) {
      const chosenPill = document.createElement("span");
      chosenPill.className = "chosen-pill";
      chosenPill.textContent = "✓ Seçilen";
      header.appendChild(chosenPill);
    }

    card.appendChild(header);

    // 3 Textareas: Kazanacaklarım, Kaybedeceklerim, Riskler
    const fieldsConfig = [
      {
        key: "gains",
        label: "Kazanacaklarım",
        dotClass: "field-dot-gains",
        placeholder: "Bu seçeneği seçersem ne kazanırım?"
      },
      {
        key: "losses",
        label: "Kaybedeceklerim",
        dotClass: "field-dot-losses",
        placeholder: "Bu seçeneği seçersem ne kaybederim / neden vazgeçerim?"
      },
      {
        key: "risks",
        label: "Riskler",
        dotClass: "field-dot-risks",
        placeholder: "Olası riskler ve belirsizlikler neler?"
      }
    ];

    const textareas = {};

    fieldsConfig.forEach((field) => {
      const wrapper = document.createElement("div");
      wrapper.className = "option-field";

      const labelEl = document.createElement("label");
      labelEl.className = "option-field-label";
      const textareaId = `opt-${option.id}-${field.key}`;
      labelEl.setAttribute("for", textareaId);

      const dot = document.createElement("span");
      dot.className = `field-dot ${field.dotClass}`;
      dot.setAttribute("aria-hidden", "true");

      const labelText = document.createElement("span");
      labelText.textContent = field.label;

      labelEl.appendChild(dot);
      labelEl.appendChild(labelText);

      const textarea = document.createElement("textarea");
      textarea.id = textareaId;
      textarea.className = "option-textarea";
      textarea.rows = 3;
      textarea.placeholder = field.placeholder;
      textarea.value = option[field.key] || "";

      textareas[field.key] = textarea;

      wrapper.appendChild(labelEl);
      wrapper.appendChild(textarea);
      card.appendChild(wrapper);
    });

    // Wire up auto-save (debounce + blur) for Option fields
    const getDraftValues = () => ({
      name: nameInput.value,
      gains: textareas.gains.value,
      losses: textareas.losses.value,
      risks: textareas.risks.value
    });

    const handleOptionInput = () => {
      scheduleOptionSave(option.id, getDraftValues);
    };

    const handleOptionBlur = () => {
      if (!nameInput.value.trim()) {
        nameInput.value = option.name || "Seçenek";
      }
      flushOptionSave(option.id, getDraftValues());
    };

    nameInput.addEventListener("input", handleOptionInput);
    nameInput.addEventListener("blur", handleOptionBlur);

    Object.values(textareas).forEach((ta) => {
      ta.addEventListener("input", handleOptionInput);
      ta.addEventListener("blur", handleOptionBlur);
    });

    // Footer: "Bunu seç" button + "Sil" button
    const footer = document.createElement("div");
    footer.className = "option-card-footer";

    const decideBtn = document.createElement("button");
    decideBtn.type = "button";
    decideBtn.className = isChosen ? "btn btn-secondary" : "btn btn-success";
    decideBtn.textContent = isChosen ? "Seçildi (Nedeni düzenle)" : "Bunu seç";
    decideBtn.addEventListener("click", () => {
      openDecideModal(option.id);
    });

    const deleteOptBtn = document.createElement("button");
    deleteOptBtn.type = "button";
    deleteOptBtn.className = "btn-icon-danger";
    deleteOptBtn.textContent = "Sil";
    deleteOptBtn.title = "Seçeneği sil";
    deleteOptBtn.addEventListener("click", () => {
      handleDeleteOption(option.id, nameInput.value || option.name);
    });

    footer.appendChild(decideBtn);
    footer.appendChild(deleteOptBtn);
    card.appendChild(footer);

    return card;
  }

  function renderOptionsGrid(decision) {
    optionsGridEl.replaceChildren();
    const options = decision.options || [];

    if (options.length === 0) {
      optionsEmptyEl.hidden = false;
      optionsGridEl.hidden = true;
      return;
    }

    optionsEmptyEl.hidden = true;
    optionsGridEl.hidden = false;

    options.forEach((opt) => {
      const cardEl = createOptionCardElement(decision, opt);
      optionsGridEl.appendChild(cardEl);
    });
  }

  function renderSelectedDecision() {
    showError("");
    const decision = getSelectedDecision();

    if (!decision) {
      emptyStateEl.hidden = false;
      decisionDetailEl.hidden = true;
      return;
    }

    emptyStateEl.hidden = true;
    decisionDetailEl.hidden = false;

    decisionTitleInput.value = decision.title;
    decisionNotesInput.value = decision.notes;

    renderDecisionHeaderState(decision);
    renderOptionsGrid(decision);
  }

  // Auto-save logic for Decision (title + notes)
  function hasDecisionChanged(decision, draft) {
    const trimmedTitle = draft.title.trim();
    if (!trimmedTitle) return false;
    return trimmedTitle !== decision.title || draft.notes !== decision.notes;
  }

  function scheduleDecisionSave(decisionId) {
    if (state.decisionTimers.has(decisionId)) {
      clearTimeout(state.decisionTimers.get(decisionId));
    }
    setSaveStatus("saving");
    const timerId = setTimeout(() => {
      state.decisionTimers.delete(decisionId);
      if (state.selectedDecisionId === decisionId) {
        flushDecisionSave(decisionId, {
          title: decisionTitleInput.value,
          notes: decisionNotesInput.value
        });
      }
    }, DEBOUNCE_MS);
    state.decisionTimers.set(decisionId, timerId);
  }

  async function flushDecisionSave(decisionId, draft) {
    if (state.decisionTimers.has(decisionId)) {
      clearTimeout(state.decisionTimers.get(decisionId));
      state.decisionTimers.delete(decisionId);
    }

    const decision = state.decisions.find((d) => d.id === decisionId);
    if (!decision) return;

    const trimmedTitle = draft.title.trim();
    if (!trimmedTitle) {
      if (state.selectedDecisionId === decisionId) {
        decisionTitleInput.value = decision.title;
      }
      setSaveStatus("idle");
      return;
    }

    if (!hasDecisionChanged(decision, draft)) {
      if (saveIndicatorEl.classList.contains("is-saving")) {
        setSaveStatus("saved");
      }
      return;
    }

    setSaveStatus("saving");
    showError("");

    try {
      const updated = await apiRequest(`/api/decisions/${decisionId}`, {
        method: "PUT",
        body: {
          title: trimmedTitle,
          notes: draft.notes
        }
      });
      replaceDecisionInState(updated);
      renderDecisionList();
      setSaveStatus("saved");
    } catch (err) {
      setSaveStatus("error");
      showError(err.message || "Karar kaydedilirken hata oluştu.");
    }
  }

  // Auto-save logic for Option (name, gains, losses, risks)
  function findOptionById(optionId) {
    for (const decision of state.decisions) {
      const found = (decision.options || []).find((o) => o.id === optionId);
      if (found) return { decision, option: found };
    }
    return null;
  }

  function hasOptionChanged(option, draft) {
    const trimmedName = draft.name.trim();
    if (!trimmedName) return false;
    return (
      trimmedName !== option.name ||
      draft.gains !== option.gains ||
      draft.losses !== option.losses ||
      draft.risks !== option.risks
    );
  }

  function scheduleOptionSave(optionId, getDraftFn) {
    if (state.optionTimers.has(optionId)) {
      clearTimeout(state.optionTimers.get(optionId));
    }
    setSaveStatus("saving");
    const timerId = setTimeout(() => {
      state.optionTimers.delete(optionId);
      flushOptionSave(optionId, getDraftFn());
    }, DEBOUNCE_MS);
    state.optionTimers.set(optionId, timerId);
  }

  async function flushOptionSave(optionId, draft) {
    if (state.optionTimers.has(optionId)) {
      clearTimeout(state.optionTimers.get(optionId));
      state.optionTimers.delete(optionId);
    }

    const match = findOptionById(optionId);
    if (!match) return;
    const { decision, option } = match;

    const trimmedName = draft.name.trim();
    if (!trimmedName) {
      setSaveStatus("idle");
      return;
    }

    if (!hasOptionChanged(option, draft)) {
      if (saveIndicatorEl.classList.contains("is-saving")) {
        setSaveStatus("saved");
      }
      return;
    }

    setSaveStatus("saving");
    showError("");

    try {
      const updatedOpt = await apiRequest(`/api/options/${optionId}`, {
        method: "PUT",
        body: {
          name: trimmedName,
          gains: draft.gains,
          losses: draft.losses,
          risks: draft.risks
        }
      });

      const normalizedOpt = normalizeOption(updatedOpt);
      const idx = decision.options.findIndex((o) => o.id === optionId);
      if (idx !== -1) {
        decision.options[idx] = normalizedOpt;
      }

      if (
        decision.status === "decided" &&
        decision.chosen_option_id === optionId &&
        state.selectedDecisionId === decision.id
      ) {
        renderDecisionHeaderState(decision);
      }
      renderDecisionList();
      setSaveStatus("saved");
    } catch (err) {
      setSaveStatus("error");
      showError(err.message || "Seçenek kaydedilirken hata oluştu.");
    }
  }

  // Actions
  async function selectDecision(decisionId) {
    if (state.selectedDecisionId != null) {
      const prevId = state.selectedDecisionId;
      if (state.decisionTimers.has(prevId)) {
        await flushDecisionSave(prevId, {
          title: decisionTitleInput.value,
          notes: decisionNotesInput.value
        });
      }
    }

    state.selectedDecisionId = decisionId;
    renderDecisionList();
    renderSelectedDecision();
  }

  async function handleCreateDecision() {
    newDecisionBtn.disabled = true;
    showError("");

    try {
      const created = await apiRequest("/api/decisions", {
        method: "POST",
        body: {
          title: "Yeni Karar",
          notes: ""
        }
      });
      const normalized = normalizeDecision(created);
      state.decisions.unshift(normalized);
      state.selectedDecisionId = normalized.id;
      renderDecisionList();
      renderSelectedDecision();
      setSaveStatus("saved", "Oluşturuldu");
      decisionTitleInput.focus();
      decisionTitleInput.select();
    } catch (err) {
      showError(err.message || "Yeni karar oluşturulamadı.");
    } finally {
      newDecisionBtn.disabled = false;
    }
  }

  async function handleDeleteDecision() {
    const decision = getSelectedDecision();
    if (!decision) return;

    const confirmed = window.confirm(
      `"${decision.title || "Adsız Karar"}" kararını ve tüm seçeneklerini silmek istediğinize emin misiniz?`
    );
    if (!confirmed) return;

    deleteDecisionBtn.disabled = true;
    showError("");

    try {
      await apiRequest(`/api/decisions/${decision.id}`, {
        method: "DELETE"
      });
      state.decisions = state.decisions.filter((d) => d.id !== decision.id);
      state.selectedDecisionId =
        state.decisions.length > 0 ? state.decisions[0].id : null;
      renderDecisionList();
      renderSelectedDecision();
    } catch (err) {
      showError(err.message || "Karar silinemedi.");
    } finally {
      deleteDecisionBtn.disabled = false;
    }
  }

  async function handleAddOption() {
    const decision = getSelectedDecision();
    if (!decision) return;

    addOptionBtn.disabled = true;
    showError("");

    const nextIndex = (decision.options ? decision.options.length : 0) + 1;
    const defaultName = `Seçenek ${nextIndex}`;

    try {
      const createdOpt = await apiRequest(
        `/api/decisions/${decision.id}/options`,
        {
          method: "POST",
          body: {
            name: defaultName,
            gains: "",
            losses: "",
            risks: ""
          }
        }
      );

      const normalizedOpt = normalizeOption(createdOpt);
      decision.options.push(normalizedOpt);

      optionsEmptyEl.hidden = true;
      optionsGridEl.hidden = false;

      const cardEl = createOptionCardElement(decision, normalizedOpt);
      optionsGridEl.appendChild(cardEl);
      renderDecisionList();
      setSaveStatus("saved", "Seçenek eklendi");

      const nameInput = cardEl.querySelector(".option-name-input");
      if (nameInput) {
        nameInput.focus();
        nameInput.select();
      }
    } catch (err) {
      showError(err.message || "Seçenek eklenemedi.");
    } finally {
      addOptionBtn.disabled = false;
    }
  }

  async function handleDeleteOption(optionId, optionName) {
    const decision = getSelectedDecision();
    if (!decision) return;

    const confirmed = window.confirm(
      `"${optionName || "Bu seçenek"}" seçeneğini silmek istediğinize emin misiniz?`
    );
    if (!confirmed) return;

    showError("");

    if (state.optionTimers.has(optionId)) {
      clearTimeout(state.optionTimers.get(optionId));
      state.optionTimers.delete(optionId);
    }

    try {
      await apiRequest(`/api/options/${optionId}`, {
        method: "DELETE"
      });

      const wasChosen = decision.chosen_option_id === optionId;
      decision.options = decision.options.filter((o) => o.id !== optionId);

      if (wasChosen) {
        decision.status = "open";
        decision.chosen_option_id = null;
        decision.decision_reason = "";
        decision.decided_at = null;
      }

      // Sync with backend in case server state updated decision fields
      try {
        const refreshed = await apiRequest(`/api/decisions/${decision.id}`);
        replaceDecisionInState(refreshed);
      } catch (_syncErr) {
        // Fallback to local state update already applied above
      }

      renderDecisionList();
      renderSelectedDecision();
      setSaveStatus("saved", "Seçenek silindi");
    } catch (err) {
      showError(err.message || "Seçenek silinemedi.");
    }
  }

  // Decide Modal & Reopen
  function openDecideModal(optionId) {
    const decision = getSelectedDecision();
    if (!decision) return;
    const option = (decision.options || []).find((o) => o.id === optionId);
    if (!option) return;

    state.decideTargetOptionId = optionId;
    decideModalDescEl.textContent = `"${option.name}" seçeneğini bu karar için seçmek üzeresiniz.`;
    decideReasonInput.value =
      decision.chosen_option_id === optionId ? decision.decision_reason : "";
    decideModalEl.hidden = false;
    decideReasonInput.focus();
  }

  function closeDecideModal() {
    state.decideTargetOptionId = null;
    decideModalEl.hidden = true;
    decideReasonInput.value = "";
  }

  async function handleConfirmDecide() {
    const decision = getSelectedDecision();
    const optionId = state.decideTargetOptionId;
    if (!decision || optionId == null) return;

    // If the option card had unsaved changes, flush them first
    if (state.optionTimers.has(optionId)) {
      const cardEl = optionsGridEl.querySelector(
        `[data-option-id="${optionId}"]`
      );
      if (cardEl) {
        const nameEl = cardEl.querySelector(".option-name-input");
        const gainsEl = document.getElementById(`opt-${optionId}-gains`);
        const lossesEl = document.getElementById(`opt-${optionId}-losses`);
        const risksEl = document.getElementById(`opt-${optionId}-risks`);
        await flushOptionSave(optionId, {
          name: nameEl ? nameEl.value : "",
          gains: gainsEl ? gainsEl.value : "",
          losses: lossesEl ? lossesEl.value : "",
          risks: risksEl ? risksEl.value : ""
        });
      }
    }

    decideConfirmBtn.disabled = true;
    showError("");

    try {
      const updated = await apiRequest(`/api/decisions/${decision.id}/decide`, {
        method: "POST",
        body: {
          option_id: optionId,
          reason: decideReasonInput.value.trim()
        }
      });

      replaceDecisionInState(updated);
      closeDecideModal();
      renderDecisionList();
      renderSelectedDecision();
      setSaveStatus("saved", "Karar kaydedildi");
    } catch (err) {
      showError(err.message || "Karar kaydedilemedi.");
    } finally {
      decideConfirmBtn.disabled = false;
    }
  }

  async function handleReopenDecision() {
    const decision = getSelectedDecision();
    if (!decision) return;

    reopenDecisionBtn.disabled = true;
    showError("");

    try {
      const updated = await apiRequest(`/api/decisions/${decision.id}/reopen`, {
        method: "POST"
      });
      replaceDecisionInState(updated);
      renderDecisionList();
      renderSelectedDecision();
      setSaveStatus("saved", "Yeniden açıldı");
    } catch (err) {
      showError(err.message || "Karar yeniden açılamadı.");
    } finally {
      reopenDecisionBtn.disabled = false;
    }
  }

  // Initial Load
  async function loadDecisions() {
    showError("");
    try {
      const list = await apiRequest("/api/decisions");
      state.decisions = Array.isArray(list) ? list.map(normalizeDecision) : [];
      if (state.decisions.length > 0 && state.selectedDecisionId == null) {
        state.selectedDecisionId = state.decisions[0].id;
      }
      renderDecisionList();
      renderSelectedDecision();
    } catch (err) {
      renderDecisionList();
      renderSelectedDecision();
      showError(err.message || "Kararlar yüklenirken bir hata oluştu.");
    }
  }

  // Event Listeners
  newDecisionBtn.addEventListener("click", handleCreateDecision);
  deleteDecisionBtn.addEventListener("click", handleDeleteDecision);
  addOptionBtn.addEventListener("click", handleAddOption);
  reopenDecisionBtn.addEventListener("click", handleReopenDecision);

  decisionTitleInput.addEventListener("input", () => {
    if (state.selectedDecisionId != null) {
      scheduleDecisionSave(state.selectedDecisionId);
    }
  });

  decisionTitleInput.addEventListener("blur", () => {
    const decision = getSelectedDecision();
    if (!decision) return;
    if (!decisionTitleInput.value.trim()) {
      decisionTitleInput.value = decision.title || "Yeni Karar";
    }
    flushDecisionSave(decision.id, {
      title: decisionTitleInput.value,
      notes: decisionNotesInput.value
    });
  });

  decisionNotesInput.addEventListener("input", () => {
    if (state.selectedDecisionId != null) {
      scheduleDecisionSave(state.selectedDecisionId);
    }
  });

  decisionNotesInput.addEventListener("blur", () => {
    const decision = getSelectedDecision();
    if (!decision) return;
    flushDecisionSave(decision.id, {
      title: decisionTitleInput.value,
      notes: decisionNotesInput.value
    });
  });

  decideCancelBtn.addEventListener("click", closeDecideModal);
  decideConfirmBtn.addEventListener("click", handleConfirmDecide);

  decideModalEl.addEventListener("click", (e) => {
    if (e.target === decideModalEl) {
      closeDecideModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !decideModalEl.hidden) {
      closeDecideModal();
    }
  });

  // Initialize
  loadDecisions();
})();
