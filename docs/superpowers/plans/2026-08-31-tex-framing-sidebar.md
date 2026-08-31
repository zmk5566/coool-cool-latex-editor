# TeX-Driven Framing Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the approved fake Framing rail with a read-only argument architecture parsed from TeX and mapped to manuscript passages.

**Architecture:** A new parser owns framing metadata. `LatexProject` resolves source-local anchors into public article targets, the article API exposes read-only framing payloads, and the existing frontend renders them as compact argument trees. Existing editor-metadata cleanup removes framing during clean export.

**Tech Stack:** Python 3.9 standard library, vanilla JavaScript, HTML, CSS, `unittest`, Playwright QA.

**Spec:** `docs/superpowers/specs/2026-08-31-tex-framing-sidebar-design.md`

## Global Constraints

- No runtime dependencies or AI integration.
- No framing mutation API or editing controls.
- Framing records live in the main TeX file as comments.
- Mapping failures are explicit and never fuzzily reattached.
- Clean export strips all framing metadata and text anchors.
- Preserve the approved dense argument-tree visual direction.

---

### Task 1: Framing Metadata Parser

**Files:**
- Create: `cool_cool_latex_editor/framing.py`
- Create: `tests/test_framing.py`
- Modify: `cool_cool_latex_editor/comments.py`

**Interfaces:**
- Produces: `parse_framings(source: str) -> tuple[list[FramingItem], list[str]]`
- Produces: `strip_framing_metadata(source: str) -> str`
- `FramingItem` exposes `id`, `section`, `section_label`, `role`, `status`, `order`, `parent`, `relation`, `text`, and `targets`.

- [ ] Write parser tests with Chinese text, supporting parent, two targets, invalid status warning, and stripping.
- [ ] Run `python -m unittest tests.test_framing -v` and confirm failures because `framing.py` does not exist.
- [ ] Implement immutable framing dataclasses, anchored regex parsing, validation, and stripping.
- [ ] Integrate stripping into `comments.strip_editor_metadata()`.
- [ ] Run `python -m unittest tests.test_framing tests.test_comments -v` and confirm all pass.

### Task 2: Project Resolution And API

**Files:**
- Modify: `cool_cool_latex_editor/project.py`
- Modify: `cool_cool_latex_editor/server.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Produces: `LatexProject.framing_payloads() -> list[dict[str, object]]`
- API payload: `article["framing"]` with target `block_id`, `source_path`, `quote`, `prefix`, `suffix`, and `health`.

- [ ] Add a multi-file server test whose root framing targets an included-file anchor and assert linked, stale, missing, and unlinked health.
- [ ] Run the targeted server test and confirm `article["framing"]` is absent.
- [ ] Resolve local anchors through `_target_map`, normalize rendered block text for quote checks, and append parser warnings.
- [ ] Add `framing` to `article_payload()` without adding write routes.
- [ ] Run targeted server and clean-export tests and confirm all pass.

### Task 3: Replace The Fake Rail With API Rendering

**Files:**
- Modify: `cool_cool_latex_editor/static/index.html`
- Modify: `cool_cool_latex_editor/static/app.js`
- Modify: `cool_cool_latex_editor/static/styles.css`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: `state.article.framing` from Task 2.
- Produces: `renderFraming()` and `activateFraming(itemId, targetIndex)` browser behavior.

- [ ] Replace the fake-shell test with assertions for an empty `#framing-rail` and no hard-coded Chinese claims.
- [ ] Run the test and confirm it fails against the prototype markup.
- [ ] Remove query gating and all hard-coded framing records.
- [ ] Render section main chains, relations, and child branches from API data using DOM creation and `textContent`.
- [ ] Activate linked targets, highlight exact quotes with CSS Highlights, cycle repeated targets, and show explicit stale/missing/placeholder notes.
- [ ] Run the static test, `node --check`, and the full Python suite.

### Task 4: Seed The HexBlocks Abstract And Validate In Browser

**Files:**
- Modify: `/Users/xuetong/Documents/research/CHI2027/hexblocks-chi2026/main.tex`
- Modify: `/Users/xuetong/Documents/research/CHI2027/hexblocks-chi2026/sections/00-abstract.tex`

**Interfaces:**
- Consumes: TeX format and read-only API from Tasks 1–3.
- Produces: six Chinese Abstract framing items and a stable source anchor.

- [ ] Add a stable text anchor before the Abstract paragraph without changing English prose.
- [ ] Add background, gap, proposal, mechanism, method, and result records to `main.tex`; mark the unsupported result as `placeholder`.
- [ ] Request `/api/article` and confirm six items, parent relationships, and expected mapping health.
- [ ] Use Playwright at 1440×1024 to verify page identity, meaningful content, no overlay, clean console, no article/rail overlap, node activation, and exact sentence highlighting.
- [ ] Run all 39+ Python tests and `node --check cool_cool_latex_editor/static/app.js` before reporting completion.
