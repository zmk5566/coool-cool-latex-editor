from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from . import __version__
from .server import EditorApplication, make_server


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def discover_repository_root(document: Path) -> Path:
    start = document.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return start
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return start


def resolve_paths(document_arg: str, root_arg: Optional[str]) -> tuple[Path, Path]:
    raw_document = Path(document_arg).expanduser()
    if root_arg:
        root = Path(root_arg).expanduser().resolve()
        document = raw_document if raw_document.is_absolute() else root / raw_document
        return root, document.resolve()

    document = raw_document.resolve()
    return discover_repository_root(document), document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cool-cool-latex-editor",
        description="Launch a local, Git-native LaTeX review editor.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "document",
        metavar="FILE.tex",
        help="LaTeX source to edit. Relative paths use the current directory.",
    )
    parser.add_argument(
        "--root",
        help="Override the automatically detected Git repository root.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Address to bind (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        default=4179,
        type=port_number,
        help="Local port, or 0 to choose a free port (default: 4179).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the editor in the default browser after launch.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root, document = resolve_paths(args.document, args.root)

    try:
        app = EditorApplication(root=root, document=document)
        server = make_server(args.host, args.port, app)
    except (OSError, ValueError) as exc:
        print(f"cool cool latex editor: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    host, port = server.server_address[:2]
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{display_host}:{port}/"
    print(f"cool cool latex editor → {url}")
    print(f"repository root        → {app.root}")
    print(f"document               → {app.relative_document}")
    print("Press Ctrl-C to stop.")

    if args.open:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping cool cool latex editor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
