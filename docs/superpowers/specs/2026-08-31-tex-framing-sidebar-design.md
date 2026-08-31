# TeX-Driven Framing Sidebar Design

## Goal

Turn the approved Framing web spike into a read-only argument-architecture sidebar whose Chinese claims, relationships, statuses, and manuscript mappings are controlled entirely by TeX comments.

## Scope

- Keep the existing left Outline.
- Show Framing as a persistent right rail on wide screens when framing metadata exists.
- Keep comments in the existing on-demand drawer; opening it may cover the Framing rail temporarily.
- Do not add AI, framing authoring, confirmation, deletion, or ordering controls.
- Codex edits framing metadata and manuscript prose outside the UI.
- Preserve the current zero-runtime-dependency Python application.

## TeX Format

Framing records live centrally in the main TeX file and are invisible to LaTeX:

```tex
%<editor-framing
% id="abstract-gap"
% section="abstract"
% section-label="Abstract"
% role="gap"
% status="proposed"
% order="20"
% relation="但当前流程中"
%>
% AI 建议、物理装置、可编辑程序与运行状态彼此割裂
%<editor-framing-target source="sections/00-abstract.tex" target="ta-framing-abstract" quote="Existing physical toolkits..."/>
%</editor-framing>
```

`id`, `section`, `role`, `status`, and `order` are required. `section-label`, `parent`, and `relation` are optional. Status is one of `confirmed`, `proposed`, or `placeholder`. Repeated target tags create one-to-many mappings. A target contains a loaded source path, a local text-anchor ID, and optional `quote`, `prefix`, and `suffix` strings.

Parentless records form a section's main argument chain. A record with `parent="proposal-id"` renders as a supporting branch beneath that parent. `relation` is displayed before the record or child group and expresses the causal transition in Chinese.

## Parsing And Mapping

A focused `framing.py` module parses and strips framing records. Malformed records do not crash article loading; they produce clear project warnings.

`LatexProject` reads framing only from the root document, resolves each source-local text anchor through the existing project block map, and emits public target IDs. Mapping health is:

- `linked`: target block exists and the quote is present after whitespace normalization.
- `stale`: target block exists but the quote no longer matches.
- `missing`: source or anchor cannot be resolved.
- `unlinked`: the item intentionally has no target, normally a placeholder.

The article API adds a `framing` array. It never exposes parser offsets or permits framing mutations.

## Sidebar And Correspondence

The static HTML contains only an empty Framing rail. JavaScript renders API data into compact section argument trees matching the approved prototype:

- main chain: Background → Gap → Proposal;
- supporting branches: Mechanism, Method, Result;
- small relationship text between nodes;
- confirmed, proposed, and placeholder markers;
- active node highlighted in amber.

Clicking a linked node cycles through its targets, scrolls to the block, and highlights the exact quote when possible. Stale or missing mappings show a clear note and never silently reattach to similar text. On wide screens the article and rail cannot overlap. Below 1080 px the rail is hidden for this first version rather than compressing the manuscript.

## Clean Submission Export

`strip_editor_metadata()` removes framing blocks in addition to comments, highlights, and text anchors. The existing clean TeX export therefore cannot leak framing metadata. Project-wide clean export is a separate follow-up because it requires deciding which non-TeX submission assets belong in an archive; this implementation guarantees cleanup for every source passed through the stripping function and the current main-file download.

## Initial HexBlocks Content

The first content pass adds an Abstract argument architecture only. It uses fine-grained Chinese records for background, gap, proposal, mechanism, method, and result. Existing manuscript sentences are mapped without changing English prose. Unsupported empirical claims remain `placeholder` rather than being presented as confirmed results.

## Testing

- Unit tests parse Chinese records, parent relations, repeated targets, invalid statuses, and stripping.
- Project tests resolve anchors across included files and report linked/stale/missing/unlinked health.
- Server tests verify the article API and clean export.
- Frontend syntax checks and Playwright verify the real page, node activation, exact highlight, no overlap, and no console errors.

## Non-Goals

- No in-app generation or model API.
- No framing editing UI or write endpoint.
- No automatic manuscript rewriting.
- No fuzzy or semantic remapping after source edits.
- No full-project submission ZIP in this pass.
