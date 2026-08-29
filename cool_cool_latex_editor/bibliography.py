from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterator, Tuple


ENTRY_RE = re.compile(
    r"@(?P<kind>[A-Za-z]+)\s*\{\s*(?P<key>[^,\s]+)\s*,",
    re.MULTILINE,
)
FIELD_RE = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*")


def _closing_brace(source: str, start: int) -> int:
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


def _quoted_end(source: str, start: int) -> int:
    cursor = start
    while cursor < len(source):
        if source[cursor] == '"' and (cursor == 0 or source[cursor - 1] != "\\"):
            return cursor
        cursor += 1
    return -1


def _plain_text(value: str) -> str:
    text = value.replace("~", " ")
    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\_": "_",
        r"\#": "#",
        r"\textendash": "–",
        r"\textemdash": "—",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    accent_replacements = (
        (r'{\"o}', "ö"),
        (r'{\"O}', "Ö"),
        (r"{\'e}", "é"),
        (r"{\'E}", "É"),
    )
    for before, after in accent_replacements:
        text = text.replace(before, after)
    text = re.sub(r"\\(?:emph|textbf|textit|textsc|texttt)\s*\{([^{}]*)\}", r"\1", text)
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def _surname(author: str) -> str:
    author = _plain_text(author)
    if not author:
        return ""
    if "," in author:
        return author.split(",", 1)[0].strip()
    words = author.split()
    if len(words) > 1 and words[-2].lower() in {"de", "del", "der", "van", "von"}:
        return " ".join(words[-2:])
    return words[-1]


@dataclass(frozen=True)
class BibliographyEntry:
    key: str
    author: str = ""
    year: str = ""
    title: str = ""

    @property
    def author_label(self) -> str:
        authors = [item.strip() for item in re.split(r"\s+and\s+", self.author) if item.strip()]
        surnames = [name for name in (_surname(item) for item in authors) if name]
        if not surnames:
            return self.key
        if len(surnames) == 1:
            return surnames[0]
        if len(surnames) == 2:
            return f"{surnames[0]} & {surnames[1]}"
        return f"{surnames[0]} et al."

    @property
    def label(self) -> str:
        if self.year:
            return f"{self.author_label}, {self.year}"
        return self.author_label

    @property
    def narrative_label(self) -> str:
        if self.year:
            return f"{self.author_label} ({self.year})"
        return self.author_label

    @property
    def tooltip(self) -> str:
        details = self.author_label
        if self.year:
            details += f" ({self.year})"
        if self.title:
            details += f". {_plain_text(self.title)}"
        return f"{self.key} — {details}"


def _entry_bodies(source: str) -> Iterator[Tuple[str, str, str]]:
    cursor = 0
    while True:
        match = ENTRY_RE.search(source, cursor)
        if not match:
            return
        closing = _closing_brace(source, match.end())
        if closing < 0:
            return
        yield match.group("kind").lower(), match.group("key"), source[match.end() : closing]
        cursor = closing + 1


def _fields(body: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    cursor = 0
    while cursor < len(body):
        match = FIELD_RE.search(body, cursor)
        if not match:
            break
        value_start = match.end()
        if value_start >= len(body):
            break
        if body[value_start] == "{":
            value_end = _closing_brace(body, value_start + 1)
            if value_end < 0:
                break
            value = body[value_start + 1 : value_end]
            cursor = value_end + 1
        elif body[value_start] == '"':
            value_end = _quoted_end(body, value_start + 1)
            if value_end < 0:
                break
            value = body[value_start + 1 : value_end]
            cursor = value_end + 1
        else:
            value_end = body.find(",", value_start)
            if value_end < 0:
                value_end = len(body)
            value = body[value_start:value_end]
            cursor = value_end + 1
        result[match.group("name").lower()] = value.strip()
    return result


def parse_bibtex(source: str) -> Dict[str, BibliographyEntry]:
    entries: Dict[str, BibliographyEntry] = {}
    for kind, key, body in _entry_bodies(source):
        if kind in {"comment", "preamble", "string"}:
            continue
        fields = _fields(body)
        entries[key] = BibliographyEntry(
            key=key,
            author=_plain_text(fields.get("author", "")),
            year=_plain_text(fields.get("year", "")),
            title=fields.get("title", ""),
        )
    return entries
