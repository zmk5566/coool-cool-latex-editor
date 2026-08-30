---
name: cool-cool-latex-editor
description: Launch, explain, version-check, or update Cool Cool LaTeX Editor for local Git-managed single-file or recursively included .tex review. Use when a user asks Codex to open a LaTeX manuscript in the editor, choose its local port, work with comments, highlights, citations, BibTeX, or contextual source editing, check its installed version, or update it from GitHub. Do not use for general LaTeX compilation or PDF editing.
---

# Cool Cool LaTeX Editor

Use this skill to operate the lightweight local article-review UI while keeping LaTeX as the only source of truth.

## Open a manuscript

Resolve the requested `.tex` path from the current repository. If no file was named and there is only one plausible manuscript, use it; otherwise ask which file to open.

For a project using `\\input` or `\\include`, choose the main file containing the document environment. The editor recursively follows static references inside the repository, including references from included files. After launch, use the source count and warning details in the header to confirm that the intended files loaded.

Check whether the command is available:

```bash
command -v cool-cool-latex-editor
```

When it is installed, launch it with:

```bash
cool-cool-latex-editor <file.tex> --port <port> --open
```

Use the user's port when supplied; otherwise use the default `4179`, or port `0` when avoiding a collision is more useful. Keep the default bind address `127.0.0.1` unless the user explicitly requests another host and understands that the app has no authentication. Report the resolved document and local URL. Keep the server process running until the user asks to stop it.

If the command is unavailable, explain the installation and request authorization before changing the Python environment:

```bash
pipx install "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

Prefer `pipx`; use a project virtual environment or ordinary `pip` only when that better matches the user's environment.

## Explain the editing model

- The browser view is an intermediate representation; the `.tex` file remains authoritative.
- In a multi-file project, each article block retains its source path. Paragraph edits, inline comments, and highlights write back to that file; overall comments belong to the main entry file.
- Paragraph edits preserve protected LaTeX tokens. In paragraph edit mode, a citation token is a separate button: use it to edit the cite command, options, comma-separated keys, and the author, year, or title of referenced BibTeX entries. Those changes write to the owning `.tex` and `.bib` files together.
- The article view keeps the document title and an explicit **Abstract** heading. Citations continue to render as author-year labels with reference details on hover after their source fields are edited.
- When cited BibTeX entries are loaded, the article ends with a numbered ACM-style **References** section containing cited works only. In reading mode, citation buttons jump to and briefly highlight their matching entries; this rendered list does not create or modify LaTeX source.
- **Source** mode follows the active or most recently outlined passage to its owning TeX file and exact line. Its file picker can switch among all recursively loaded sources. Use it for structural or LaTeX-specific changes.
- Passage comments, overall comments, anchors, and highlights are stored as TeX comments and do not render into normal PDF output.
- **Reading** is quiet; **Bubbles** shows open discussions beside their text on wide screens.
- External disk changes in any loaded source produce a reload prompt. Never discard unsaved browser edits on the user's behalf.
- BibTeX files declared with `\\bibliography` or `\\addbibresource` are display dependencies and also trigger the external-change prompt.
- Static references outside the repository and dynamic macro-generated include paths remain unresolved warnings; do not guess or silently read beyond the repository boundary.
- Git identity is only a browser suggestion. The name chosen in the UI is copied into each annotation.

## Check or update the installation

Read the installed version with:

```bash
cool-cool-latex-editor --version
```

Only update when the user asks. Determine whether the installation is managed by `pipx`, an ordinary Python environment, or an editable source checkout. Use the matching operation:

```bash
pipx upgrade cool-cool-latex-editor
python3 -m pip install --upgrade "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
git -C <checkout> pull --ff-only
```

Treat installation, upgrading, and `git pull` as external mutations: inspect first and obtain any required authorization immediately before running them. Do not overwrite local checkout changes. After an update, verify `cool-cool-latex-editor --version` and restart any running editor process so it loads the new code.

The application has no silent self-updater. Do not invent one or run upgrade commands merely because a newer revision may exist.
