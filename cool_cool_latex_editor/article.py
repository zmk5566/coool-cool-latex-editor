from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .bibliography import BibliographyEntry

from .comments import (
    ANCHOR_RE,
    ATTRIBUTE_RE,
    COMMENT_RE,
    HIGHLIGHT_RE,
    format_comment,
    format_highlight,
    parse_comments,
)


DOCUMENT_BEGIN_RE = re.compile(r"\\begin\{document\}")
DOCUMENT_END_RE = re.compile(r"\\end\{document\}")
NON_PROSE_ENVIRONMENT_RE = re.compile(
    r"\\begin\{(?P<environment>figure\*?|table\*?|tikzpicture|tabular\*?|tabularx|"
    r"CCSXML|equation\*?|align\*?|verbatim|lstlisting|minted)\}"
    r".*?\\end\{(?P=environment)\}",
    re.DOTALL,
)
NON_PROSE_COMMAND_RE = re.compile(
    r"\\(?:keywords|ccsdesc)(?:\[[^\]]*\])?\{.*?\}", re.DOTALL
)
SECTION_RE = re.compile(
    r"^\s*\\(?P<command>section|subsection|subsubsection|paragraph)"
    r"\*?\{(?P<content>.*)\}\s*$"
)
DOCUMENT_TITLE_RE = re.compile(r"\\title\s*\{")
ABSTRACT_BEGIN_RE = re.compile(r"^\s*\\begin\{abstract\}\s*$")
TITLE_RE = re.compile(r"^\s*\{\\Large\\bfseries\s+(?P<content>.*?)\}\\par\s*$")
SUBTITLE_RE = re.compile(r"^\s*\{\\large\s+(?P<content>.*?)\}\\par\s*$")
LIST_ITEM_RE = re.compile(r"^\s*\\item\s+(?P<content>.*)$")
INLINE_TOKEN_RE = re.compile(
    r"(?<!\\)\$|\\(?:emph|textbf|url)\{|\\judgment(?:\{\})?|"
    r"\\textbackslash\{\}(?:cite|citep|citet|citeauthor|citeyear|parencite|textcite|autocite)"
    r"\s*\\\{[^{}]*\\\}|"
    r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|textcite|autocite)"
    r"(?:\s*\[[^\]]*\])*\s*\{"
)
MACRO_DEFINITION_RE = re.compile(
    r"\\(?:newcommand|renewcommand)\s*\{\\(?P<name>[A-Za-z@]+)\}\s*"
    r"(?:\[(?P<arguments>\d+)\])?\s*\{"
)
CITATION_COMMANDS = {
    "cite",
    "citep",
    "citet",
    "citeauthor",
    "citeyear",
    "parencite",
    "textcite",
    "autocite",
}
CITATION_KEY_RE = re.compile(r"^[A-Za-z0-9_.:/+\-]+$")
CITATION_OPTIONS_RE = re.compile(r"^(?:\[[^\[\]]*\])*$")


@dataclass(frozen=True)
class ArticleToken:
    index: int
    source: str
    text: str
    kind: str
    start: int
    end: int
    tooltip: Optional[str] = None
    unresolved: bool = False
    citation_command: Optional[str] = None
    citation_options: str = ""
    citation_keys: Tuple[str, ...] = ()

    def public_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "index": self.index,
            "text": self.text,
            "kind": self.kind,
        }
        if self.tooltip:
            result["tooltip"] = self.tooltip
        if self.unresolved:
            result["unresolved"] = True
        if self.kind == "citation" and self.citation_command:
            result["citation"] = {
                "command": self.citation_command,
                "options": self.citation_options,
                "keys": list(self.citation_keys),
            }
        return result


@dataclass
class ArticleBlock:
    id: str
    kind: str
    start: int
    end: int
    content_start: int
    content_end: int
    line_start: int
    line_end: int
    runs: List[Dict[str, object]] = field(default_factory=list)
    tokens: List[ArticleToken] = field(default_factory=list)
    comment_count: int = 0
    heading_level: Optional[int] = None

    def public_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "runs": self.runs,
            "tokens": [token.public_dict() for token in self.tokens],
            "comment_count": self.comment_count,
            "heading_level": self.heading_level,
            "editable": self.kind in {"title", "subtitle", "heading", "paragraph", "list-item"},
        }


def _mask_match(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def metadata_mask(source: str) -> str:
    masked = NON_PROSE_ENVIRONMENT_RE.sub(_mask_match, source)
    masked = NON_PROSE_COMMAND_RE.sub(_mask_match, masked)
    masked = COMMENT_RE.sub(_mask_match, masked)
    masked = HIGHLIGHT_RE.sub(_mask_match, masked)
    masked = ANCHOR_RE.sub(_mask_match, masked)
    return masked


def _attributes(raw: str) -> Dict[str, str]:
    return {key: value for key, value in ATTRIBUTE_RE.findall(raw)}


def _anchor_spans(source: str) -> List[Tuple[str, int, int]]:
    anchors: List[Tuple[str, int, int]] = []
    for match in ANCHOR_RE.finditer(source):
        anchor_id = _attributes(match.group("attrs")).get("id")
        if anchor_id:
            anchors.append((anchor_id, match.start(), match.end()))
    return anchors


def latex_text(value: str) -> str:
    text = value
    replacements = (
        (r"\_", "_"),
        (r"\&", "&"),
        (r"\%", "%"),
        (r"\#", "#"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\vdash", "⊢"),
        (r"\textbackslash{}", "\\"),
        (r"\textasciitilde{}", "~"),
        (r"\textasciicircum{}", "^"),
    )
    for before, after in replacements:
        text = text.replace(before, after)
    text = text.replace("``", "“").replace("''", "”")
    text = text.replace("---", "—").replace("--", "–")
    text = text.replace("~", " ").replace(r"\\", "\n")
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    return text


def _macro_preview(value: str) -> str:
    text = value.replace(r"\xspace", "")
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"\\(?:emph|textbf|textit|textsc|texttt|mathrm)\s*\{([^{}]*)\}",
            r"\1",
            text,
        )
    text = text.replace(r"\LaTeX", "LaTeX").replace(r"\TeX", "TeX")
    if re.search(r"\\[A-Za-z@]+", text) or "#" in text:
        return ""
    return latex_text(text).strip()


def extract_simple_macros(source: str) -> Dict[str, str]:
    macros: Dict[str, str] = {}
    for match in MACRO_DEFINITION_RE.finditer(source):
        if match.group("arguments") not in {None, "0"}:
            continue
        closing = _find_closing_brace(source, match.end())
        if closing < 0:
            continue
        preview = _macro_preview(source[match.end() : closing])
        if preview:
            macros[match.group("name")] = preview
    return macros


def _find_closing_brace(source: str, start: int) -> int:
    depth = 1
    cursor = start
    while cursor < len(source):
        character = source[cursor]
        if character == "{" and (cursor == 0 or source[cursor - 1] != "\\"):
            depth += 1
        elif character == "}" and (cursor == 0 or source[cursor - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return -1


def _citation_display(
    command: str,
    keys: Sequence[str],
    bibliography: Mapping[str, BibliographyEntry],
) -> Tuple[str, str, bool]:
    entries = [bibliography.get(key) for key in keys]
    unresolved = any(entry is None for entry in entries)

    if command in {"citeauthor"}:
        labels = [entry.author_label if entry else key for key, entry in zip(keys, entries)]
        display = "; ".join(labels)
    elif command in {"citeyear"}:
        labels = [entry.year if entry and entry.year else key for key, entry in zip(keys, entries)]
        display = "; ".join(labels)
    elif command in {"citet", "textcite"}:
        labels = [entry.narrative_label if entry else key for key, entry in zip(keys, entries)]
        display = "; ".join(labels)
    else:
        labels = [entry.label if entry else key for key, entry in zip(keys, entries)]
        display = "(" + "; ".join(labels) + ")"

    tooltip_lines = [
        entry.tooltip if entry else f"{key} — bibliography entry not found"
        for key, entry in zip(keys, entries)
    ]
    return display, "\n".join(tooltip_lines), unresolved


def tokenize_inline(
    source: str,
    *,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> Tuple[List[Dict[str, object]], List[ArticleToken]]:
    runs: List[Dict[str, object]] = []
    tokens: List[ArticleToken] = []
    cursor = 0
    bibliography = bibliography or {}
    macros = macros or {}
    token_re = INLINE_TOKEN_RE
    if macros:
        macro_names = "|".join(re.escape(name) for name in sorted(macros, key=len, reverse=True))
        token_re = re.compile(INLINE_TOKEN_RE.pattern + rf"|\\(?:{macro_names})(?:\{{\}})?")

    def add_text(raw: str) -> None:
        rendered = latex_text(raw)
        if rendered:
            runs.append({"type": "text", "text": rendered})

    while cursor < len(source):
        match = token_re.search(source, cursor)
        if not match:
            add_text(source[cursor:])
            break
        add_text(source[cursor : match.start()])
        raw = ""
        display = ""
        kind = "latex"
        tooltip: Optional[str] = None
        unresolved = False
        citation_command: Optional[str] = None
        citation_options = ""
        citation_keys: Tuple[str, ...] = ()
        end = match.end()
        marker = match.group(0)

        if marker == "$":
            closing = source.find("$", match.end())
            if closing < 0:
                add_text(source[match.start() :])
                break
            raw = source[match.start() : closing + 1]
            display = latex_text(source[match.end() : closing]).strip()
            kind = "formula"
            end = closing + 1
        elif marker.startswith(r"\judgment"):
            raw = marker
            display = "Alice; AI_Collar ⊢ 我 : Dog"
            kind = "formula"
        elif marker.startswith(r"\textbackslash{}"):
            legacy_match = re.fullmatch(
                r"\\textbackslash\{\}(?P<command>cite|citep|citet|citeauthor|citeyear|"
                r"parencite|textcite|autocite)\s*\\\{(?P<keys>[^{}]*)\\\}",
                marker,
            )
            if not legacy_match:
                add_text(marker)
                cursor = match.end()
                continue
            keys = [key.strip() for key in legacy_match.group("keys").split(",") if key.strip()]
            citation_command = legacy_match.group("command")
            citation_keys = tuple(keys)
            raw = f"\\{citation_command}{{{','.join(keys)}}}"
            display, tooltip, unresolved = _citation_display(
                citation_command, keys, bibliography
            )
            tooltip = "Legacy escaped citation; saving this paragraph repairs it.\n" + tooltip
            kind = "citation"
        elif re.match(
            r"\\(?:cite|citep|citet|citeauthor|citeyear|parencite|textcite|autocite)",
            marker,
        ):
            command_match = re.match(r"\\(?P<command>[A-Za-z]+)", marker)
            closing = _find_closing_brace(source, match.end())
            if not command_match or closing < 0:
                add_text(source[match.start() :])
                break
            raw = source[match.start() : closing + 1]
            keys = [key.strip() for key in source[match.end() : closing].split(",") if key.strip()]
            citation_command = command_match.group("command")
            citation_options = marker[command_match.end() :].rsplit("{", 1)[0].strip()
            citation_keys = tuple(keys)
            display, tooltip, unresolved = _citation_display(
                citation_command, keys, bibliography
            )
            kind = "citation"
            end = closing + 1
        elif marker.startswith("\\") and marker[1:].rstrip("{}").strip() in macros:
            raw = marker
            name = marker[1:].rstrip("{}").strip()
            display = macros[name]
            kind = "macro"
            tooltip = f"Protected LaTeX macro: \\{name}"
        else:
            command = marker[1 : marker.index("{")]
            closing = _find_closing_brace(source, match.end())
            if closing < 0:
                add_text(source[match.start() :])
                break
            raw = source[match.start() : closing + 1]
            inner = source[match.end() : closing]
            display = latex_text(inner).strip()
            kind = {"emph": "emphasis", "textbf": "strong", "url": "url"}[command]
            end = closing + 1

        index = len(tokens)
        token = ArticleToken(
            index=index,
            source=raw,
            text=display,
            kind=kind,
            start=match.start(),
            end=end,
            tooltip=tooltip,
            unresolved=unresolved,
            citation_command=citation_command,
            citation_options=citation_options,
            citation_keys=citation_keys,
        )
        tokens.append(token)
        runs.append({"type": "token", **token.public_dict()})
        cursor = end

    return runs, tokens


def _is_structure_line(masked_line: str) -> bool:
    stripped = masked_line.strip()
    if not stripped:
        return True
    if SECTION_RE.match(masked_line) or TITLE_RE.match(masked_line) or SUBTITLE_RE.match(masked_line):
        return True
    if LIST_ITEM_RE.match(masked_line):
        return True
    if stripped.startswith("%"):
        return True
    if re.match(r"^\\(?:begin|end)\{(?:center|abstract|itemize|enumerate)\}", stripped):
        return True
    if re.match(r"^\\(?:vspace|hangindent|setlength|setstretch|maketitle)\b", stripped):
        return True
    if re.match(
        r"^\\(?:input|include|label|centering|caption|Description|graphicspath|"
        r"bibliography|bibliographystyle|keywords|ccsdesc)\b",
        stripped,
    ):
        return True
    if re.match(r"^\{\\small\b.*\}\\par$", stripped):
        return True
    return False


def _block_id(kind: str, source: str, start: int, end: int) -> str:
    identity = f"{start}\0".encode("utf-8") + source[start:end].encode("utf-8")
    digest = hashlib.sha1(identity).hexdigest()[:10]
    return f"b-{kind}-{digest}"


def _anchored_id(
    masked: str,
    anchors: Sequence[Tuple[str, int, int]],
    block_start: int,
    default: str,
) -> str:
    for anchor_id, _, anchor_end in reversed(anchors):
        if anchor_end > block_start:
            continue
        if not masked[anchor_end:block_start].strip():
            return anchor_id
        break
    return default


def _make_block(
    *,
    source: str,
    masked: str,
    anchors: Sequence[Tuple[str, int, int]],
    kind: str,
    start: int,
    end: int,
    content_start: int,
    content_end: int,
    heading_level: Optional[int] = None,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> ArticleBlock:
    runs, tokens = tokenize_inline(
        source[content_start:content_end], bibliography=bibliography, macros=macros
    )
    default_id = _block_id(kind, source, start, end)
    return ArticleBlock(
        id=_anchored_id(masked, anchors, start, default_id),
        kind=kind,
        start=start,
        end=end,
        content_start=content_start,
        content_end=content_end,
        line_start=source.count("\n", 0, start) + 1,
        line_end=source.count("\n", 0, max(start, end - 1)) + 1,
        runs=runs,
        tokens=tokens,
        heading_level=heading_level,
    )


def parse_document_title(
    source: str,
    *,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> Optional[ArticleBlock]:
    match = DOCUMENT_TITLE_RE.search(source)
    if not match:
        return None
    document_begin = DOCUMENT_BEGIN_RE.search(source)
    if document_begin and match.start() > document_begin.start():
        return None
    closing = _find_closing_brace(source, match.end())
    if closing < 0:
        return None
    masked = metadata_mask(source)
    return _make_block(
        source=source,
        masked=masked,
        anchors=_anchor_spans(source),
        kind="title",
        start=match.start(),
        end=closing + 1,
        content_start=match.end(),
        content_end=closing,
        bibliography=bibliography,
        macros=macros,
    )


def _abstract_heading(
    source: str,
    masked: str,
    anchors: Sequence[Tuple[str, int, int]],
    start: int,
    end: int,
) -> ArticleBlock:
    block_id = _anchored_id(
        masked, anchors, start, _block_id("abstract-heading", source, start, end)
    )
    return ArticleBlock(
        id=block_id,
        kind="abstract-heading",
        start=start,
        end=end,
        content_start=start,
        content_end=start,
        line_start=source.count("\n", 0, start) + 1,
        line_end=source.count("\n", 0, max(start, end - 1)) + 1,
        runs=[{"type": "text", "text": "Abstract"}],
        heading_level=1,
    )


def _article_bounds(source: str, *, allow_fragment: bool) -> Tuple[int, int]:
    begin = DOCUMENT_BEGIN_RE.search(source)
    end = DOCUMENT_END_RE.search(source, begin.end() if begin else 0)
    if begin and end:
        return begin.end(), end.start()
    if allow_fragment:
        return 0, len(source)
    raise ValueError("The LaTeX document must contain a document environment.")


def parse_article_range(
    source: str,
    start: int,
    end: int,
    *,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> List[ArticleBlock]:
    if start < 0 or end < start or end > len(source):
        raise ValueError("The article source range is invalid.")

    masked = metadata_mask(source)
    anchors = _anchor_spans(source)
    line_records: List[Tuple[int, int, int]] = []
    cursor = start
    for line in source[start:end].splitlines(keepends=True):
        line_end = cursor + len(line)
        content_end = line_end - 1 if line.endswith("\n") else line_end
        line_records.append((cursor, line_end, content_end))
        cursor = line_end
    if cursor < end:
        line_records.append((cursor, end, end))

    blocks: List[ArticleBlock] = []
    index = 0
    while index < len(line_records):
        line_start, line_end, line_content_end = line_records[index]
        masked_line = masked[line_start:line_content_end]
        raw_line = source[line_start:line_content_end]
        stripped = masked_line.strip()
        if not stripped or stripped.startswith("%"):
            index += 1
            continue

        if ABSTRACT_BEGIN_RE.match(raw_line):
            blocks.append(_abstract_heading(source, masked, anchors, line_start, line_end))
            index += 1
            continue

        matched: Optional[re.Match[str]] = TITLE_RE.match(raw_line)
        kind = "title"
        if not matched:
            matched = SUBTITLE_RE.match(raw_line)
            kind = "subtitle"
        if not matched:
            matched = SECTION_RE.match(raw_line)
            kind = "heading"
        if not matched:
            matched = LIST_ITEM_RE.match(raw_line)
            kind = "list-item"
        if matched:
            content_start = line_start + matched.start("content")
            content_end = line_start + matched.end("content")
            heading_level = None
            if kind == "heading":
                heading_level = {
                    "section": 1,
                    "subsection": 2,
                    "subsubsection": 3,
                    "paragraph": 4,
                }[matched.group("command")]
            blocks.append(
                _make_block(
                    source=source,
                    masked=masked,
                    anchors=anchors,
                    kind=kind,
                    start=line_start,
                    end=line_end,
                    content_start=content_start,
                    content_end=content_end,
                    heading_level=heading_level,
                    bibliography=bibliography,
                    macros=macros,
                )
            )
            index += 1
            continue

        if _is_structure_line(masked_line):
            index += 1
            continue

        paragraph_start = line_start
        paragraph_end = line_end
        paragraph_content_end = line_content_end
        cursor_index = index + 1
        while cursor_index < len(line_records):
            next_start, next_end, next_content_end = line_records[cursor_index]
            next_masked = masked[next_start:next_content_end]
            if _is_structure_line(next_masked):
                break
            paragraph_end = next_end
            paragraph_content_end = next_content_end
            cursor_index += 1

        leading = len(source[paragraph_start:paragraph_content_end]) - len(
            source[paragraph_start:paragraph_content_end].lstrip()
        )
        blocks.append(
            _make_block(
                source=source,
                masked=masked,
                anchors=anchors,
                kind="paragraph",
                start=paragraph_start,
                end=paragraph_end,
                content_start=paragraph_start + leading,
                content_end=paragraph_content_end,
                bibliography=bibliography,
                macros=macros,
            )
        )
        index = cursor_index

    open_comments = [comment for comment in parse_comments(source) if comment.status == "open"]
    for block in blocks:
        block.comment_count = sum(1 for comment in open_comments if comment.target == block.id)
    return blocks


def parse_article(
    source: str,
    *,
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> List[ArticleBlock]:
    start, end = _article_bounds(source, allow_fragment=allow_fragment)
    effective_macros = dict(macros or extract_simple_macros(source))
    blocks: List[ArticleBlock] = []
    if not allow_fragment:
        title = parse_document_title(
            source, bibliography=bibliography, macros=effective_macros
        )
        if title:
            blocks.append(title)
    blocks.extend(
        parse_article_range(
            source,
            start,
            end,
            bibliography=bibliography,
            macros=effective_macros,
        )
    )
    return blocks


def article_block(
    source: str,
    block_id: str,
    *,
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> ArticleBlock:
    for block in parse_article(
        source,
        allow_fragment=allow_fragment,
        bibliography=bibliography,
        macros=macros,
    ):
        if block.id == block_id:
            return block
    raise ValueError("That article block no longer exists. Reload and try again.")


def escape_latex_text(value: str) -> str:
    result: List[str] = []
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for character in value.replace("\r\n", "\n").replace("\r", "\n"):
        result.append(replacements.get(character, character))
    return "".join(result)


def serialize_segments(block: ArticleBlock, segments: Iterable[Dict[str, object]]) -> str:
    values: List[str] = []
    token_order: List[int] = []
    for segment in segments:
        segment_type = segment.get("type")
        if segment_type == "text":
            value = str(segment.get("value", ""))
            if "\x00" in value:
                raise ValueError("Edited text contains an invalid null byte.")
            values.append(escape_latex_text(value))
        elif segment_type == "token":
            try:
                token_index = int(segment.get("index", -1))
                token = block.tokens[token_index]
            except (IndexError, TypeError, ValueError) as exc:
                raise ValueError("A protected LaTeX token is invalid.") from exc
            token_order.append(token_index)
            values.append(token.source)
        else:
            raise ValueError("Edited content contains an unknown segment.")

    expected_order = list(range(len(block.tokens)))
    if token_order != expected_order:
        raise ValueError("Protected LaTeX tokens cannot be removed or reordered.")
    updated = "".join(values).strip()
    if not updated:
        raise ValueError("An article block cannot be empty.")
    if block.kind in {"title", "subtitle", "heading"}:
        updated = re.sub(r"\s*\n\s*", " ", updated)
    return updated


def update_article_citation(
    source: str,
    block_id: str,
    token_index: int,
    *,
    command: str,
    options: str,
    keys: Sequence[str],
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> str:
    block = article_block(
        source,
        block_id,
        allow_fragment=allow_fragment,
        bibliography=bibliography,
        macros=macros,
    )
    try:
        token = block.tokens[token_index]
    except (IndexError, TypeError) as exc:
        raise ValueError("That citation no longer exists. Reload and try again.") from exc
    if token.kind != "citation":
        raise ValueError("The selected LaTeX token is not a citation.")

    command = command.strip()
    options = options.strip()
    normalized_keys = [str(key).strip() for key in keys if str(key).strip()]
    if command not in CITATION_COMMANDS:
        raise ValueError(f"Unsupported citation command: {command}")
    if options and not CITATION_OPTIONS_RE.fullmatch(options):
        raise ValueError("Citation options must use balanced square brackets.")
    if not normalized_keys:
        raise ValueError("A citation must contain at least one BibTeX key.")
    if any(not CITATION_KEY_RE.fullmatch(key) for key in normalized_keys):
        raise ValueError("Citation keys contain unsupported characters.")

    replacement = f"\\{command}{options}{{{','.join(normalized_keys)}}}"
    start = block.content_start + token.start
    end = block.content_start + token.end
    return source[:start] + replacement + source[end:]


def update_article_block(
    source: str,
    block_id: str,
    segments: Iterable[Dict[str, object]],
    *,
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> str:
    block = article_block(
        source,
        block_id,
        allow_fragment=allow_fragment,
        bibliography=bibliography,
        macros=macros,
    )
    replacement = serialize_segments(block, segments)
    return source[: block.content_start] + replacement + source[block.content_end :]


def add_article_comment(
    source: str,
    *,
    author: str,
    body: str,
    scope: str,
    block_id: Optional[str] = None,
    quote: Optional[str] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> str:
    author = author.strip()
    body = body.strip()
    if not author:
        raise ValueError("Comment author is required.")
    if not body:
        raise ValueError("Comment text is required.")
    if scope == "document":
        comment_id = "ec-" + uuid.uuid4().hex[:8]
        comment = format_comment(
            comment_id=comment_id,
            author=author,
            body=body,
            scope="document",
            quote=quote,
            prefix=prefix,
            suffix=suffix,
        )
        begin = DOCUMENT_BEGIN_RE.search(source)
        if not begin:
            return comment + "\n" + source
        return source[: begin.end()] + "\n" + comment + source[begin.end() :].lstrip("\n")
    if scope != "inline" or not block_id:
        raise ValueError("Inline comments require an article block.")

    block = article_block(
        source,
        block_id,
        allow_fragment=allow_fragment,
        bibliography=bibliography,
        macros=macros,
    )
    target = block.id if block.id.startswith("ta-") else "ta-" + uuid.uuid4().hex[:8]
    anchor = "" if block.id.startswith("ta-") else f'%<text-anchor id="{target}"/>\n'
    comment = format_comment(
        comment_id="ec-" + uuid.uuid4().hex[:8],
        author=author,
        body=body,
        scope="inline",
        target=target,
        quote=quote,
        prefix=prefix,
        suffix=suffix,
    )
    block_source = source[block.start : block.end]
    if block_source and not block_source.endswith("\n"):
        block_source += "\n"
    return (
        source[: block.start]
        + anchor
        + block_source
        + comment
        + source[block.end :]
    )


def add_article_highlight(
    source: str,
    *,
    author: str,
    block_id: str,
    quote: str,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    tone: str = "amber",
    allow_fragment: bool = False,
    bibliography: Optional[Mapping[str, BibliographyEntry]] = None,
    macros: Optional[Mapping[str, str]] = None,
) -> str:
    block = article_block(
        source,
        block_id,
        allow_fragment=allow_fragment,
        bibliography=bibliography,
        macros=macros,
    )
    target = block.id if block.id.startswith("ta-") else "ta-" + uuid.uuid4().hex[:8]
    anchor = "" if block.id.startswith("ta-") else f'%<text-anchor id="{target}"/>\n'
    highlight = format_highlight(
        highlight_id="eh-" + uuid.uuid4().hex[:8],
        author=author,
        target=target,
        quote=quote,
        prefix=prefix,
        suffix=suffix,
        tone=tone,
    )
    block_source = source[block.start : block.end]
    if block_source and not block_source.endswith("\n"):
        block_source += "\n"
    return (
        source[: block.start]
        + anchor
        + block_source
        + highlight
        + source[block.end :]
    )
