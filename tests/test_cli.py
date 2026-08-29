import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.__main__ import (  # noqa: E402
    build_parser,
    discover_repository_root,
    port_number,
    resolve_paths,
)


class CliTests(unittest.TestCase):
    def test_version_can_be_read_without_a_document(self):
        with self.assertRaises(SystemExit) as exit_context:
            with patch("sys.stdout") as stdout:
                build_parser().parse_args(["--version"])

        self.assertEqual(exit_context.exception.code, 0)
        stdout.write.assert_called_once_with("cool-cool-latex-editor 0.2.1\n")

    def test_document_is_positional_and_port_is_configurable(self):
        args = build_parser().parse_args(["draft/proposal.tex", "--port", "4188"])
        self.assertEqual(args.document, "draft/proposal.tex")
        self.assertEqual(args.port, 4188)

    def test_port_zero_is_allowed_and_invalid_ports_are_rejected(self):
        self.assertEqual(port_number("0"), 0)
        with self.assertRaises(argparse.ArgumentTypeError):
            port_number("65536")
        with self.assertRaises(argparse.ArgumentTypeError):
            port_number("not-a-port")

    def test_git_root_is_detected_from_document_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "draft" / "proposal.tex"
            document.parent.mkdir()
            document.write_text("", encoding="utf-8")
            completed = Mock(returncode=0, stdout=directory + "\n")
            with patch("subprocess.run", return_value=completed) as run:
                root = discover_repository_root(document)

        self.assertEqual(root, Path(directory).resolve())
        self.assertEqual(run.call_args.args[0][:3], ["git", "-C", str(document.parent)])

    def test_explicit_root_resolves_relative_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root, document = resolve_paths("draft/proposal.tex", directory)
            self.assertEqual(root, Path(directory).resolve())
            self.assertEqual(document, (Path(directory) / "draft/proposal.tex").resolve())


if __name__ == "__main__":
    unittest.main()
