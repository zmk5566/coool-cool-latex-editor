from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .framing import strip_framing_metadata


COMMENT_RE = re.compile(
    r"^%<editor-comment\b(?P<attrs>.*?)^%>\s*\n"
    r"(?P<body>.*?)"
    r"^%</editor-comment>[ \t]*(?:\n|$)",
    re.MULTILINE | re.DOTALL,
)
HIGHLIGHT_RE = re.compile(
    r"^%<editor-highlight\b(?P<attrs>.*?)^%/>[ \t]*(?:\n|$)",
    re.MULTILINE | re.DOTALL,
)
ANCHOR_RE = re.compile(
    r'^%<text-anchor\b(?P<attrs>[^>]*)/>[ \t]*(?:\n|$)', re.MULTILINE
)
ATTRIBUTE_RE = re.compile(r'([A-Za-z][A-Za-z0-9_-]*)="([^"]*)"')


@dataclass(frozen=True)
class EditorComment:
    id: str
    author: str
    status: str
    scope: str
    target: Optional[str]
    target_line: Optional[int]
    quote: Optional[str]
    prefix: Optional[str]
    suffix: Optional[str]
    body: str
    created: str
    line: int
    start: int
    end: int

    def public_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data.pop("start")
        data.pop("end")
        return data


@dataclass(frozen=True)
class EditorHighlight:
    id: str
    author: str
    target: str
    target_line: Optional[int]
    quote: str
    prefix: Optional[str]
    suffix: Optional[str]
    tone: str
    created: str
    line: int
    start: int
    end: int

    def public_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data.pop("start")
        data.pop("end")
        return data


def _attributes(raw: str) -> Dict[str, str]:
    return {key: value for key, value in ATTRIBUTE_RE.findall(raw)}


def _comment_body(raw: str) -> str:
    lines: List[str] = []
    for line in raw.splitlines():
        if line.startswith("% "):
            lines.append(line[2:])
        elif line.startswith("%"):
            lines.append(line[1:])
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _anchor_lines(source: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for match in ANCHOR_RE.finditer(source):
        attrs = _attributes(match.group("attrs"))
        anchor_id = attrs.get("id")
        if anchor_id:
            result[anchor_id] = source.count("\n", 0, match.start()) + 2
    return result


def parse_comments(source: str) -> List[EditorComment]:
    anchors = _anchor_lines(source)
    comments: List[EditorComment] = []
    for match in COMMENT_RE.finditer(source):
        attrs = _attributes(match.group("attrs"))
        target = attrs.get("target")
        scope = attrs.get("scope", "inline" if target else "document")
        comments.append(
            EditorComment(
                id=attrs.get("id", "unknown"),
                author=attrs.get("author", "Unknown"),
                status=attrs.get("status", "open"),
                scope=scope,
                target=target,
                target_line=anchors.get(target) if target else None,
                quote=attrs.get("quote") or None,
                prefix=attrs.get("prefix") or None,
                suffix=attrs.get("suffix") or None,
                body=_comment_body(match.group("body")),
                created=attrs.get("created", ""),
                line=source.count("\n", 0, match.start()) + 1,
                start=match.start(),
                end=match.end(),
            )
        )
    return comments


def parse_highlights(source: str) -> List[EditorHighlight]:
    anchors = _anchor_lines(source)
    highlights: List[EditorHighlight] = []
    for match in HIGHLIGHT_RE.finditer(source):
        attrs = _attributes(match.group("attrs"))
        target = attrs.get("target", "")
        highlights.append(
            EditorHighlight(
                id=attrs.get("id", "unknown"),
                author=attrs.get("author", "Unknown"),
                target=target,
                target_line=anchors.get(target) if target else None,
                quote=attrs.get("quote", ""),
                prefix=attrs.get("prefix") or None,
                suffix=attrs.get("suffix") or None,
                tone=attrs.get("tone", "amber"),
                created=attrs.get("created", ""),
                line=source.count("\n", 0, match.start()) + 1,
                start=match.start(),
                end=match.end(),
            )
        )
    return highlights


def _safe_attribute(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'").replace("\n", " ")


def _format_body(body: str) -> str:
    lines = body.strip().splitlines() or [""]
    return "\n".join("% " + line.rstrip() if line else "%" for line in lines)


def format_comment(
    *,
    comment_id: str,
    author: str,
    body: str,
    scope: str,
    target: Optional[str] = None,
    quote: Optional[str] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    created: Optional[str] = None,
) -> str:
    created = created or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "%<editor-comment",
        f'% id="{_safe_attribute(comment_id)}"',
        f'% author="{_safe_attribute(author.strip())}"',
        '% status="open"',
        f'% scope="{_safe_attribute(scope)}"',
    ]
    if target:
        lines.append(f'% target="{_safe_attribute(target)}"')
    if quote:
        lines.append(f'% quote="{_safe_attribute(quote)}"')
    if prefix:
        lines.append(f'% prefix="{_safe_attribute(prefix)}"')
    if suffix:
        lines.append(f'% suffix="{_safe_attribute(suffix)}"')
    lines.extend(
        [
            f'% created="{_safe_attribute(created)}"',
            "%>",
            _format_body(body),
            "%</editor-comment>",
        ]
    )
    return "\n".join(lines) + "\n"


def format_highlight(
    *,
    highlight_id: str,
    author: str,
    target: str,
    quote: str,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    tone: str = "amber",
    created: Optional[str] = None,
) -> str:
    author = author.strip()
    quote = quote.strip()
    if not author:
        raise ValueError("Highlight author is required.")
    if not target:
        raise ValueError("Highlight target is required.")
    if not quote:
        raise ValueError("Highlighted text is required.")
    if tone != "amber":
        raise ValueError("Highlight tone must be amber.")

    created = created or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "%<editor-highlight",
        f'% id="{_safe_attribute(highlight_id)}"',
        f'% author="{_safe_attribute(author)}"',
        f'% target="{_safe_attribute(target)}"',
        f'% quote="{_safe_attribute(quote)}"',
    ]
    if prefix:
        lines.append(f'% prefix="{_safe_attribute(prefix)}"')
    if suffix:
        lines.append(f'% suffix="{_safe_attribute(suffix)}"')
    lines.extend(
        [
            f'% tone="{tone}"',
            f'% created="{_safe_attribute(created)}"',
            "%/>",
        ]
    )
    return "\n".join(lines) + "\n"


def add_comment(
    source: str,
    *,
    author: str,
    body: str,
    scope: str,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    quote: Optional[str] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
) -> Tuple[str, str]:
    author = author.strip()
    body = body.strip()
    if not author:
        raise ValueError("Comment author is required.")
    if not body:
        raise ValueError("Comment text is required.")
    if scope not in {"document", "inline"}:
        raise ValueError("Comment scope must be document or inline.")

    comment_id = "ec-" + uuid.uuid4().hex[:8]
    if scope == "document":
        block = format_comment(
            comment_id=comment_id,
            author=author,
            body=body,
            scope="document",
            quote=quote,
            prefix=prefix,
            suffix=suffix,
        )
        marker = "\\begin{document}"
        marker_at = source.find(marker)
        if marker_at < 0:
            return block + "\n" + source, comment_id
        insert_at = marker_at + len(marker)
        return source[:insert_at] + "\n" + block + source[insert_at:].lstrip("\n"), comment_id

    lines = source.splitlines(keepends=True)
    if not lines:
        lines = [""]
    start = max(1, int(line_start or 1))
    end = max(start, int(line_end or start))
    start = min(start, len(lines))
    end = min(end, len(lines))
    start_index = start - 1
    end_index = end
    anchor_id = "ta-" + uuid.uuid4().hex[:8]
    anchor = f'%<text-anchor id="{anchor_id}"/>\n'
    block = format_comment(
        comment_id=comment_id,
        author=author,
        body=body,
        scope="inline",
        target=anchor_id,
        quote=quote,
        prefix=prefix,
        suffix=suffix,
    )

    selected = "".join(lines[start_index:end_index])
    if selected and not selected.endswith("\n"):
        selected += "\n"
    updated = (
        "".join(lines[:start_index])
        + anchor
        + selected
        + block
        + "".join(lines[end_index:])
    )
    return updated, comment_id


def set_comment_status(source: str, comment_id: str, status: str) -> str:
    if status not in {"open", "addressed"}:
        raise ValueError("Comment status must be open or addressed.")
    for comment in parse_comments(source):
        if comment.id != comment_id:
            continue
        block = source[comment.start : comment.end]
        if re.search(r'^% status="[^"]*"', block, re.MULTILINE):
            changed = re.sub(
                r'^% status="[^"]*"',
                f'% status="{status}"',
                block,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            changed = block.replace("%>", f'% status="{status}"\n%>', 1)
        return source[: comment.start] + changed + source[comment.end :]
    raise ValueError(f"Comment {comment_id!r} was not found.")


def remove_highlight(source: str, highlight_id: str) -> str:
    for highlight in parse_highlights(source):
        if highlight.id == highlight_id:
            return source[: highlight.start] + source[highlight.end :]
    raise ValueError(f"Highlight {highlight_id!r} was not found.")


def strip_editor_metadata(source: str) -> str:
    clean = strip_framing_metadata(source)
    clean = COMMENT_RE.sub("", clean)
    clean = HIGHLIGHT_RE.sub("", clean)
    clean = ANCHOR_RE.sub("", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean
