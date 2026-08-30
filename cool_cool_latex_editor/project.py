from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .article import (
    DOCUMENT_BEGIN_RE,
    DOCUMENT_END_RE,
    ArticleBlock,
    extract_simple_macros,
    parse_article_range,
    parse_document_title,
)
from .bibliography import BibliographyEntry, parse_bibtex
from .comments import parse_comments, parse_highlights


INCLUDE_RE = re.compile(
    r"^[ \t]*\\(?P<command>input|include)\s*\{(?P<target>[^{}\r\n]+)\}"
    r"[ \t]*(?:%[^\n]*)?(?:\n|$)",
    re.MULTILINE,
)
BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\s*\{(?P<targets>[^{}]+)\}")
ADD_BIB_RESOURCE_RE = re.compile(
    r"\\addbibresource(?:\[[^\]]*\])?\s*\{(?P<target>[^{}]+)\}"
)
MAX_INCLUDE_DEPTH = 64


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProjectSource:
    path: Path
    relative_path: str
    content: str
    modified_ns: int

    @property
    def hash(self) -> str:
        return content_hash(self.content)


@dataclass(frozen=True)
class ProjectBlock:
    id: str
    source: ProjectSource
    block: ArticleBlock

    def public_dict(self) -> Dict[str, object]:
        data = self.block.public_dict()
        data["id"] = self.id
        data["source_path"] = self.source.relative_path
        return data


@dataclass
class LatexProject:
    root: Path
    document: Path
    sources: Dict[str, ProjectSource] = field(default_factory=dict)
    blocks: List[ProjectBlock] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    bibliography_sources: Dict[str, ProjectSource] = field(default_factory=dict)
    bibliography: Dict[str, BibliographyEntry] = field(default_factory=dict)
    macros: Dict[str, str] = field(default_factory=dict)
    _block_map: Dict[str, ProjectBlock] = field(default_factory=dict)
    _target_map: Dict[Tuple[str, str], str] = field(default_factory=dict)
    _block_occurrences: Dict[Tuple[str, str], int] = field(default_factory=dict)

    @classmethod
    def load(cls, *, root: Path, document: Path) -> "LatexProject":
        project = cls(root=root.resolve(), document=document.resolve())
        root_source = project._read_source(project.document)
        if root_source is None:
            raise ValueError("The main LaTeX file could not be read.")
        project.macros = extract_simple_macros(root_source.content)
        project._load_bibliographies(root_source)
        project._walk(project.document, is_root=True, stack=[])
        return project

    @property
    def hash(self) -> str:
        digest = hashlib.sha256()
        for relative_path in sorted(self.sources):
            source = self.sources[relative_path]
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.content.encode("utf-8"))
            digest.update(b"\0")
        for relative_path in sorted(self.bibliography_sources):
            source = self.bibliography_sources[relative_path]
            digest.update(b"bib\0")
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.content.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    @property
    def modified_ns(self) -> int:
        dependencies = [*self.sources.values(), *self.bibliography_sources.values()]
        return max((source.modified_ns for source in dependencies), default=0)

    @property
    def root_source(self) -> ProjectSource:
        relative_path = self.document.relative_to(self.root).as_posix()
        return self.sources[relative_path]

    @property
    def relative_paths(self) -> List[str]:
        return list(self.sources)

    def source_payloads(self) -> List[Dict[str, object]]:
        block_counts: Dict[str, int] = {path: 0 for path in self.sources}
        for block in self.blocks:
            block_counts[block.source.relative_path] += 1
        return [
            {
                "path": source.relative_path,
                "hash": source.hash,
                "modified_ns": source.modified_ns,
                "block_count": block_counts[source.relative_path],
            }
            for source in self.sources.values()
        ]

    def bibliography_payloads(self) -> List[Dict[str, str]]:
        return [self.bibliography[key].public_dict() for key in sorted(self.bibliography)]

    def references_payloads(self) -> List[Dict[str, object]]:
        if not self.bibliography_sources:
            return []
        cited_keys = {
            key
            for project_block in self.blocks
            for token in project_block.block.tokens
            if token.kind == "citation"
            for key in token.citation_keys
        }
        ordered_keys = sorted(
            cited_keys,
            key=lambda key: (
                self.bibliography[key].author_label.casefold(),
                self.bibliography[key].year.casefold(),
                self.bibliography[key].title.casefold(),
                key.casefold(),
            )
            if key in self.bibliography
            else ("\uffff", "", "", key.casefold()),
        )
        result: List[Dict[str, object]] = []
        for index, key in enumerate(ordered_keys, start=1):
            entry = self.bibliography.get(key)
            data: Dict[str, object]
            if entry is None:
                data = {"key": key, "missing": True}
            else:
                data = entry.public_dict()
            data["index"] = index
            result.append(data)
        return result

    def source(self, relative_path: str) -> ProjectSource:
        try:
            return self.sources[relative_path]
        except KeyError as exc:
            raise ValueError(f"LaTeX source {relative_path!r} is not loaded.") from exc

    def bibliography_source(self, key: str) -> ProjectSource:
        try:
            entry = self.bibliography[key]
            return self.bibliography_sources[entry.source_path]
        except KeyError as exc:
            raise ValueError(f"Bibliography entry {key!r} was not found.") from exc

    def block(self, public_id: str) -> ProjectBlock:
        try:
            return self._block_map[public_id]
        except KeyError as exc:
            raise ValueError("That article block no longer exists. Reload and try again.") from exc

    def comment_source(self, comment_id: str) -> ProjectSource:
        for source in self.sources.values():
            if any(comment.id == comment_id for comment in parse_comments(source.content)):
                return source
        raise ValueError(f"Comment {comment_id!r} was not found.")

    def highlight_source(self, highlight_id: str) -> ProjectSource:
        for source in self.sources.values():
            if any(item.id == highlight_id for item in parse_highlights(source.content)):
                return source
        raise ValueError(f"Highlight {highlight_id!r} was not found.")

    def comments_payload(self) -> List[Dict[str, object]]:
        result: List[Dict[str, object]] = []
        for source in self.sources.values():
            for comment in parse_comments(source.content):
                data = comment.public_dict()
                if comment.target:
                    data["target"] = self._target_map.get(
                        (source.relative_path, comment.target),
                        self._fallback_target(source.relative_path, comment.target),
                    )
                data["source_path"] = source.relative_path
                result.append(data)
        return result

    def highlights_payload(self) -> List[Dict[str, object]]:
        result: List[Dict[str, object]] = []
        for source in self.sources.values():
            for highlight in parse_highlights(source.content):
                data = highlight.public_dict()
                data["target"] = self._target_map.get(
                    (source.relative_path, highlight.target),
                    self._fallback_target(source.relative_path, highlight.target),
                )
                data["source_path"] = source.relative_path
                result.append(data)
        return result

    def _relative_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("Included LaTeX files must stay inside the repository root.") from exc

    def _read_source(self, path: Path) -> Optional[ProjectSource]:
        relative_path = self._relative_path(path)
        if relative_path in self.sources:
            return self.sources[relative_path]
        try:
            content = path.read_text(encoding="utf-8")
            modified_ns = path.stat().st_mtime_ns
        except (OSError, UnicodeError) as exc:
            self.warnings.append(f"Could not read {relative_path}: {exc}")
            return None
        source = ProjectSource(
            path=path.resolve(),
            relative_path=relative_path,
            content=content,
            modified_ns=modified_ns,
        )
        self.sources[relative_path] = source
        return source

    def _resolve_bibliography(self, raw_target: str, source: ProjectSource) -> Optional[Path]:
        target = raw_target.strip()
        if not target or "\\" in target or "#" in target:
            self.warnings.append(
                f"Unsupported dynamic bibliography in {source.relative_path}: {raw_target}"
            )
            return None
        raw_path = Path(target)
        variants = [raw_path] if raw_path.suffix else [raw_path.with_suffix(".bib")]
        checked: set[Path] = set()
        for base in (self.document.parent, source.path.parent, self.root):
            for variant in variants:
                candidate = variant.resolve() if variant.is_absolute() else (base / variant).resolve()
                if candidate in checked:
                    continue
                checked.add(candidate)
                try:
                    candidate.relative_to(self.root)
                except ValueError:
                    continue
                if candidate.is_file():
                    return candidate
        self.warnings.append(
            f"Bibliography file not found from {source.relative_path}: {target}"
        )
        return None

    def _load_bibliography_source(self, path: Path) -> None:
        relative_path = self._relative_path(path)
        if relative_path in self.bibliography_sources:
            return
        try:
            content = path.read_text(encoding="utf-8")
            modified_ns = path.stat().st_mtime_ns
        except (OSError, UnicodeError) as exc:
            self.warnings.append(f"Could not read {relative_path}: {exc}")
            return
        source = ProjectSource(
            path=path.resolve(),
            relative_path=relative_path,
            content=content,
            modified_ns=modified_ns,
        )
        self.bibliography_sources[relative_path] = source
        self.bibliography.update(parse_bibtex(content, source_path=relative_path))

    def _load_bibliographies(self, source: ProjectSource) -> None:
        targets: List[str] = []
        for match in BIBLIOGRAPHY_RE.finditer(source.content):
            targets.extend(item.strip() for item in match.group("targets").split(","))
        targets.extend(
            match.group("target").strip()
            for match in ADD_BIB_RESOURCE_RE.finditer(source.content)
        )
        for target in targets:
            path = self._resolve_bibliography(target, source)
            if path is not None:
                self._load_bibliography_source(path)

    def _bounds(self, source: ProjectSource, *, is_root: bool) -> Tuple[int, int]:
        begin = DOCUMENT_BEGIN_RE.search(source.content)
        end = DOCUMENT_END_RE.search(source.content, begin.end() if begin else 0)
        if begin and end:
            return begin.end(), end.start()
        if is_root:
            raise ValueError("The main LaTeX file must contain a document environment.")
        return 0, len(source.content)

    def _resolve_include(self, source: ProjectSource, raw_target: str) -> Optional[Path]:
        target = raw_target.strip()
        if not target or "\\" in target or "#" in target:
            self.warnings.append(
                f"Unsupported dynamic include in {source.relative_path}: {raw_target}"
            )
            return None

        raw_path = Path(target).expanduser()
        variants = [raw_path]
        if not raw_path.suffix:
            variants.append(raw_path.with_suffix(".tex"))

        bases: Sequence[Path]
        if raw_path.is_absolute():
            bases = [Path("/")]
        else:
            bases = [self.document.parent, source.path.parent, self.root]

        outside_root = False
        checked: set[Path] = set()
        for base in bases:
            for variant in variants:
                candidate = variant.resolve() if variant.is_absolute() else (base / variant).resolve()
                if candidate in checked:
                    continue
                checked.add(candidate)
                try:
                    candidate.relative_to(self.root)
                except ValueError:
                    outside_root = True
                    continue
                if candidate.is_file():
                    return candidate

        if outside_root:
            self.warnings.append(
                f"Skipped include outside the repository in {source.relative_path}: {target}"
            )
        else:
            self.warnings.append(
                f"Included file not found from {source.relative_path}: {target}"
            )
        return None

    def _fallback_target(self, relative_path: str, local_id: str) -> str:
        return f"{relative_path}::{local_id}"

    def _append_block(self, source: ProjectSource, block: ArticleBlock) -> None:
        key = (source.relative_path, block.id)
        occurrence = self._block_occurrences.get(key, 0)
        self._block_occurrences[key] = occurrence + 1
        public_id = self._fallback_target(source.relative_path, block.id)
        if occurrence:
            public_id += f"::{occurrence + 1}"
        wrapped = ProjectBlock(id=public_id, source=source, block=block)
        self.blocks.append(wrapped)
        self._block_map[public_id] = wrapped
        self._target_map.setdefault(key, public_id)

    def _add_blocks(self, source: ProjectSource, start: int, end: int) -> None:
        if start >= end:
            return
        for block in parse_article_range(
            source.content,
            start,
            end,
            bibliography=self.bibliography,
            macros=self.macros,
        ):
            self._append_block(source, block)

    def _walk(self, path: Path, *, is_root: bool, stack: List[Path]) -> None:
        resolved = path.resolve()
        if resolved in stack:
            cycle = " -> ".join(
                [item.relative_to(self.root).as_posix() for item in stack]
                + [resolved.relative_to(self.root).as_posix()]
            )
            self.warnings.append(f"Circular include skipped: {cycle}")
            return
        if len(stack) >= MAX_INCLUDE_DEPTH:
            self.warnings.append(
                f"Include depth exceeded {MAX_INCLUDE_DEPTH} at {self._relative_path(resolved)}"
            )
            return

        source = self._read_source(resolved)
        if source is None:
            return
        if is_root:
            title = parse_document_title(
                source.content,
                bibliography=self.bibliography,
                macros=self.macros,
            )
            if title:
                self._append_block(source, title)
        start, end = self._bounds(source, is_root=is_root)
        cursor = start
        next_stack = [*stack, resolved]
        for match in INCLUDE_RE.finditer(source.content, start, end):
            self._add_blocks(source, cursor, match.start())
            child = self._resolve_include(source, match.group("target"))
            if child is not None:
                self._walk(child, is_root=False, stack=next_stack)
            cursor = match.end()
        self._add_blocks(source, cursor, end)
