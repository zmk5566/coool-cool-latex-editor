from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


FRAMING_RE = re.compile(
    r"^%<editor-framing\b(?P<attrs>.*?)^%>\s*\n"
    r"(?P<body>.*?)"
    r"^%</editor-framing>[ \t]*(?:\n|$)",
    re.MULTILINE | re.DOTALL,
)
FRAMING_TARGET_RE = re.compile(
    r'^%<editor-framing-target\b(?P<attrs>[^>]*)/>[ \t]*(?:\n|$)',
    re.MULTILINE,
)
ATTRIBUTE_RE = re.compile(r'([A-Za-z][A-Za-z0-9_-]*)="([^"]*)"')
VALID_STATUSES = {"confirmed", "proposed", "placeholder"}


@dataclass(frozen=True)
class FramingTarget:
    source_path: str
    anchor: str
    quote: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None


@dataclass(frozen=True)
class FramingItem:
    id: str
    section: str
    section_label: str
    role: str
    status: str
    order: int
    parent: Optional[str]
    relation: Optional[str]
    text: str
    targets: Tuple[FramingTarget, ...]


def _attributes(raw: str) -> dict[str, str]:
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


def parse_framings(source: str) -> tuple[list[FramingItem], list[str]]:
    items: List[FramingItem] = []
    warnings: List[str] = []
    seen: set[str] = set()
    for match in FRAMING_RE.finditer(source):
        attrs = _attributes(match.group("attrs"))
        item_id = attrs.get("id", "").strip()
        required = [name for name in ("id", "section", "role", "status", "order") if not attrs.get(name, "").strip()]
        if required:
            warnings.append(
                "Framing record at line "
                + str(source.count("\n", 0, match.start()) + 1)
                + " is missing: "
                + ", ".join(required)
            )
            continue
        if item_id in seen:
            warnings.append(f"Framing record {item_id!r} is duplicated.")
            continue
        status = attrs["status"].strip()
        if status not in VALID_STATUSES:
            warnings.append(
                f"Framing record {item_id!r} has invalid status {status!r}."
            )
            continue
        try:
            order = int(attrs["order"])
        except ValueError:
            warnings.append(
                f"Framing record {item_id!r} has non-integer order {attrs['order']!r}."
            )
            continue

        body = match.group("body")
        targets: List[FramingTarget] = []
        for target_match in FRAMING_TARGET_RE.finditer(body):
            target_attrs = _attributes(target_match.group("attrs"))
            source_path = target_attrs.get("source", "").strip()
            anchor = target_attrs.get("target", "").strip()
            if not source_path or not anchor:
                warnings.append(
                    f"Framing record {item_id!r} contains a target without source and target."
                )
                continue
            targets.append(
                FramingTarget(
                    source_path=source_path,
                    anchor=anchor,
                    quote=target_attrs.get("quote") or None,
                    prefix=target_attrs.get("prefix") or None,
                    suffix=target_attrs.get("suffix") or None,
                )
            )
        text = _comment_body(FRAMING_TARGET_RE.sub("", body))
        if not text:
            warnings.append(f"Framing record {item_id!r} has no text.")
            continue
        seen.add(item_id)
        items.append(
            FramingItem(
                id=item_id,
                section=attrs["section"].strip(),
                section_label=attrs.get("section-label", attrs["section"]).strip(),
                role=attrs["role"].strip(),
                status=status,
                order=order,
                parent=attrs.get("parent") or None,
                relation=attrs.get("relation") or None,
                text=text,
                targets=tuple(targets),
            )
        )
    items.sort(key=lambda item: (item.section, item.order, item.id))
    return items, warnings


def strip_framing_metadata(source: str) -> str:
    clean = FRAMING_RE.sub("", source)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean
