from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from .article import (
    add_article_comment,
    add_article_highlight,
    parse_article,
    update_article_block,
)
from .comments import (
    add_comment,
    parse_comments,
    parse_highlights,
    remove_highlight,
    set_comment_status,
    strip_editor_metadata,
)


MAX_REQUEST_BYTES = 12 * 1024 * 1024


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class DocumentConflict(RuntimeError):
    pass


class EditorApplication:
    def __init__(self, *, root: Path, document: Path) -> None:
        self.root = root.resolve()
        self.document = document.resolve()
        try:
            self.relative_document = self.document.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("The document must be inside the repository root.") from exc
        if not self.document.is_file():
            raise ValueError(f"LaTeX document does not exist: {self.relative_document}")
        if self.document.suffix.lower() != ".tex":
            raise ValueError("The document must be a .tex file.")

        self.static_dir = Path(__file__).parent / "static"
        self.build_dir = self.root / ".cool-cool-latex-editor" / "build"
        self.lock = threading.RLock()

    @property
    def pdf_path(self) -> Path:
        return self.build_dir / (self.document.stem + ".pdf")

    def read_source(self) -> str:
        return self.document.read_text(encoding="utf-8")

    def _assert_hash(self, expected_hash: Optional[str], current: str) -> None:
        if expected_hash and expected_hash != content_hash(current):
            raise DocumentConflict(
                "The LaTeX file changed on disk. Reload before overwriting it."
            )

    def save_source(self, content: str, expected_hash: Optional[str]) -> str:
        if "\x00" in content:
            raise ValueError("The document contains an invalid null byte.")
        with self.lock:
            current = self.read_source()
            self._assert_hash(expected_hash, current)
            if current == content:
                return content_hash(current)
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=str(self.document.parent),
                prefix="." + self.document.name + ".",
                suffix=".tmp",
                delete=False,
            )
            temp_path = Path(handle.name)
            try:
                with handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(str(temp_path), str(self.document))
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            return content_hash(content)

    def git_info(self) -> Dict[str, Any]:
        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.stdout.strip()

        return {
            "user": git("config", "--get", "user.name"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "—",
            "status": git("status", "--short", "--", self.relative_document),
        }

    def document_payload(self) -> Dict[str, Any]:
        with self.lock:
            source = self.read_source()
            comments = [item.public_dict() for item in parse_comments(source)]
        pdf_exists = self.pdf_path.is_file()
        return {
            "path": self.relative_document,
            "name": self.document.name,
            "content": source,
            "hash": content_hash(source),
            "comments": comments,
            "git": self.git_info(),
            "compiler": {
                "latexmk": bool(shutil.which("latexmk")),
                "xelatex": bool(shutil.which("xelatex")),
            },
            "preview": {
                "ready": pdf_exists,
                "version": self.pdf_path.stat().st_mtime_ns if pdf_exists else None,
            },
        }

    def article_payload(self) -> Dict[str, Any]:
        with self.lock:
            source = self.read_source()
            comments = [item.public_dict() for item in parse_comments(source)]
            highlights = [item.public_dict() for item in parse_highlights(source)]
            blocks = [block.public_dict() for block in parse_article(source)]
        return {
            "path": self.relative_document,
            "name": self.document.name,
            "hash": content_hash(source),
            "blocks": blocks,
            "comments": comments,
            "highlights": highlights,
            "git": self.git_info(),
        }

    def status_payload(self) -> Dict[str, Any]:
        with self.lock:
            source = self.read_source()
            modified_ns = self.document.stat().st_mtime_ns
        return {
            "hash": content_hash(source),
            "modified_ns": modified_ns,
        }

    def update_article_block(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            segments = payload.get("segments")
            if not isinstance(segments, list):
                raise ValueError("Edited article content must be a list of segments.")
            updated = update_article_block(
                current,
                str(payload.get("block_id", "")),
                segments,
            )
            self.save_source(updated, content_hash(current))
        return self.article_payload()

    def add_article_comment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            updated = add_article_comment(
                current,
                author=str(payload.get("author", "")),
                body=str(payload.get("body", "")),
                scope=str(payload.get("scope", "document")),
                block_id=str(payload.get("block_id", "")) or None,
                quote=str(payload.get("quote", "")) or None,
                prefix=str(payload.get("prefix", "")) or None,
                suffix=str(payload.get("suffix", "")) or None,
            )
            self.save_source(updated, content_hash(current))
        return self.article_payload()

    def update_article_comment_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            updated = set_comment_status(
                current,
                str(payload.get("id", "")),
                str(payload.get("status", "addressed")),
            )
            self.save_source(updated, content_hash(current))
        return self.article_payload()

    def add_article_highlight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            updated = add_article_highlight(
                current,
                author=str(payload.get("author", "")),
                block_id=str(payload.get("block_id", "")),
                quote=str(payload.get("quote", "")),
                prefix=str(payload.get("prefix", "")) or None,
                suffix=str(payload.get("suffix", "")) or None,
                tone=str(payload.get("tone", "amber")),
            )
            self.save_source(updated, content_hash(current))
        return self.article_payload()

    def remove_article_highlight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            updated = remove_highlight(current, str(payload.get("id", "")))
            self.save_source(updated, content_hash(current))
        return self.article_payload()

    def add_comment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            source = str(payload.get("content", current))
            updated, _ = add_comment(
                source,
                author=str(payload.get("author", "")),
                body=str(payload.get("body", "")),
                scope=str(payload.get("scope", "document")),
                line_start=payload.get("line_start"),
                line_end=payload.get("line_end"),
            )
            self.save_source(updated, content_hash(current))
        return self.document_payload()

    def update_comment_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current = self.read_source()
            self._assert_hash(payload.get("expected_hash"), current)
            source = str(payload.get("content", current))
            updated = set_comment_status(
                source,
                str(payload.get("id", "")),
                str(payload.get("status", "addressed")),
            )
            self.save_source(updated, content_hash(current))
        return self.document_payload()

    def compile(self, payload: Dict[str, Any]) -> Tuple[HTTPStatus, Dict[str, Any]]:
        source = str(payload.get("content", self.read_source()))
        self.save_source(source, payload.get("expected_hash"))
        latexmk = shutil.which("latexmk")
        if not latexmk:
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "ok": False,
                "message": "latexmk is not installed or not on PATH.",
                "log": "Install a TeX distribution that provides latexmk and XeLaTeX.",
                "document": self.document_payload(),
            }

        self.build_dir.mkdir(parents=True, exist_ok=True)
        command = [
            latexmk,
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-outdir={self.build_dir}",
            str(self.document),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=str(self.document.parent),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            full_log = (result.stdout or "") + (result.stderr or "")
            log = "\n".join(full_log.splitlines()[-100:])
            ok = result.returncode == 0 and self.pdf_path.is_file()
            message = "XeLaTeX passed." if ok else "XeLaTeX failed."
            return (HTTPStatus.OK if ok else HTTPStatus.UNPROCESSABLE_ENTITY), {
                "ok": ok,
                "message": message,
                "log": log,
                "preview_version": time.time_ns() if ok else None,
                "document": self.document_payload(),
            }
        except subprocess.TimeoutExpired as exc:
            return HTTPStatus.REQUEST_TIMEOUT, {
                "ok": False,
                "message": "XeLaTeX timed out after 120 seconds.",
                "log": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
                "document": self.document_payload(),
            }

    def git_diff(self) -> Dict[str, str]:
        status = self.git_info()["status"]
        command = ["git", "diff", "--no-ext-diff", "--", self.relative_document]
        if str(status).startswith("??"):
            command = [
                "git",
                "diff",
                "--no-index",
                "--",
                os.devnull,
                str(self.document),
            ]
        result = subprocess.run(
            command,
            cwd=str(self.root),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        diff = result.stdout.strip()
        if not diff:
            diff = "No textual changes in this LaTeX file."
        return {"status": str(status), "diff": diff}


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: Tuple[str, int], app: EditorApplication) -> None:
        self.app = app
        super().__init__(server_address, EditorRequestHandler)


class EditorRequestHandler(BaseHTTPRequestHandler):
    server: EditorServer

    def log_message(self, format: str, *args: object) -> None:
        if args and str(args[0]).startswith("GET /api/status "):
            return
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _headers(
        self,
        status: HTTPStatus,
        content_type: str,
        length: int,
        *,
        disposition: Optional[str] = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()

    def _bytes(
        self,
        data: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        *,
        disposition: Optional[str] = None,
    ) -> None:
        self._headers(status, content_type, len(data), disposition=disposition)
        self.wfile.write(data)

    def _json(self, data: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._bytes(payload, "application/json; charset=utf-8", status)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"ok": False, "message": message}, status)

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object.")
        return value

    def _serve_static(self, name: str) -> None:
        path = (self.server.app.static_dir / name).resolve()
        try:
            path.relative_to(self.server.app.static_dir.resolve())
        except ValueError:
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        if not path.is_file():
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript"}:
            content_type += "; charset=utf-8"
        self._bytes(path.read_bytes(), content_type)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_static("index.html")
        elif path in {"/styles.css", "/app.js"}:
            self._serve_static(path.lstrip("/"))
        elif path == "/favicon.ico":
            self._bytes(b"", "image/x-icon", HTTPStatus.NO_CONTENT)
        elif path == "/api/document":
            self._json(self.server.app.document_payload())
        elif path == "/api/article":
            self._json(self.server.app.article_payload())
        elif path == "/api/status":
            self._json(self.server.app.status_payload())
        elif path == "/api/git-diff":
            self._json(self.server.app.git_diff())
        elif path == "/api/preview.pdf":
            pdf = self.server.app.pdf_path
            if not pdf.is_file():
                self._error(HTTPStatus.NOT_FOUND, "Compile the document to create a preview.")
            else:
                self._bytes(pdf.read_bytes(), "application/pdf")
        elif path == "/api/export/clean":
            source = strip_editor_metadata(self.server.app.read_source()).encode("utf-8")
            filename = self.server.app.document.stem + "-clean.tex"
            self._bytes(
                source,
                "application/x-tex; charset=utf-8",
                disposition=f'attachment; filename="{filename}"',
            )
        else:
            self._error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/document", "/api/article/block"}:
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        try:
            payload = self._read_json()
            if path == "/api/article/block":
                self._json(self.server.app.update_article_block(payload))
                return
            content = payload.get("content")
            if not isinstance(content, str):
                raise ValueError("Document content must be a string.")
            self.server.app.save_source(content, payload.get("expected_hash"))
            self._json(self.server.app.document_payload())
        except DocumentConflict as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/comments":
                self._json(self.server.app.add_comment(payload), HTTPStatus.CREATED)
            elif path == "/api/comments/status":
                self._json(self.server.app.update_comment_status(payload))
            elif path == "/api/article/comments":
                self._json(self.server.app.add_article_comment(payload), HTTPStatus.CREATED)
            elif path == "/api/article/comments/status":
                self._json(self.server.app.update_article_comment_status(payload))
            elif path == "/api/article/highlights":
                self._json(self.server.app.add_article_highlight(payload), HTTPStatus.CREATED)
            elif path == "/api/article/highlights/remove":
                self._json(self.server.app.remove_article_highlight(payload))
            elif path == "/api/compile":
                status, response = self.server.app.compile(payload)
                self._json(response, status)
            else:
                self._error(HTTPStatus.NOT_FOUND, "Not found.")
        except DocumentConflict as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except (OSError, subprocess.SubprocessError) as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))


def make_server(host: str, port: int, app: EditorApplication) -> EditorServer:
    return EditorServer((host, port), app)
