from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Mapping, Optional


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
    source_path: str = ""

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

    def public_dict(self) -> Dict[str, str]:
        return {
            "key": self.key,
            "author": self.author,
            "year": self.year,
            "title": self.title,
            "source_path": self.source_path,
            "label": self.label,
            "tooltip": self.tooltip,
        }


@dataclass(frozen=True)
class BibtexField:
    name: str
    value: str
    value_start: int
    value_end: int


@dataclass(frozen=True)
class BibtexRecord:
    kind: str
    key: str
    start: int
    end: int
    closing: int
    fields: Mapping[str, BibtexField]


def _record_fields(source: str, start: int, end: int) -> Dict[str, BibtexField]:
    result: Dict[str, BibtexField] = {}
    cursor = start
    while cursor < end:
        match = FIELD_RE.search(source, cursor, end)
        if not match:
            break
        value_start = match.end()
        if value_start >= end:
            break
        if source[value_start] == "{":
            value_end = _closing_brace(source, value_start + 1)
            content_start = value_start + 1
        elif source[value_start] == '"':
            value_end = _quoted_end(source, value_start + 1)
            content_start = value_start + 1
        else:
            value_end = source.find(",", value_start, end)
            if value_end < 0:
                value_end = end
            content_start = value_start
            while value_end > content_start and source[value_end - 1].isspace():
                value_end -= 1
        if value_end < 0 or value_end > end:
            break
        name = match.group("name").lower()
        result[name] = BibtexField(
            name=name,
            value=source[content_start:value_end].strip(),
            value_start=content_start,
            value_end=value_end,
        )
        cursor = value_end + 1
    return result


def bibtex_records(source: str) -> Dict[str, BibtexRecord]:
    records: Dict[str, BibtexRecord] = {}
    cursor = 0
    while True:
        match = ENTRY_RE.search(source, cursor)
        if not match:
            break
        closing = _closing_brace(source, match.end())
        if closing < 0:
            break
        kind = match.group("kind").lower()
        key = match.group("key")
        records[key] = BibtexRecord(
            kind=kind,
            key=key,
            start=match.start(),
            end=closing + 1,
            closing=closing,
            fields=_record_fields(source, match.end(), closing),
        )
        cursor = closing + 1
    return records


def parse_bibtex(source: str, *, source_path: str = "") -> Dict[str, BibliographyEntry]:
    entries: Dict[str, BibliographyEntry] = {}
    for key, record in bibtex_records(source).items():
        if record.kind in {"comment", "preamble", "string"}:
            continue
        fields = record.fields
        entries[key] = BibliographyEntry(
            key=key,
            author=fields["author"].value if "author" in fields else "",
            year=fields["year"].value if "year" in fields else "",
            title=fields["title"].value if "title" in fields else "",
            source_path=source_path,
        )
    return entries


def _balanced_braces(value: str) -> bool:
    depth = 0
    for index, character in enumerate(value):
        if index and value[index - 1] == "\\":
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def update_bibtex_entry(
    source: str,
    key: str,
    updates: Mapping[str, str],
) -> str:
    record = bibtex_records(source).get(key)
    if record is None:
        raise ValueError(f"Bibliography entry {key!r} was not found.")
    allowed = {"author", "year", "title"}
    replacements = []
    missing: Dict[str, str] = {}
    for raw_name, raw_value in updates.items():
        name = raw_name.lower().strip()
        if name not in allowed:
            raise ValueError(f"Bibliography field {raw_name!r} cannot be edited here.")
        value = str(raw_value).strip()
        if "\x00" in value or not _balanced_braces(value):
            raise ValueError(f"Bibliography field {name!r} contains invalid braces.")
        field = record.fields.get(name)
        if field is None:
            missing[name] = value
        else:
            replacements.append((field.value_start, field.value_end, value))

    if missing:
        before_closing = source[: record.closing].rstrip()
        separator = "" if before_closing.endswith(",") else ","
        insertion = separator + "\n" + "\n".join(
            f"  {name:<9}= {{{value}}}," for name, value in missing.items()
        ) + "\n"
        replacements.append((record.closing, record.closing, insertion))

    updated = source
    for start, end, value in sorted(replacements, reverse=True):
        updated = updated[:start] + value + updated[end:]
    return updated
