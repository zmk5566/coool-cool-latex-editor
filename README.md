# cool cool latex editor

[English](README.md) | [简体中文](README.zh-CN.md)

A lightweight, local, Git-native writing and review interface for LaTeX manuscripts. LaTeX remains the single source of truth; the browser provides a calmer intermediate view for reading, focused edits, comments, and highlights.

## What it does

- Renders LaTeX as a centered article instead of an IDE or PDF viewer.
- Recursively follows static `\\input{...}` and `\\include{...}` references, including references from already included files.
- Lets you click a paragraph for a focused edit while protecting formulas, emphasis, links, and other LaTeX structures.
- Adds passage comments, document-level comments, and editor-only highlights from a text selection.
- Stores annotations as TeX comments, so they do not appear in normal LaTeX or PDF output.
- Provides Reading and Bubbles display modes, a document outline, and a full Source mode.
- Detects external file updates without silently discarding unsaved browser edits.
- Stores the chosen reviewer name with each annotation, making review history portable through Git.

The package has no runtime dependencies and binds to `127.0.0.1` by default.

## Install

`pipx` is recommended:

```bash
pipx install "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

You can also install it into the current Python environment:

```bash
python3 -m pip install "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

For local development:

```bash
git clone https://github.com/zmk5566/coool-cool-latex-editor.git
cd coool-cool-latex-editor
python3 -m pip install -e .
```

## Open a manuscript

Pass the `.tex` file as the first argument:

```bash
cool-cool-latex-editor draft/proposal.tex --open
```

The default address is <http://127.0.0.1:4179>. You can choose a port, or use port `0` to let the operating system select an available one:

```bash
cool-cool-latex-editor draft/proposal.tex --port 52732 --open
cool-cool-latex-editor draft/proposal.tex --port 0 --open
```

The editor discovers the containing Git repository automatically. Use `--root /path/to/repository` only when automatic discovery is not appropriate.

For a multi-file manuscript, pass the main entry file. The header reports how many source files were loaded, and hovering it lists their paths and any unresolved include warnings. Article edits, comments, and highlights are written back to the included file that owns the selected passage. **Source** mode intentionally edits only the main entry file.

Check the installed version with:

```bash
cool-cool-latex-editor --version
```

## Update

For a `pipx` installation:

```bash
pipx upgrade cool-cool-latex-editor
```

For a regular `pip` installation:

```bash
python3 -m pip install --upgrade "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

Restart any running editor process after upgrading. The application never updates itself silently in the background.

## Use with Codex CLI

This repository includes a Codex skill that teaches Codex how to locate a manuscript, launch the editor, explain its review model, check the installed version, and update it when explicitly requested.

1. Run `codex` in your terminal to enter Codex CLI.
2. Enter the following at the **Codex conversation prompt**. It is not a shell command:

   ```text
   $skill-installer install https://github.com/zmk5566/coool-cool-latex-editor/tree/main/skills/cool-cool-latex-editor
   ```

3. Codex normally discovers the new skill automatically. If `$cool-cool-latex-editor` does not appear, exit and restart Codex CLI.

After installation, you can ask naturally:

```text
Open draft/proposal.tex with cool cool latex editor on port 52732.
```

Or invoke the skill explicitly:

```text
Use $cool-cool-latex-editor to open draft/proposal.tex.
```

Installing or updating software changes the local environment, so Codex may still request authorization before running the corresponding command.

### Manual skill installation

Codex CLI also reads personal skills from `$HOME/.agents/skills`. If you already cloned this repository, you can link the bundled skill:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "/absolute/path/to/coool-cool-latex-editor/skills/cool-cool-latex-editor" \
  "$HOME/.agents/skills/cool-cool-latex-editor"
```

With this setup, updating the checkout also updates the skill:

```bash
git -C /absolute/path/to/coool-cool-latex-editor pull --ff-only
```

Codex normally detects skill file changes automatically. Restart Codex CLI if an update does not appear.

## Git workflow

1. Pull the manuscript repository and launch the editor locally.
2. Edit prose or add passage comments, an overall comment, and highlights.
3. Use **Source** mode for structural or LaTeX-specific changes.
4. Review the normal Git diff, then commit and push the `.tex` changes.

Comment status is either `open` or `addressed`; “addressed” does not imply that an AI made the edit. Editor metadata consists of valid TeX comments and stays out of normal LaTeX/PDF output. Source mode can also export a clean `.tex` file with editor metadata removed.

## Safety boundaries

- The server listens on `127.0.0.1` by default and has no authentication. Do not expose it directly to the public internet.
- The intermediate renderer focuses on writing structures such as titles, sections, paragraphs, and lists. The complete LaTeX source remains available in **Source** mode.
- Static `\\input` and `\\include` paths must resolve inside the detected repository. Dynamic macro-generated paths are reported as warnings instead of being guessed.
- When another process changes the source file, the page asks before reloading and never silently discards unsaved browser edits.

## Development

```bash
python3 -m unittest discover -s tests -v
node --check cool_cool_latex_editor/static/app.js
```

Current version: `0.2.0`
