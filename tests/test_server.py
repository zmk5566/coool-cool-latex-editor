import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.server import EditorApplication, make_server  # noqa: E402


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "draft").mkdir()
        self.document = self.root / "draft" / "proposal.tex"
        self.document.write_text(
            "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n",
            encoding="utf-8",
        )
        app = EditorApplication(root=self.root, document=self.document)
        self.server = make_server("127.0.0.1", 0, app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
        return json.loads(data) if "application/json" in content_type else data

    def test_document_can_be_loaded_and_saved(self):
        document = self.request("/api/document")
        self.assertEqual(document["path"], "draft/proposal.tex")
        document["content"] = document["content"].replace("Hello.", "Hello, Alice.")
        saved = self.request(
            "/api/document",
            method="PUT",
            payload={"content": document["content"], "expected_hash": document["hash"]},
        )
        self.assertIn("Hello, Alice.", saved["content"])

    def test_status_api_detects_an_external_file_update(self):
        article = self.request("/api/article")
        initial = self.request("/api/status")
        self.assertEqual(initial["hash"], article["hash"])
        self.assertIsInstance(initial["modified_ns"], int)

        self.document.write_text(
            "\\documentclass{article}\n\\begin{document}\nChanged elsewhere.\n\\end{document}\n",
            encoding="utf-8",
        )
        changed = self.request("/api/status")
        self.assertNotEqual(changed["hash"], article["hash"])

    def test_comment_api_and_clean_export(self):
        document = self.request("/api/document")
        updated = self.request(
            "/api/comments",
            method="POST",
            payload={
                "content": document["content"],
                "expected_hash": document["hash"],
                "author": "Alice",
                "body": "Overall thought.",
                "scope": "document",
            },
        )
        self.assertEqual(len(updated["comments"]), 1)
        clean = self.request("/api/export/clean")
        self.assertNotIn(b"editor-comment", clean)
        self.assertIn(b"Hello.", clean)

    def test_static_application_is_served(self):
        html = self.request("/")
        self.assertIn(b"cool cool latex editor", html)
        self.assertIn(b"Editable article", html)
        self.assertIn(b"Add an overall comment", html)
        self.assertIn(b"Overall comment", html)
        self.assertIn(b"LaTeX changed on disk", html)
        self.assertNotIn(b"PDF preview", html)

    def test_article_block_api_round_trips_plain_text(self):
        article = self.request("/api/article")
        self.assertEqual(len(article["blocks"]), 1)
        block = article["blocks"][0]

        updated = self.request(
            "/api/article/block",
            method="PUT",
            payload={
                "block_id": block["id"],
                "segments": [{"type": "text", "value": "Hello, Alice & Bob."}],
                "expected_hash": article["hash"],
            },
        )

        self.assertEqual(updated["blocks"][0]["runs"][0]["text"], "Hello, Alice & Bob.")
        self.assertIn("Hello, Alice \\& Bob.", self.document.read_text(encoding="utf-8"))

    def test_article_comment_api_adds_quote_and_updates_status(self):
        article = self.request("/api/article")
        updated = self.request(
            "/api/article/comments",
            method="POST",
            payload={
                "expected_hash": article["hash"],
                "author": "Alice",
                "body": "Make this opening gentler.",
                "scope": "inline",
                "block_id": article["blocks"][0]["id"],
                "quote": "Hello.",
                "prefix": "Before ",
                "suffix": " After.",
            },
        )

        self.assertEqual(updated["blocks"][0]["comment_count"], 1)
        comment = updated["comments"][0]
        self.assertEqual(comment["quote"], "Hello.")
        self.assertEqual(comment["prefix"], "Before ")
        self.assertEqual(comment["suffix"], " After.")
        self.assertEqual(comment["target"], updated["blocks"][0]["id"])

        addressed = self.request(
            "/api/article/comments/status",
            method="POST",
            payload={
                "expected_hash": updated["hash"],
                "id": comment["id"],
                "status": "addressed",
            },
        )
        self.assertEqual(addressed["comments"][0]["status"], "addressed")
        self.assertEqual(addressed["blocks"][0]["comment_count"], 0)

    def test_article_highlight_api_adds_removes_and_exports_cleanly(self):
        article = self.request("/api/article")
        updated = self.request(
            "/api/article/highlights",
            method="POST",
            payload={
                "expected_hash": article["hash"],
                "author": "Alice",
                "block_id": article["blocks"][0]["id"],
                "quote": "Hello",
                "prefix": "",
                "suffix": ".",
                "tone": "amber",
            },
        )

        self.assertEqual(len(updated["highlights"]), 1)
        highlight = updated["highlights"][0]
        self.assertEqual(highlight["author"], "Alice")
        self.assertEqual(highlight["quote"], "Hello")
        self.assertEqual(highlight["target"], updated["blocks"][0]["id"])
        source = self.document.read_text(encoding="utf-8")
        self.assertIn("%<editor-highlight", source)

        clean = self.request("/api/export/clean")
        self.assertNotIn(b"editor-highlight", clean)
        self.assertNotIn(b"text-anchor", clean)
        self.assertIn(b"Hello.", clean)

        removed = self.request(
            "/api/article/highlights/remove",
            method="POST",
            payload={
                "expected_hash": updated["hash"],
                "id": highlight["id"],
            },
        )
        self.assertEqual(removed["highlights"], [])


if __name__ == "__main__":
    unittest.main()
