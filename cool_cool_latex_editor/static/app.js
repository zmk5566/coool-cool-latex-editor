"use strict";

const state = {
  article: null,
  activeBlockId: null,
  dirty: false,
  author:
    localStorage.getItem("cool-cool-latex-editor.author") ||
    localStorage.getItem("cool-cool-editor.author") ||
    "",
  drawerOpen: false,
  commentView: "all",
  passageBlockId: null,
  selectedQuote: "",
  selectedPrefix: "",
  selectedSuffix: "",
  selectionRange: null,
  selectionProtected: false,
  selectedHighlightId: null,
  contextBlockId: null,
  contextPoint: { x: 0, y: 0 },
  displayMode:
    localStorage.getItem("cool-cool-latex-editor.display-mode") ||
    localStorage.getItem("cool-cool-editor.display-mode") ||
    "reading",
  outlineActiveBlockId: null,
  showAddressed: false,
  sourceHash: "",
  sourcePath: "",
  sourceLine: 1,
  sourceDirty: false,
  citationBlockId: null,
  citationTokenIndex: null,
  citationBibDraft: {},
  citationDirty: false,
  saving: false,
  externalHash: "",
  dismissedExternalHash: "",
  statusChecking: false,
  pendingWrites: 0,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const els = {
  app: $("#editor-app"),
  article: $("#article-content"),
  articleStage: $("#article-stage"),
  outlineList: $("#outline-list"),
  bubbleRail: $("#bubble-rail"),
  fileName: $("#file-name"),
  authorButton: $("#author-button"),
  authorName: $("#author-name"),
  commentsButton: $("#comments-button"),
  overallCommentButton: $("#overall-comment-button"),
  commentCount: $("#comment-count"),
  displayButton: $("#display-button"),
  displayLabel: $("#display-label"),
  displayMenu: $("#display-menu"),
  sourceButton: $("#source-button"),
  saveButton: $("#save-button"),
  drawer: $("#comment-drawer"),
  drawerClose: $("#drawer-close"),
  drawerScrim: $("#drawer-scrim"),
  drawerContext: $("#drawer-context"),
  commentList: $("#comment-list"),
  addressedToggle: $("#addressed-toggle"),
  addressedCount: $("#addressed-count"),
  commentForm: $("#comment-form"),
  commentInput: $("#comment-input"),
  commentLabel: $("#comment-label"),
  composerQuote: $("#composer-quote"),
  composerAuthor: $("#composer-author"),
  selectionComment: $("#selection-comment"),
  contextMenu: $("#context-menu"),
  contextEdit: $("#context-edit"),
  contextEditLabel: $("#context-edit-label"),
  contextComment: $("#context-comment"),
  contextCommentLabel: $("#context-comment-label"),
  contextHighlight: $("#context-highlight"),
  contextHighlightLabel: $("#context-highlight-label"),
  contextHint: $("#context-hint"),
  selectionEditor: $("#selection-editor"),
  selectionEditorClose: $("#selection-editor-close"),
  selectionEditInput: $("#selection-edit-input"),
  selectionEditCancel: $("#selection-edit-cancel"),
  selectionEditApply: $("#selection-edit-apply"),
  identityDialog: $("#identity-dialog"),
  identityForm: $("#identity-form"),
  identityInput: $("#identity-input"),
  citationDialog: $("#citation-dialog"),
  citationForm: $("#citation-form"),
  citationLocation: $("#citation-location"),
  citationCommand: $("#citation-command"),
  citationOptions: $("#citation-options"),
  citationKeys: $("#citation-keys"),
  citationSave: $("#citation-save"),
  bibEditorCount: $("#bib-editor-count"),
  bibEditorList: $("#bib-editor-list"),
  sourceDialog: $("#source-dialog"),
  sourceForm: $("#source-form"),
  sourceFileSelect: $("#source-file-select"),
  sourceLocation: $("#source-location"),
  sourceEditor: $("#source-editor"),
  sourceSave: $("#source-save"),
  externalChangeBanner: $("#external-change-banner"),
  externalChangeMessage: $("#external-change-message"),
  externalChangeLater: $("#external-change-later"),
  externalChangeReload: $("#external-change-reload"),
  toast: $("#toast"),
};

let toastTimer = null;
let outlineFrame = null;

async function api(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const mutating = !["GET", "HEAD"].includes(method);
  if (mutating) state.pendingWrites += 1;
  const headers = options.body
    ? { "Content-Type": "application/json", ...(options.headers || {}) }
    : options.headers;
  try {
    const response = await fetch(path, { ...options, headers });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    if (!response.ok) {
      const message = payload && payload.message ? payload.message : "Request failed (" + response.status + ")";
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload;
  } finally {
    if (mutating) state.pendingWrites = Math.max(0, state.pendingWrites - 1);
  }
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.toggle("is-error", isError);
  els.toast.classList.add("is-visible");
  toastTimer = window.setTimeout(() => {
    els.toast.classList.remove("is-visible");
  }, 2600);
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
}

function setDirty(dirty) {
  state.dirty = dirty;
  els.saveButton.textContent = dirty ? "Save changes" : "Saved";
  els.saveButton.classList.toggle("is-clean", !dirty);
  updateBeforeUnload();
  if (state.externalHash) renderExternalChange();
}

function hasUnsavedChanges() {
  return state.dirty || state.sourceDirty || state.citationDirty;
}

function updateBeforeUnload() {
  window.onbeforeunload = hasUnsavedChanges() ? () => true : null;
}

function hideExternalChange() {
  els.externalChangeBanner.hidden = true;
}

function renderExternalChange() {
  const unsaved = hasUnsavedChanges();
  els.externalChangeMessage.textContent = unsaved
    ? "The local file changed while you have unsaved edits. Reloading will discard them."
    : "Detected an update to the local file. Reload the latest version?";
  els.externalChangeReload.textContent = unsaved ? "Discard & reload" : "Reload";
  els.externalChangeBanner.hidden = false;
}

async function checkExternalUpdate({ force = false } = {}) {
  if (
    !state.article ||
    state.saving ||
    state.pendingWrites > 0 ||
    state.statusChecking ||
    (document.hidden && !force)
  ) {
    return;
  }
  state.statusChecking = true;
  try {
    const status = await api("/api/status");
    if (state.saving || state.pendingWrites > 0 || !state.article) return;
    if (status.hash === state.article.hash) {
      state.externalHash = "";
      state.dismissedExternalHash = "";
      hideExternalChange();
      return;
    }
    if (status.hash === state.dismissedExternalHash) return;
    state.externalHash = status.hash;
    renderExternalChange();
  } catch (_error) {
    // A transient status failure should not interrupt writing; the next poll retries.
  } finally {
    state.statusChecking = false;
  }
}

function dismissExternalChange() {
  state.dismissedExternalHash = state.externalHash;
  state.externalHash = "";
  hideExternalChange();
}

async function reloadExternalChange() {
  if (!state.article || state.saving) return;
  state.saving = true;
  setBusy(els.externalChangeReload, true);
  try {
    const payload = await api("/api/article");
    state.activeBlockId = null;
    state.selectionRange = null;
    state.selectedHighlightId = null;
    state.sourceDirty = false;
    state.citationDirty = false;
    updateBeforeUnload();
    if (els.sourceDialog.open) els.sourceDialog.close();
    if (els.citationDialog.open) els.citationDialog.close();
    applyArticle(payload);
    showToast("Reloaded the latest LaTeX from disk.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    state.saving = false;
    setBusy(els.externalChangeReload, false);
  }
}

function setAuthor(name) {
  state.author = name.trim();
  localStorage.setItem("cool-cool-latex-editor.author", state.author);
  els.authorName.textContent = state.author || "Choose name";
  els.composerAuthor.textContent = state.author || "choose a name";
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function positionFloating(element, x, y, width = 240, height = 140) {
  const left = Math.max(8, Math.min(window.innerWidth - width - 8, x));
  const top = Math.max(8, Math.min(window.innerHeight - height - 8, y));
  element.style.left = left + "px";
  element.style.top = top + "px";
}

function hideDisplayMenu() {
  els.displayMenu.hidden = true;
  els.displayButton.setAttribute("aria-expanded", "false");
}

function setDisplayMode(mode, { persist = true } = {}) {
  state.displayMode = mode === "bubbles" ? "bubbles" : "reading";
  if (persist) {
    localStorage.setItem("cool-cool-latex-editor.display-mode", state.displayMode);
  }
  const bubbles = state.displayMode === "bubbles";
  els.app.classList.toggle("bubble-mode", bubbles);
  els.displayLabel.textContent = bubbles ? "Bubbles" : "Reading";
  for (const option of $$("[data-display-mode]")) {
    option.setAttribute("aria-checked", String(option.dataset.displayMode === state.displayMode));
  }
  hideDisplayMenu();
  window.requestAnimationFrame(renderBubbles);
}

function blockText(block) {
  return block.runs.map((run) => run.text || "").join("").replace(/\s+/g, " ").trim();
}

function setOutlineActive(blockId) {
  state.outlineActiveBlockId = blockId;
  for (const button of $$("[data-outline-block-id]", els.outlineList)) {
    const active = button.dataset.outlineBlockId === blockId;
    button.classList.toggle("is-active", active);
    if (active) {
      button.setAttribute("aria-current", "location");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

function updateOutlineActive() {
  const buttons = $$("[data-outline-block-id]", els.outlineList);
  if (!buttons.length) return;
  const threshold = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-height")) + 54;
  let activeId = buttons[0].dataset.outlineBlockId;
  for (const button of buttons) {
    const row = $('.article-block[data-block-id="' + CSS.escape(button.dataset.outlineBlockId) + '"]');
    if (!row || row.getBoundingClientRect().top > threshold) break;
    activeId = button.dataset.outlineBlockId;
  }
  if (activeId !== state.outlineActiveBlockId) setOutlineActive(activeId);
}

function scheduleOutlineUpdate() {
  if (outlineFrame) return;
  outlineFrame = window.requestAnimationFrame(() => {
    outlineFrame = null;
    updateOutlineActive();
  });
}

function jumpToOutlineBlock(blockId) {
  const row = $('.article-block[data-block-id="' + CSS.escape(blockId) + '"]');
  if (!row) return;
  setOutlineActive(blockId);
  row.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    block: "start",
  });
}

function referenceDomId(key) {
  return "reference-" + encodeURIComponent(key).replaceAll("%", "_");
}

function referencesForKeys(keys) {
  if (!state.article || !Array.isArray(state.article.references)) return [];
  const wanted = new Set(keys || []);
  return state.article.references.filter((entry) => wanted.has(entry.key));
}

function jumpToReferences(keys) {
  const entries = referencesForKeys(keys);
  const rows = entries
    .map((entry) => document.getElementById(referenceDomId(entry.key)))
    .filter(Boolean);
  if (!rows.length) return;
  rows[0].scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    block: "center",
  });
  for (const row of rows) row.classList.add("is-citation-target");
  window.setTimeout(() => {
    for (const row of rows) row.classList.remove("is-citation-target");
  }, 2600);
}

function renderOutline() {
  if (!state.article) return;
  const structuralBlocks = state.article.blocks.filter((block) => {
    return (
      block.kind === "title" ||
      block.kind === "abstract-heading" ||
      block.kind === "heading"
    );
  });
  const items = structuralBlocks.map((block) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "outline-item" +
      (block.kind === "title" ? " is-title" : "") +
      (block.heading_level ? " is-level-" + block.heading_level : "");
    button.dataset.outlineBlockId = block.id;
    button.textContent = blockText(block);
    button.title = blockText(block);
    button.addEventListener("click", () => jumpToOutlineBlock(block.id));
    return button;
  });
  if (Array.isArray(state.article.references) && state.article.references.length) {
    const references = document.createElement("button");
    references.type = "button";
    references.className = "outline-item is-level-1";
    references.dataset.outlineBlockId = "__references__";
    references.textContent = "References";
    references.title = state.article.references.length + " cited references";
    references.addEventListener("click", () => jumpToOutlineBlock("__references__"));
    items.push(references);
  }
  els.outlineList.replaceChildren(...items);
  window.requestAnimationFrame(updateOutlineActive);
}

function createToken(run, block, isEditing) {
  const citedReferences = run.kind === "citation" && run.citation
    ? referencesForKeys(run.citation.keys)
    : [];
  const citationButton = run.kind === "citation" && (isEditing || citedReferences.length);
  const token = document.createElement(citationButton ? "button" : "span");
  if (citationButton) token.type = "button";
  token.className = "protected-token " + run.kind;
  if (run.unresolved) token.classList.add("is-unresolved");
  token.dataset.tokenIndex = String(run.index);
  token.contentEditable = "false";
  token.textContent = run.text;
  token.title = run.tooltip || "Protected LaTeX: edit in Source mode";
  if (run.kind === "citation") {
    token.classList.toggle("is-editable", isEditing);
    token.classList.toggle("is-reference-link", !isEditing && citedReferences.length > 0);
    token.tabIndex = citationButton ? 0 : -1;
    token.setAttribute("role", citationButton ? "button" : "note");
    const referenceNumbers = citedReferences.map((entry) => `[${entry.index}]`).join(", ");
    token.setAttribute(
      "aria-label",
      isEditing
        ? "Edit citation " + run.text
        : referenceNumbers
          ? "View references " + referenceNumbers + " for citation " + run.text
          : "Citation " + run.text
    );
    if (isEditing) {
      token.title = "Edit citation and referenced BibTeX fields";
      const open = (event) => {
        event.preventDefault();
        event.stopPropagation();
        openCitationEditor(block.id, run.index);
      };
      token.addEventListener("click", open);
      token.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") open(event);
      });
    } else if (citedReferences.length) {
      token.title = run.tooltip + "\nReferences " + referenceNumbers;
      const jump = (event) => {
        event.preventDefault();
        event.stopPropagation();
        jumpToReferences(run.citation.keys);
      };
      token.addEventListener("click", jump);
      token.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") jump(event);
      });
    }
  }
  return token;
}

function fillRuns(container, block, isEditing) {
  for (const run of block.runs) {
    if (run.type === "token") {
      container.append(createToken(run, block, isEditing));
    } else {
      container.append(document.createTextNode(run.text));
    }
  }
}

function focusAtEnd(element) {
  element.focus();
  const range = document.createRange();
  range.selectNodeContents(element);
  range.collapse(false);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

function focusEditingBlock(blockId) {
  window.requestAnimationFrame(() => {
    const content = $('.article-block[data-block-id="' + CSS.escape(blockId) + '"] .editable-content');
    if (content) focusAtEnd(content);
  });
}

async function beginEditing(blockId) {
  if (state.saving) return;
  if (state.activeBlockId === blockId) return;
  if (state.activeBlockId && state.activeBlockId !== blockId) {
    if (state.dirty) {
      await saveActiveBlock(blockId);
      return;
    }
    state.activeBlockId = blockId;
    setDirty(false);
    renderArticle();
    focusEditingBlock(blockId);
    return;
  }
  state.activeBlockId = blockId;
  setDirty(false);
  renderArticle();
  focusEditingBlock(blockId);
}

function cancelEditing() {
  state.activeBlockId = null;
  setDirty(false);
  renderArticle();
}

function appendTextSegment(segments, value) {
  if (!value) return;
  const last = segments[segments.length - 1];
  if (last && last.type === "text") {
    last.value += value;
  } else {
    segments.push({ type: "text", value });
  }
}

function collectSegments(content) {
  const segments = [];

  function visit(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      appendTextSegment(segments, node.nodeValue || "");
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node;
    if (element.classList.contains("protected-token")) {
      segments.push({ type: "token", index: Number(element.dataset.tokenIndex) });
      return;
    }
    if (element.tagName === "BR") {
      appendTextSegment(segments, "\n");
      return;
    }
    for (const child of element.childNodes) visit(child);
    if (element !== content && (element.tagName === "DIV" || element.tagName === "P")) {
      appendTextSegment(segments, "\n");
    }
  }

  visit(content);
  return segments;
}

async function saveActiveBlock(nextBlockId = null) {
  if (!state.activeBlockId || !state.article || state.saving) {
    showToast("Everything is already saved.");
    return;
  }
  const row = $('.article-block[data-block-id="' + CSS.escape(state.activeBlockId) + '"]');
  const content = row ? $(".editable-content", row) : null;
  if (!content) return;

  state.saving = true;
  setBusy(els.saveButton, true);
  try {
    const payload = await api("/api/article/block", {
      method: "PUT",
      body: JSON.stringify({
        block_id: state.activeBlockId,
        segments: collectSegments(content),
        expected_hash: state.article.hash,
      }),
    });
    state.activeBlockId = nextBlockId;
    applyArticle(payload);
    if (nextBlockId) {
      focusEditingBlock(nextBlockId);
      showToast("Previous paragraph saved.");
    } else {
      showToast("Paragraph saved to LaTeX.");
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    state.saving = false;
    setBusy(els.saveButton, false);
  }
}

function editActions() {
  const actions = document.createElement("div");
  actions.className = "edit-actions";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", cancelEditing);

  const save = document.createElement("button");
  save.type = "button";
  save.className = "save-paragraph";
  save.textContent = "Save paragraph";
  save.addEventListener("click", () => saveActiveBlock());

  actions.append(cancel, save);
  return actions;
}

function renderBlock(block) {
  const row = document.createElement("div");
  row.className = "article-block " + block.kind;
  row.dataset.blockId = block.id;
  if (block.source_path) row.dataset.sourcePath = block.source_path;
  if (block.heading_level) row.dataset.headingLevel = String(block.heading_level);

  const content = document.createElement("div");
  content.className = "editable-content";
  const canEdit = block.editable !== false;
  content.tabIndex = canEdit ? 0 : -1;
  const sourceLocation = block.source_path
    ? block.source_path + ":" + block.line_start + "–" + block.line_end
    : "the LaTeX source";
  content.setAttribute(
    "aria-label",
    (canEdit ? "Edit " : "Read ") + block.kind + " in " + sourceLocation
  );
  content.title = "Source: " + sourceLocation;
  const isEditing = canEdit && state.activeBlockId === block.id;
  fillRuns(content, block, isEditing);
  if (isEditing) {
    row.classList.add("is-editing");
    content.contentEditable = "true";
    content.spellcheck = true;
    content.setAttribute("role", "textbox");
    content.addEventListener("input", () => setDirty(true));
    content.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cancelEditing();
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "enter") {
        event.preventDefault();
        saveActiveBlock();
      } else if (
        event.key === "Enter" &&
        ["title", "subtitle", "heading"].includes(block.kind)
      ) {
        event.preventDefault();
        saveActiveBlock();
      }
    });
    content.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = event.clipboardData.getData("text/plain");
      const selection = window.getSelection();
      if (!selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const node = document.createTextNode(text);
      range.insertNode(node);
      range.setStartAfter(node);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      setDirty(true);
    });
  } else if (canEdit) {
    content.addEventListener("click", () => {
      const selection = window.getSelection();
      if (selection && !selection.isCollapsed && selection.toString().trim()) return;
      beginEditing(block.id);
    });
    content.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        beginEditing(block.id);
      }
    });
  }

  row.append(content);
  if (isEditing) row.append(editActions());

  if (block.comment_count > 0) {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "comment-marker";
    marker.textContent = String(block.comment_count);
    marker.setAttribute(
      "aria-label",
      block.comment_count + " open comment" + (block.comment_count === 1 ? "" : "s")
    );
    marker.addEventListener("click", (event) => {
      event.stopPropagation();
      openPassageComments(block.id);
    });
    row.append(marker);
  }
  return row;
}

function appendReferencePart(container, text, className = "") {
  if (!text) return;
  const span = document.createElement("span");
  if (className) span.className = className;
  span.textContent = text;
  container.append(span);
}

function renderReferenceEntry(entry) {
  const item = document.createElement("li");
  item.className = "reference-entry" + (entry.missing ? " is-missing" : "");
  item.id = referenceDomId(entry.key);
  item.dataset.referenceKey = entry.key;
  item.title = "BibTeX key: " + entry.key;

  const number = document.createElement("span");
  number.className = "reference-number";
  number.textContent = `[${entry.index}]`;
  number.setAttribute("aria-hidden", "true");

  const body = document.createElement("div");
  body.className = "reference-body";
  if (entry.missing) {
    appendReferencePart(body, entry.key + ". ", "reference-authors");
    appendReferencePart(body, "BibTeX entry not found.", "reference-missing-note");
  } else {
    appendReferencePart(body, (entry.authors || entry.key) + ". ", "reference-authors");
    appendReferencePart(body, (entry.year || "n.d.") + ". ", "reference-year");
    appendReferencePart(body, (entry.reference_title || entry.key) + ". ", "reference-title");
    if (entry.venue) {
      appendReferencePart(
        body,
        (entry.entry_type === "inproceedings" ? "In " : "") + entry.venue,
        "reference-venue"
      );
      const volumeIssue = entry.volume
        ? " " + entry.volume + (entry.issue ? `, ${entry.issue}` : "")
        : entry.issue
          ? " " + entry.issue
          : "";
      appendReferencePart(body, volumeIssue + ". ");
    }
    const publication = [entry.publisher, entry.address].filter(Boolean).join(", ");
    appendReferencePart(body, publication ? publication + ". " : "");
    if (entry.article_number) {
      appendReferencePart(body, "Article " + entry.article_number + ". ");
    }
    appendReferencePart(body, entry.pages ? entry.pages + ". " : "");
    if (entry.doi || entry.url) {
      const link = document.createElement("a");
      link.className = "reference-link";
      const doi = entry.doi
        ? entry.doi.replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, "")
        : "";
      link.href = doi ? "https://doi.org/" + doi : entry.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = doi ? "https://doi.org/" + doi : entry.url;
      body.append(link);
    }
  }

  item.append(number, body);
  return item;
}

function renderReferences() {
  const references = state.article && Array.isArray(state.article.references)
    ? state.article.references
    : [];
  if (!references.length) return null;
  const section = document.createElement("section");
  section.className = "references-section article-block";
  section.dataset.blockId = "__references__";
  section.id = "references";
  section.setAttribute("aria-labelledby", "references-title");

  const heading = document.createElement("h2");
  heading.id = "references-title";
  heading.textContent = "References";
  const count = document.createElement("span");
  count.className = "references-count";
  count.textContent = references.length + (references.length === 1 ? " cited work" : " cited works");
  const list = document.createElement("ol");
  list.className = "references-list";
  list.setAttribute("aria-label", "ACM-style cited references");
  list.replaceChildren(...references.map(renderReferenceEntry));
  section.append(heading, count, list);
  return section;
}

function renderArticle() {
  if (!state.article) return;
  const fragment = document.createDocumentFragment();
  for (const block of state.article.blocks) {
    fragment.append(renderBlock(block));
  }
  const references = renderReferences();
  if (references) fragment.append(references);
  els.article.replaceChildren(fragment);
  renderOutline();
  window.requestAnimationFrame(() => {
    renderHighlights();
    renderBubbles();
  });
}

function openCommentCount() {
  if (!state.article) return 0;
  return state.article.comments.filter((comment) => comment.status === "open").length;
}

function addressedCount() {
  if (!state.article) return 0;
  return state.article.comments.filter((comment) => comment.status === "addressed").length;
}

function setDrawerOpen(open) {
  state.drawerOpen = open;
  els.app.classList.toggle("drawer-open", open);
  els.drawer.setAttribute("aria-hidden", String(!open));
  if (!open) hideSelectionButton();
}

function selectCommentView(view) {
  if (view === "passage" && !state.passageBlockId) return;
  state.commentView = view;
  state.showAddressed = false;
  if (view !== "passage") {
    state.selectedQuote = "";
    state.selectedPrefix = "";
    state.selectedSuffix = "";
  }
  renderComments();
}

function filteredComments() {
  if (!state.article) return [];
  let comments = state.article.comments.filter((comment) => {
    return state.showAddressed ? comment.status === "addressed" : comment.status === "open";
  });
  if (state.commentView === "passage") {
    comments = comments.filter((comment) => comment.target === state.passageBlockId);
  } else if (state.commentView === "overall") {
    comments = comments.filter((comment) => comment.scope === "document");
  }
  return comments;
}

function scrollToCommentTarget(target) {
  if (!target) return;
  const row = $('.article-block[data-block-id="' + CSS.escape(target) + '"]');
  if (row) {
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    const content = $(".editable-content", row);
    content.animate(
      [
        { backgroundColor: "#f7f0e3" },
        { backgroundColor: "transparent" },
      ],
      { duration: 900, easing: "ease-out" }
    );
  }
}

function commentCard(comment) {
  const card = document.createElement("article");
  card.className = "comment-card" + (comment.status === "addressed" ? " is-addressed" : "");

  const meta = document.createElement("div");
  meta.className = "comment-meta";
  const avatar = document.createElement("span");
  avatar.className = "comment-avatar";
  avatar.textContent = (comment.author || "?").slice(0, 1);
  const byline = document.createElement("span");
  byline.className = "comment-byline";
  const author = document.createElement("span");
  author.className = "comment-author";
  author.textContent = comment.author;
  const date = document.createElement("time");
  date.className = "comment-date";
  date.textContent = [formatDate(comment.created), comment.source_path]
    .filter(Boolean)
    .join(" · ");
  byline.append(author, date);
  meta.append(avatar, byline);
  card.append(meta);

  if (comment.quote) {
    const quote = document.createElement("blockquote");
    quote.className = "comment-quote";
    quote.textContent = "“" + comment.quote + "”";
    if (comment.target) {
      quote.tabIndex = 0;
      quote.addEventListener("click", () => scrollToCommentTarget(comment.target));
    }
    card.append(quote);
  }

  const body = document.createElement("p");
  body.className = "comment-body";
  body.textContent = comment.body;
  card.append(body);

  const action = document.createElement("button");
  action.type = "button";
  action.className = "comment-action";
  action.textContent = comment.status === "open" ? "Mark addressed" : "Reopen";
  action.addEventListener("click", () => {
    updateCommentStatus(
      comment.id,
      comment.status === "open" ? "addressed" : "open",
      action
    );
  });
  card.append(action);
  return card;
}

function quoteIndex(text, comment) {
  if (!comment.quote) return -1;
  const candidates = [];
  let cursor = text.indexOf(comment.quote);
  while (cursor >= 0) {
    let score = 0;
    if (comment.prefix && text.slice(0, cursor).endsWith(comment.prefix)) score += 2;
    if (
      comment.suffix &&
      text.slice(cursor + comment.quote.length).startsWith(comment.suffix)
    ) {
      score += 2;
    }
    candidates.push({ index: cursor, score });
    cursor = text.indexOf(comment.quote, cursor + 1);
  }
  if (!candidates.length) return -1;
  candidates.sort((left, right) => right.score - left.score);
  return candidates[0].index;
}

function domPointForOffset(container, offset) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let remaining = offset;
  let node = walker.nextNode();
  while (node) {
    const length = (node.nodeValue || "").length;
    if (remaining <= length) return { node, offset: remaining };
    remaining -= length;
    node = walker.nextNode();
  }
  return { node: container, offset: container.childNodes.length };
}

function renderHighlights() {
  if (!window.CSS || !CSS.highlights || typeof Highlight === "undefined") return;
  CSS.highlights.delete("editor-highlight-amber");
  if (!state.article || !Array.isArray(state.article.highlights)) return;

  const ranges = [];
  let unattached = 0;
  for (const highlight of state.article.highlights) {
    const row = $('.article-block[data-block-id="' + CSS.escape(highlight.target) + '"]');
    const content = row ? $(".editable-content", row) : null;
    if (!content) {
      unattached += 1;
      continue;
    }
    const text = content.textContent || "";
    const index = quoteIndex(text, highlight);
    if (index < 0) {
      unattached += 1;
      continue;
    }
    const start = domPointForOffset(content, index);
    const end = domPointForOffset(content, index + highlight.quote.length);
    const range = document.createRange();
    try {
      range.setStart(start.node, start.offset);
      range.setEnd(end.node, end.offset);
      ranges.push(range);
    } catch (_error) {
      unattached += 1;
    }
  }
  if (ranges.length) {
    CSS.highlights.set("editor-highlight-amber", new Highlight(...ranges));
  }
  els.app.dataset.unattachedHighlights = String(unattached);
}

function commentAnchorTop(comment) {
  const stageRect = els.articleStage.getBoundingClientRect();
  const fallback = $(".article-block.title") || $(".article-block");
  let row = fallback;
  if (comment.target) {
    row = $('.article-block[data-block-id="' + CSS.escape(comment.target) + '"]') || fallback;
  }
  if (!row) return 0;

  const content = $(".editable-content", row);
  const text = content ? content.textContent || "" : "";
  const index = content ? quoteIndex(text, comment) : -1;
  if (index >= 0) {
    const start = domPointForOffset(content, index);
    const end = domPointForOffset(content, index + comment.quote.length);
    const range = document.createRange();
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, end.offset);
    const rect = range.getBoundingClientRect();
    if (rect.height) return Math.max(0, rect.top - stageRect.top - 5);
  }
  return Math.max(0, row.getBoundingClientRect().top - stageRect.top);
}

function bubbleComment(comment) {
  const item = document.createElement("article");
  item.className = "bubble-comment";

  const meta = document.createElement("div");
  meta.className = "bubble-comment-meta";
  const author = document.createElement("span");
  author.className = "bubble-comment-author";
  const avatar = document.createElement("span");
  avatar.className = "bubble-comment-avatar";
  avatar.textContent = (comment.author || "?").slice(0, 1);
  const name = document.createElement("span");
  name.textContent = comment.author;
  author.append(avatar, name);
  const date = document.createElement("time");
  date.textContent = [formatDate(comment.created), comment.source_path]
    .filter(Boolean)
    .join(" · ");
  meta.append(author, date);
  item.append(meta);

  if (comment.quote) {
    const quote = document.createElement("blockquote");
    quote.textContent = "“" + comment.quote + "”";
    item.append(quote);
  }

  const body = document.createElement("p");
  body.textContent = comment.body;
  item.append(body);

  const action = document.createElement("button");
  action.type = "button";
  action.textContent = "Mark addressed";
  action.addEventListener("click", () => updateCommentStatus(comment.id, "addressed", action));
  item.append(action);
  return item;
}

function bubbleGroup(comments) {
  const target = comments[0].target;
  const group = document.createElement("section");
  group.className = "bubble-group";

  const header = document.createElement("div");
  header.className = "bubble-group-header";
  const label = document.createElement("span");
  label.textContent = target
    ? comments.length + " on this passage"
    : comments.length + " overall";
  const open = document.createElement("button");
  open.type = "button";
  open.textContent = "Open thread";
  open.addEventListener("click", () => {
    if (target) {
      openPassageComments(target);
    } else {
      state.commentView = "overall";
      state.selectedQuote = "";
      setDrawerOpen(true);
      renderComments();
    }
  });
  header.append(label, open);
  group.append(header, ...comments.map(bubbleComment));
  return group;
}

function renderBubbles() {
  els.bubbleRail.replaceChildren();
  if (
    state.displayMode !== "bubbles" ||
    !state.article ||
    window.matchMedia("(max-width: 1379px)").matches
  ) {
    return;
  }

  const openComments = state.article.comments.filter((comment) => comment.status === "open");
  const grouped = new Map();
  for (const comment of openComments) {
    const key = comment.target || "__overall__";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(comment);
  }

  const groups = Array.from(grouped.values())
    .map((comments) => ({ comments, top: commentAnchorTop(comments[0]) }))
    .sort((left, right) => left.top - right.top);

  let nextTop = 0;
  for (const entry of groups) {
    const group = bubbleGroup(entry.comments);
    const top = Math.max(entry.top, nextTop);
    group.style.top = top + "px";
    els.bubbleRail.append(group);
    nextTop = top + group.offsetHeight + 12;
  }
}

function renderComments() {
  if (!state.article) return;
  els.commentCount.textContent = String(openCommentCount());
  els.addressedCount.textContent = String(addressedCount());
  els.addressedToggle.textContent = state.showAddressed ? "Back to open comments" : "Show addressed ";
  if (!state.showAddressed) {
    const count = document.createElement("span");
    count.textContent = String(addressedCount());
    els.addressedToggle.append(count);
  }

  const passageTab = $('[data-comment-view="passage"]');
  passageTab.disabled = !state.passageBlockId;
  for (const tab of $$("[data-comment-view]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.commentView === state.commentView));
  }

  if (state.commentView === "passage") {
    els.drawerContext.textContent = "This passage";
    els.commentLabel.textContent = "Add a comment on this passage";
  } else if (state.commentView === "overall") {
    els.drawerContext.textContent = "Whole document";
    els.commentLabel.textContent = "Add an overall comment";
  } else {
    els.drawerContext.textContent = "Document";
    els.commentLabel.textContent = "Add an overall comment";
  }

  if (state.commentView === "passage" && state.selectedQuote) {
    els.composerQuote.hidden = false;
    els.composerQuote.textContent = "“" + state.selectedQuote + "”";
  } else {
    els.composerQuote.hidden = true;
    els.composerQuote.textContent = "";
  }

  const comments = filteredComments();
  if (!comments.length) {
    const empty = document.createElement("div");
    empty.className = "empty-comments";
    const title = document.createElement("strong");
    title.textContent = state.showAddressed ? "No addressed comments" : "No open comments here";
    const hint = document.createElement("span");
    hint.textContent =
      state.commentView === "passage"
        ? "Select text below to start a precise thread."
        : "A new note will be stored inside the LaTeX file.";
    empty.append(title, hint);
    els.commentList.replaceChildren(empty);
  } else {
    els.commentList.replaceChildren(...comments.map(commentCard));
  }
}

function applyArticle(payload) {
  state.article = payload;
  state.externalHash = "";
  state.dismissedExternalHash = "";
  hideExternalChange();
  const sourceCount = Array.isArray(payload.sources) ? payload.sources.length : 1;
  const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
  els.fileName.textContent =
    (payload.name || payload.path) +
    (sourceCount > 1 ? " · " + sourceCount + " files" : "") +
    (warnings.length
      ? " · " + warnings.length + " warning" + (warnings.length === 1 ? "" : "s")
      : "");
  const sourcePaths = Array.isArray(payload.sources)
    ? payload.sources.map((source) => source.path)
    : [payload.path];
  els.fileName.title = [
    "Loaded LaTeX sources:",
    ...sourcePaths,
    ...(warnings.length ? ["", "Warnings:", ...warnings] : []),
  ].join("\n");
  if (!state.author) {
    els.authorName.textContent = "Choose name";
    els.composerAuthor.textContent = "choose a name";
  }
  setDirty(false);
  renderArticle();
  renderComments();
  setDisplayMode(state.displayMode, { persist: false });
}

async function loadArticle() {
  try {
    const payload = await api("/api/article");
    applyArticle(payload);
    if (!state.author) {
      els.identityInput.value = (payload.git && payload.git.user) || "";
      els.identityDialog.showModal();
      window.setTimeout(() => els.identityInput.focus(), 0);
    } else {
      setAuthor(state.author);
    }
  } catch (error) {
    const message = document.createElement("div");
    message.className = "empty-comments";
    const title = document.createElement("strong");
    title.textContent = "The article could not be rendered.";
    const detail = document.createElement("span");
    detail.textContent = error.message;
    message.append(title, detail);
    els.article.replaceChildren(message);
    showToast(error.message, true);
  }
}

function ensureAuthor() {
  if (state.author) return true;
  els.identityDialog.showModal();
  window.setTimeout(() => els.identityInput.focus(), 0);
  return false;
}

function openPassageComments(blockId, quote = "", prefix = "", suffix = "") {
  state.passageBlockId = blockId;
  state.selectedQuote = quote;
  state.selectedPrefix = prefix;
  state.selectedSuffix = suffix;
  state.commentView = "passage";
  state.showAddressed = false;
  setDrawerOpen(true);
  renderComments();
}

function hideSelectionButton() {
  els.selectionComment.hidden = true;
}

function hideContextMenu() {
  els.contextMenu.hidden = true;
}

function hideSelectionEditor() {
  els.selectionEditor.hidden = true;
}

function elementFromNode(node) {
  if (!node) return null;
  return node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
}

function captureSelection(showButton = true) {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.rangeCount) {
    if (showButton) hideSelectionButton();
    return false;
  }
  const range = selection.getRangeAt(0);
  const start = elementFromNode(range.startContainer);
  const end = elementFromNode(range.endContainer);
  const startBlock = start ? start.closest(".article-block") : null;
  const endBlock = end ? end.closest(".article-block") : null;
  const quote = selection.toString().replace(/\s+/g, " ").trim();
  if (
    !startBlock ||
    startBlock !== endBlock ||
    !els.article.contains(startBlock) ||
    quote.length < 2
  ) {
    if (showButton) hideSelectionButton();
    return false;
  }

  const content = $(".editable-content", startBlock);
  const before = document.createRange();
  before.selectNodeContents(content);
  before.setEnd(range.startContainer, range.startOffset);
  const rawText = selection.toString();
  const leading = (rawText.match(/^\s*/) || [""])[0].length;
  const trailing = (rawText.match(/\s*$/) || [""])[0].length;
  const startOffset = before.toString().length + leading;
  const selectedLength = Math.max(0, rawText.length - leading - trailing);
  const fullText = content.textContent || "";
  const prefix = fullText.slice(Math.max(0, startOffset - 48), startOffset);
  const suffix = fullText.slice(startOffset + selectedLength, startOffset + selectedLength + 48);
  const protectedTokens = $$(".protected-token", content);
  const protectedSelection = protectedTokens.some((token) => range.intersectsNode(token));

  const rect = range.getBoundingClientRect();
  state.passageBlockId = startBlock.dataset.blockId;
  state.selectedQuote = quote.slice(0, 280);
  state.selectedPrefix = prefix.replace(/\s+/g, " ").slice(-48);
  state.selectedSuffix = suffix.replace(/\s+/g, " ").slice(0, 48);
  state.selectionRange = range.cloneRange();
  state.selectionProtected = protectedSelection;
  if (showButton) {
    els.selectionComment.style.left = Math.max(62, Math.min(window.innerWidth - 62, rect.left + rect.width / 2)) + "px";
    els.selectionComment.style.top = Math.max(52, rect.top - 8) + "px";
    els.selectionComment.hidden = false;
  }
  return true;
}

function matchingSelectionHighlight() {
  if (!state.article || !Array.isArray(state.article.highlights) || !state.selectedQuote) {
    return null;
  }
  return state.article.highlights.find((highlight) => {
    return (
      highlight.target === state.passageBlockId &&
      highlight.quote === state.selectedQuote &&
      (highlight.prefix || "") === state.selectedPrefix &&
      (highlight.suffix || "") === state.selectedSuffix
    );
  }) || null;
}

function showContextMenu(event, row) {
  if (!window.matchMedia("(pointer: fine)").matches) return;
  event.preventDefault();
  hideDisplayMenu();
  hideSelectionEditor();

  const captured = captureSelection(false);
  const selectionHere = captured && state.passageBlockId === row.dataset.blockId;
  state.contextBlockId = row.dataset.blockId;
  state.contextPoint = { x: event.clientX, y: event.clientY };
  if (!selectionHere) {
    state.selectionRange = null;
    state.selectionProtected = false;
    state.selectedQuote = "";
    state.selectedPrefix = "";
    state.selectedSuffix = "";
    state.selectedHighlightId = null;
  }

  const selectedHighlight = selectionHere ? matchingSelectionHighlight() : null;
  state.selectedHighlightId = selectedHighlight ? selectedHighlight.id : null;

  els.contextEditLabel.textContent = selectionHere ? "Edit selection" : "Edit paragraph";
  els.contextCommentLabel.textContent = selectionHere
    ? "Comment on selection"
    : "Comment on paragraph";
  els.contextHighlight.hidden = !selectionHere;
  els.contextHighlightLabel.textContent = selectedHighlight
    ? "Remove highlight by " + selectedHighlight.author
    : "Highlight selection";
  els.contextEdit.disabled = selectionHere && state.selectionProtected;
  els.contextHint.hidden = !(selectionHere && state.selectionProtected);
  positionFloating(els.contextMenu, event.clientX, event.clientY, 224, selectionHere ? 166 : 126);
  els.contextMenu.hidden = false;
}

function openSelectionEditor() {
  if (!state.selectionRange || state.selectionProtected) {
    showToast("This selection contains protected LaTeX. Use Source mode to change it.", true);
    return;
  }
  hideContextMenu();
  hideSelectionButton();
  els.selectionEditInput.value = state.selectionRange.toString();
  positionFloating(
    els.selectionEditor,
    state.contextPoint.x + 8,
    state.contextPoint.y + 8,
    360,
    220
  );
  els.selectionEditor.hidden = false;
  window.setTimeout(() => {
    els.selectionEditInput.focus();
    els.selectionEditInput.select();
  }, 0);
}

async function applySelectionEdit() {
  if (!state.selectionRange || !state.article || !state.contextBlockId || state.saving) return;
  const row = $('.article-block[data-block-id="' + CSS.escape(state.contextBlockId) + '"]');
  const content = row ? $(".editable-content", row) : null;
  if (!content || !state.selectionRange.commonAncestorContainer.isConnected) {
    hideSelectionEditor();
    showToast("That selection changed. Select it again and retry.", true);
    return;
  }

  const replacement = els.selectionEditInput.value;
  const range = state.selectionRange.cloneRange();
  range.deleteContents();
  const replacementNode = document.createTextNode(replacement);
  range.insertNode(replacementNode);
  hideSelectionEditor();
  state.saving = true;
  setBusy(els.saveButton, true);
  try {
    const payload = await api("/api/article/block", {
      method: "PUT",
      body: JSON.stringify({
        block_id: state.contextBlockId,
        segments: collectSegments(content),
        expected_hash: state.article.hash,
      }),
    });
    state.selectionRange = null;
    applyArticle(payload);
    showToast("Selection saved to LaTeX.");
  } catch (error) {
    renderArticle();
    showToast(error.message, true);
  } finally {
    state.saving = false;
    setBusy(els.saveButton, false);
  }
}

async function addComment(body) {
  if (!ensureAuthor() || !state.article) return;
  const inline = state.commentView === "passage" && state.passageBlockId;
  const previousIds = new Set(state.article.comments.map((comment) => comment.id));
  const submit = $(".send-button", els.commentForm);
  setBusy(submit, true);
  try {
    const payload = await api("/api/article/comments", {
      method: "POST",
      body: JSON.stringify({
        expected_hash: state.article.hash,
        author: state.author,
        body,
        scope: inline ? "inline" : "document",
        block_id: inline ? state.passageBlockId : null,
        quote: inline ? state.selectedQuote : null,
        prefix: inline ? state.selectedPrefix : null,
        suffix: inline ? state.selectedSuffix : null,
      }),
    });
    const added = payload.comments.find((comment) => !previousIds.has(comment.id));
    if (inline && added && added.target) state.passageBlockId = added.target;
    state.selectedQuote = "";
    state.selectedPrefix = "";
    state.selectedSuffix = "";
    els.commentInput.value = "";
    applyArticle(payload);
    showToast("Comment added to LaTeX.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(submit, false);
  }
}

async function updateCommentStatus(id, status, button) {
  if (!state.article) return;
  setBusy(button, true);
  try {
    const payload = await api("/api/article/comments/status", {
      method: "POST",
      body: JSON.stringify({
        expected_hash: state.article.hash,
        id,
        status,
      }),
    });
    applyArticle(payload);
    showToast(status === "addressed" ? "Comment marked addressed." : "Comment reopened.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function toggleSelectionHighlight() {
  if (!state.article || !state.contextBlockId || !state.selectedQuote || state.saving) return;
  const removing = Boolean(state.selectedHighlightId);
  if (!removing && !ensureAuthor()) return;

  hideContextMenu();
  hideSelectionButton();
  state.saving = true;
  setBusy(els.saveButton, true);
  try {
    const path = removing
      ? "/api/article/highlights/remove"
      : "/api/article/highlights";
    const body = removing
      ? {
          expected_hash: state.article.hash,
          id: state.selectedHighlightId,
        }
      : {
          expected_hash: state.article.hash,
          author: state.author,
          block_id: state.contextBlockId,
          quote: state.selectedQuote,
          prefix: state.selectedPrefix,
          suffix: state.selectedSuffix,
          tone: "amber",
        };
    const payload = await api(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.selectionRange = null;
    state.selectedHighlightId = null;
    window.getSelection().removeAllRanges();
    applyArticle(payload);
    showToast(removing ? "Highlight removed." : "Highlight saved in LaTeX metadata.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    state.saving = false;
    setBusy(els.saveButton, false);
  }
}

function blockById(blockId) {
  if (!state.article || !blockId) return null;
  return state.article.blocks.find((block) => block.id === blockId) || null;
}

function bibliographyByKey(key) {
  if (!state.article || !Array.isArray(state.article.bibliography)) return null;
  return state.article.bibliography.find((entry) => entry.key === key) || null;
}

function parsedCitationKeys() {
  return els.citationKeys.value
    .split(",")
    .map((key) => key.trim())
    .filter(Boolean);
}

function syncBibDraftFromForm() {
  for (const card of $$(".bib-entry-card[data-bib-key]", els.bibEditorList)) {
    const key = card.dataset.bibKey;
    state.citationBibDraft[key] = {
      key,
      author: $("[data-bib-field='author']", card).value,
      year: $("[data-bib-field='year']", card).value,
      title: $("[data-bib-field='title']", card).value,
    };
  }
}

function bibField(labelText, field, value, { wide = false } = {}) {
  const label = document.createElement("label");
  if (wide) label.className = "is-wide";
  const caption = document.createElement("span");
  caption.textContent = labelText;
  const input = document.createElement(field === "title" ? "textarea" : "input");
  input.dataset.bibField = field;
  input.value = value || "";
  if (input.tagName === "TEXTAREA") input.rows = 2;
  label.append(caption, input);
  return label;
}

function renderBibEditor() {
  const keys = parsedCitationKeys();
  const cards = keys.map((key) => {
    const entry = bibliographyByKey(key);
    if (!entry) {
      const missing = document.createElement("article");
      missing.className = "bib-entry-card is-missing";
      const title = document.createElement("strong");
      title.textContent = key;
      const detail = document.createElement("span");
      detail.textContent = "No loaded BibTeX entry. The citation can still be saved as unresolved.";
      missing.append(title, detail);
      return missing;
    }
    if (!state.citationBibDraft[key]) {
      state.citationBibDraft[key] = {
        key,
        author: entry.author || "",
        year: entry.year || "",
        title: entry.title || "",
      };
    }
    const draft = state.citationBibDraft[key];
    const card = document.createElement("article");
    card.className = "bib-entry-card";
    card.dataset.bibKey = key;
    const header = document.createElement("header");
    const name = document.createElement("strong");
    name.textContent = key;
    const path = document.createElement("span");
    path.textContent = entry.source_path || ".bib";
    header.append(name, path);
    const fields = document.createElement("div");
    fields.className = "bib-entry-fields";
    fields.append(
      bibField("Author", "author", draft.author, { wide: true }),
      bibField("Year", "year", draft.year),
      bibField("Title", "title", draft.title, { wide: true })
    );
    card.append(header, fields);
    return card;
  });
  const resolvedCount = cards.filter((card) => !card.classList.contains("is-missing")).length;
  els.bibEditorCount.textContent = resolvedCount + " / " + keys.length + " resolved";
  els.bibEditorList.replaceChildren(...cards);
}

function openCitationEditor(blockId, tokenIndex) {
  if (state.dirty) {
    showToast("Save the paragraph text before editing its citation.", true);
    return;
  }
  const block = blockById(blockId);
  const run = block && block.runs.find(
    (item) => item.type === "token" && item.index === tokenIndex
  );
  if (!block || !run || !run.citation) {
    showToast("That citation is no longer available. Reload and try again.", true);
    return;
  }
  state.citationBlockId = blockId;
  state.citationTokenIndex = tokenIndex;
  state.citationBibDraft = {};
  state.citationDirty = false;
  els.citationCommand.value = run.citation.command;
  els.citationOptions.value = run.citation.options || "";
  els.citationKeys.value = run.citation.keys.join(", ");
  els.citationLocation.textContent =
    (block.source_path || state.article.path) + ":" + block.line_start;
  renderBibEditor();
  updateBeforeUnload();
  els.citationDialog.showModal();
  window.setTimeout(() => els.citationKeys.focus(), 0);
}

async function saveCitation() {
  if (!state.article || state.saving) return;
  syncBibDraftFromForm();
  const keys = parsedCitationKeys();
  const bibliography = keys
    .filter((key) => bibliographyByKey(key) && state.citationBibDraft[key])
    .map((key) => state.citationBibDraft[key]);
  const originalBlock = blockById(state.citationBlockId);
  state.saving = true;
  setBusy(els.citationSave, true);
  try {
    const payload = await api("/api/article/citation", {
      method: "PUT",
      body: JSON.stringify({
        block_id: state.citationBlockId,
        token_index: state.citationTokenIndex,
        command: els.citationCommand.value,
        options: els.citationOptions.value,
        keys,
        bibliography,
        expected_hash: state.article.hash,
      }),
    });
    const nextBlock = originalBlock
      ? payload.blocks.find(
          (block) =>
            block.source_path === originalBlock.source_path &&
            block.line_start === originalBlock.line_start &&
            block.kind === originalBlock.kind
        )
      : null;
    state.citationDirty = false;
    state.activeBlockId = nextBlock ? nextBlock.id : null;
    els.citationDialog.close();
    updateBeforeUnload();
    applyArticle(payload);
    if (nextBlock) focusEditingBlock(nextBlock.id);
    showToast("Citation and BibTeX fields saved.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    state.saving = false;
    setBusy(els.citationSave, false);
  }
}

function sourceTargetBlock() {
  return (
    blockById(state.activeBlockId) ||
    blockById(state.outlineActiveBlockId) ||
    blockById(state.contextBlockId)
  );
}

function populateSourceFiles(selectedPath) {
  const sources = state.article && Array.isArray(state.article.sources)
    ? state.article.sources
    : [];
  const options = sources.map((source) => {
    const option = document.createElement("option");
    option.value = source.path;
    option.textContent = source.path;
    return option;
  });
  els.sourceFileSelect.replaceChildren(...options);
  els.sourceFileSelect.value = selectedPath;
}

function focusSourceLine(line) {
  const safeLine = Math.max(1, Number(line) || 1);
  const lines = els.sourceEditor.value.split("\n");
  const offset = lines.slice(0, safeLine - 1).reduce((total, value) => total + value.length + 1, 0);
  els.sourceEditor.focus();
  els.sourceEditor.setSelectionRange(offset, offset);
  const lineHeight = parseFloat(getComputedStyle(els.sourceEditor).lineHeight) || 19;
  els.sourceEditor.scrollTop = Math.max(0, (safeLine - 1) * lineHeight - els.sourceEditor.clientHeight * 0.3);
}

async function loadSourceFile(path, line = 1) {
  const payload = await api("/api/source?path=" + encodeURIComponent(path));
  state.sourceHash = payload.hash;
  state.sourcePath = payload.path;
  state.sourceLine = Math.max(1, Number(line) || 1);
  state.sourceDirty = false;
  els.sourceEditor.value = payload.content;
  els.sourceFileSelect.value = payload.path;
  els.sourceLocation.textContent = payload.path + " · line " + state.sourceLine;
  updateBeforeUnload();
  window.setTimeout(() => focusSourceLine(state.sourceLine), 0);
}

async function openSource() {
  if (state.dirty || state.citationDirty) {
    showToast("Save the current article edit before opening Source.", true);
    return;
  }
  setBusy(els.sourceButton, true);
  try {
    const target = sourceTargetBlock();
    const path = target ? target.source_path : state.article.path;
    const line = target ? target.line_start : 1;
    populateSourceFiles(path);
    els.sourceDialog.showModal();
    await loadSourceFile(path, line);
  } catch (error) {
    if (els.sourceDialog.open) els.sourceDialog.close();
    showToast(error.message, true);
  } finally {
    setBusy(els.sourceButton, false);
  }
}

async function saveSource() {
  setBusy(els.sourceSave, true);
  try {
    const payload = await api("/api/source", {
      method: "PUT",
      body: JSON.stringify({
        path: state.sourcePath,
        content: els.sourceEditor.value,
        expected_hash: state.sourceHash,
      }),
    });
    els.sourceDialog.close();
    state.sourceDirty = false;
    updateBeforeUnload();
    state.activeBlockId = null;
    applyArticle(payload);
    showToast(state.sourcePath + " saved.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(els.sourceSave, false);
  }
}

els.article.addEventListener("mouseup", () => {
  window.setTimeout(captureSelection, 0);
});
els.article.addEventListener("keyup", () => {
  window.setTimeout(captureSelection, 0);
});
els.article.addEventListener("contextmenu", (event) => {
  const target = elementFromNode(event.target);
  const row = target ? target.closest(".article-block") : null;
  if (row) showContextMenu(event, row);
});

els.selectionComment.addEventListener("mousedown", (event) => event.preventDefault());
els.selectionComment.addEventListener("click", () => {
  if (!ensureAuthor() || !state.passageBlockId) return;
  const quote = state.selectedQuote;
  openPassageComments(
    state.passageBlockId,
    quote,
    state.selectedPrefix,
    state.selectedSuffix
  );
  hideSelectionButton();
  window.getSelection().removeAllRanges();
  window.setTimeout(() => els.commentInput.focus(), 0);
});

els.commentsButton.addEventListener("click", () => {
  state.commentView = "all";
  state.showAddressed = false;
  state.selectedQuote = "";
  state.selectedPrefix = "";
  state.selectedSuffix = "";
  setDrawerOpen(true);
  renderComments();
});

els.overallCommentButton.addEventListener("click", () => {
  state.passageBlockId = null;
  state.commentView = "overall";
  state.showAddressed = false;
  state.selectedQuote = "";
  state.selectedPrefix = "";
  state.selectedSuffix = "";
  setDrawerOpen(true);
  renderComments();
  window.setTimeout(() => els.commentInput.focus(), 0);
});

els.displayButton.addEventListener("click", () => {
  if (!els.displayMenu.hidden) {
    hideDisplayMenu();
    return;
  }
  hideContextMenu();
  const rect = els.displayButton.getBoundingClientRect();
  positionFloating(els.displayMenu, rect.right - 238, rect.bottom + 6, 238, 120);
  els.displayMenu.hidden = false;
  els.displayButton.setAttribute("aria-expanded", "true");
});

for (const option of $$("[data-display-mode]")) {
  option.addEventListener("click", () => setDisplayMode(option.dataset.displayMode));
}

els.contextEdit.addEventListener("click", () => {
  if (state.selectionRange) {
    openSelectionEditor();
  } else if (state.contextBlockId) {
    hideContextMenu();
    beginEditing(state.contextBlockId);
  }
});

els.contextComment.addEventListener("click", () => {
  if (!ensureAuthor() || !state.contextBlockId) return;
  hideContextMenu();
  openPassageComments(
    state.contextBlockId,
    state.selectedQuote,
    state.selectedPrefix,
    state.selectedSuffix
  );
  window.setTimeout(() => els.commentInput.focus(), 0);
});

els.contextHighlight.addEventListener("mousedown", (event) => event.preventDefault());
els.contextHighlight.addEventListener("click", toggleSelectionHighlight);

els.selectionEditor.addEventListener("submit", (event) => {
  event.preventDefault();
  applySelectionEdit();
});
els.selectionEditorClose.addEventListener("click", hideSelectionEditor);
els.selectionEditCancel.addEventListener("click", hideSelectionEditor);

els.drawerClose.addEventListener("click", () => setDrawerOpen(false));
els.drawerScrim.addEventListener("click", () => setDrawerOpen(false));

for (const tab of $$("[data-comment-view]")) {
  tab.addEventListener("click", () => selectCommentView(tab.dataset.commentView));
}

els.addressedToggle.addEventListener("click", () => {
  state.showAddressed = !state.showAddressed;
  renderComments();
});

els.commentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const body = els.commentInput.value.trim();
  if (body) addComment(body);
});

els.authorButton.addEventListener("click", () => {
  els.identityInput.value = state.author;
  els.identityDialog.showModal();
  window.setTimeout(() => els.identityInput.focus(), 0);
});
els.composerAuthor.addEventListener("click", () => {
  els.identityInput.value = state.author;
  els.identityDialog.showModal();
  window.setTimeout(() => els.identityInput.focus(), 0);
});

els.identityForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = els.identityInput.value.trim();
  if (!name) return;
  setAuthor(name);
  els.identityDialog.close();
  showToast("Comments will be signed as " + name + ".");
});

els.citationForm.addEventListener("input", (event) => {
  if (event.target === els.citationKeys) {
    syncBibDraftFromForm();
    renderBibEditor();
  }
  state.citationDirty = true;
  updateBeforeUnload();
  if (state.externalHash) renderExternalChange();
});
els.citationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveCitation();
});

els.sourceButton.addEventListener("click", openSource);
els.sourceFileSelect.addEventListener("change", async () => {
  if (state.sourceDirty) {
    els.sourceFileSelect.value = state.sourcePath;
    showToast("Save or cancel the current source edit before switching files.", true);
    return;
  }
  try {
    await loadSourceFile(els.sourceFileSelect.value, 1);
  } catch (error) {
    els.sourceFileSelect.value = state.sourcePath;
    showToast(error.message, true);
  }
});
els.sourceEditor.addEventListener("input", () => {
  state.sourceDirty = true;
  updateBeforeUnload();
  if (state.externalHash) renderExternalChange();
});
els.sourceForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveSource();
});
els.sourceDialog.addEventListener("close", () => {
  state.sourceDirty = false;
  updateBeforeUnload();
});
els.citationDialog.addEventListener("close", () => {
  state.citationDirty = false;
  updateBeforeUnload();
});
els.saveButton.addEventListener("click", () => saveActiveBlock());

for (const button of $$("[data-close-dialog]")) {
  button.addEventListener("click", () => {
    const dialog = document.getElementById(button.dataset.closeDialog);
    if (dialog && dialog.open) {
      dialog.close();
      if (dialog === els.sourceDialog) {
        state.sourceDirty = false;
        updateBeforeUnload();
      } else if (dialog === els.citationDialog) {
        state.citationDirty = false;
        updateBeforeUnload();
      }
    }
  });
}

els.externalChangeLater.addEventListener("click", dismissExternalChange);
els.externalChangeReload.addEventListener("click", reloadExternalChange);

document.addEventListener("mousedown", (event) => {
  if (!els.selectionComment.contains(event.target)) hideSelectionButton();
  if (!els.contextMenu.contains(event.target)) hideContextMenu();
  if (!els.displayMenu.contains(event.target) && !els.displayButton.contains(event.target)) {
    hideDisplayMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    if (els.citationDialog.open) {
      saveCitation();
    } else if (els.sourceDialog.open) {
      saveSource();
    } else {
      saveActiveBlock();
    }
  }
  if (event.key === "Escape") {
    if (!els.selectionEditor.hidden) {
      hideSelectionEditor();
    } else if (!els.contextMenu.hidden) {
      hideContextMenu();
    } else if (!els.displayMenu.hidden) {
      hideDisplayMenu();
    } else if (state.drawerOpen && !$("dialog[open]")) {
      setDrawerOpen(false);
    }
  }
});

window.addEventListener("resize", () => {
  hideContextMenu();
  hideSelectionEditor();
  hideDisplayMenu();
  renderBubbles();
  scheduleOutlineUpdate();
});
window.addEventListener("scroll", scheduleOutlineUpdate, { passive: true });
window.addEventListener("focus", () => checkExternalUpdate({ force: true }));
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) checkExternalUpdate({ force: true });
});
window.setInterval(checkExternalUpdate, 2500);

loadArticle();
