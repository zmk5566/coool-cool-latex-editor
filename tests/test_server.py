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

    def write_multifile_document(self):
        sections = self.root / "sections"
        figures = self.root / "figures"
        sections.mkdir(exist_ok=True)
        figures.mkdir(exist_ok=True)
        included = sections / "one.tex"
        nested = figures / "deep.tex"
        self.document.write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "Root opening.\n\n"
            "\\input{sections/one}\n\n"
            "Root closing.\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        included.write_text(
            "\\section{Included section}\n"
            "\\label{sec:included}\n\n"
            "Included paragraph.\n\n"
            "\\input{figures/deep}\n",
            encoding="utf-8",
        )
        nested.write_text(
            "\\section{Deep section}\n\nDeep paragraph.\n",
            encoding="utf-8",
        )
        return included, nested

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

    def test_article_api_recursively_expands_input_files_in_order(self):
        self.write_multifile_document()

        article = self.request("/api/article")
        texts = [
            "".join(str(run.get("text", "")) for run in block["runs"])
            for block in article["blocks"]
        ]

        self.assertEqual(
            texts,
            [
                "Root opening.",
                "Included section",
                "Included paragraph.",
                "Deep section",
                "Deep paragraph.",
                "Root closing.",
            ],
        )
        self.assertEqual(
            [source["path"] for source in article["sources"]],
            ["draft/proposal.tex", "sections/one.tex", "figures/deep.tex"],
        )
        self.assertEqual(article["warnings"], [])
        self.assertEqual(article["blocks"][4]["source_path"], "figures/deep.tex")

    def test_project_renders_title_abstract_and_bibliography_citations(self):
        sections = self.root / "sections"
        sections.mkdir()
        abstract = sections / "abstract.tex"
        bibliography = self.root / "references.bib"
        self.document.write_text(
            "\\documentclass{article}\n"
            "\\newcommand{\\sysname}{\\textsc{HexBlocks}\\xspace}\n"
            "\\title{\\sysname: Connected authoring}\n"
            "\\begin{document}\n"
            "\\input{sections/abstract}\n"
            "\\bibliography{references}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        abstract.write_text(
            "\\begin{abstract}\n"
            "Prior work matters~\\cite{greenberg2001phidgets}.\n"
            "\\end{abstract}\n",
            encoding="utf-8",
        )
        bibliography.write_text(
            "@inproceedings{greenberg2001phidgets,\n"
            "  author={Greenberg, Saul and Fitchett, Chester},\n"
            "  title={Phidgets},\n"
            "  booktitle={Proceedings of the ACM Symposium},\n"
            "  year={2001},\n"
            "  pages={209--218},\n"
            "  doi={10.1145/502348.502388}\n"
            "}\n"
            "@article{uncited2026,\n"
            "  author={Unused, Alice},\n"
            "  title={Not in the rendered list},\n"
            "  year={2026}\n"
            "}\n",
            encoding="utf-8",
        )

        article = self.request("/api/article")

        self.assertEqual(
            [block["kind"] for block in article["blocks"]],
            ["title", "abstract-heading", "paragraph"],
        )
        self.assertEqual(
            "".join(run["text"] for run in article["blocks"][0]["runs"]),
            "HexBlocks: Connected authoring",
        )
        citation = next(
            run
            for run in article["blocks"][2]["runs"]
            if run.get("kind") == "citation"
        )
        self.assertEqual(citation["text"], "(Greenberg & Fitchett, 2001)")
        self.assertIn("Phidgets", citation["tooltip"])
        self.assertEqual(len(article["sources"]), 2)
        self.assertEqual(len(article["references"]), 1)
        reference = article["references"][0]
        self.assertEqual(reference["index"], 1)
        self.assertEqual(reference["key"], "greenberg2001phidgets")
        self.assertEqual(reference["authors"], "Saul Greenberg and Chester Fitchett")
        self.assertEqual(reference["venue"], "Proceedings of the ACM Symposium")
        self.assertEqual(reference["pages"], "209–218")
        self.assertEqual(reference["doi"], "10.1145/502348.502388")

        paragraph = article["blocks"][2]
        segments = [
            {"type": "token", "index": run["index"]}
            if run["type"] == "token"
            else {"type": "text", "value": run["text"]}
            for run in paragraph["runs"]
        ]
        saved = self.request(
            "/api/article/block",
            method="PUT",
            payload={
                "block_id": paragraph["id"],
                "segments": segments,
                "expected_hash": article["hash"],
            },
        )
        self.assertIn(
            "\\cite{greenberg2001phidgets}", abstract.read_text(encoding="utf-8")
        )
        self.assertNotIn("\\textbackslash{}cite", abstract.read_text(encoding="utf-8"))

        initial_hash = saved["hash"]
        bibliography.write_text(
            bibliography.read_text(encoding="utf-8").replace("2001", "2002"),
            encoding="utf-8",
        )
        status = self.request("/api/status")
        self.assertNotEqual(status["hash"], initial_hash)
        self.assertEqual(status["source_count"], 2)

    def test_recursive_article_edit_writes_to_the_origin_file(self):
        _included, nested = self.write_multifile_document()
        root_before = self.document.read_text(encoding="utf-8")
        article = self.request("/api/article")
        block = next(
            block
            for block in article["blocks"]
            if block["source_path"] == "figures/deep.tex" and block["kind"] == "paragraph"
        )

        updated = self.request(
            "/api/article/block",
            method="PUT",
            payload={
                "block_id": block["id"],
                "segments": [{"type": "text", "value": "Deep paragraph revised."}],
                "expected_hash": article["hash"],
            },
        )

        self.assertIn("Deep paragraph revised.", nested.read_text(encoding="utf-8"))
        self.assertEqual(self.document.read_text(encoding="utf-8"), root_before)
        self.assertTrue(
            any(
                item["source_path"] == "figures/deep.tex"
                and item["runs"][0]["text"] == "Deep paragraph revised."
                for item in updated["blocks"]
                if item["kind"] == "paragraph"
            )
        )

    def test_source_api_opens_and_saves_the_selected_included_file(self):
        included, _nested = self.write_multifile_document()
        root_before = self.document.read_text(encoding="utf-8")
        article = self.request("/api/article")

        source = self.request("/api/source?path=sections/one.tex")

        self.assertEqual(source["path"], "sections/one.tex")
        self.assertEqual(source["hash"], article["hash"])
        self.assertIn("Included paragraph.", source["content"])
        saved = self.request(
            "/api/source",
            method="PUT",
            payload={
                "path": "sections/one.tex",
                "content": source["content"].replace(
                    "Included paragraph.", "Included paragraph from Source mode."
                ),
                "expected_hash": article["hash"],
            },
        )

        self.assertIn("Included paragraph from Source mode.", included.read_text(encoding="utf-8"))
        self.assertEqual(self.document.read_text(encoding="utf-8"), root_before)
        self.assertTrue(
            any(
                block["source_path"] == "sections/one.tex"
                and "Included paragraph from Source mode."
                in "".join(run["text"] for run in block["runs"])
                for block in saved["blocks"]
            )
        )

    def test_citation_api_updates_tex_fields_and_referenced_bib_entry(self):
        sections = self.root / "sections"
        sections.mkdir()
        related = sections / "related.tex"
        bibliography = self.root / "references.bib"
        self.document.write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\input{sections/related}\n"
            "\\bibliography{references}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        related.write_text(
            "Prior work~\\cite{sample2024}.\n",
            encoding="utf-8",
        )
        bibliography.write_text(
            "@article{sample2024,\n"
            "  author = {Old, Alice},\n"
            "  title = {Original title},\n"
            "  year = {2024},\n"
            "  doi = {10.0000/example}\n"
            "}\n",
            encoding="utf-8",
        )
        article = self.request("/api/article")
        paragraph = article["blocks"][0]
        citation = next(run for run in paragraph["runs"] if run.get("kind") == "citation")

        updated = self.request(
            "/api/article/citation",
            method="PUT",
            payload={
                "block_id": paragraph["id"],
                "token_index": citation["index"],
                "command": "citet",
                "options": "[p. 8]",
                "keys": ["sample2024"],
                "bibliography": [
                    {
                        "key": "sample2024",
                        "author": "New, Alice and Other, Bob",
                        "title": "Revised title",
                        "year": "2026",
                    }
                ],
                "expected_hash": article["hash"],
            },
        )

        self.assertIn("\\citet[p. 8]{sample2024}", related.read_text(encoding="utf-8"))
        bib_source = bibliography.read_text(encoding="utf-8")
        self.assertIn("author = {New, Alice and Other, Bob}", bib_source)
        self.assertIn("title = {Revised title}", bib_source)
        self.assertIn("year = {2026}", bib_source)
        self.assertIn("doi = {10.0000/example}", bib_source)
        self.assertEqual(updated["bibliography"][0]["source_path"], "references.bib")
        updated_citation = next(
            run for run in updated["blocks"][0]["runs"] if run.get("kind") == "citation"
        )
        self.assertEqual(updated_citation["text"], "New & Other (2026)")
        self.assertIn("Revised title", updated_citation["tooltip"])

    def test_recursive_comments_and_highlights_stay_with_the_origin_file(self):
        included, nested = self.write_multifile_document()
        article = self.request("/api/article")
        included_block = next(
            block
            for block in article["blocks"]
            if block["source_path"] == "sections/one.tex" and block["kind"] == "paragraph"
        )
        commented = self.request(
            "/api/article/comments",
            method="POST",
            payload={
                "expected_hash": article["hash"],
                "author": "Alice",
                "body": "Comment in the included section.",
                "scope": "inline",
                "block_id": included_block["id"],
                "quote": "Included paragraph",
            },
        )
        comment = commented["comments"][0]

        self.assertIn("%<editor-comment", included.read_text(encoding="utf-8"))
        self.assertNotIn("%<editor-comment", self.document.read_text(encoding="utf-8"))
        self.assertEqual(comment["source_path"], "sections/one.tex")
        self.assertTrue(comment["target"].startswith("sections/one.tex::ta-"))

        deep_block = next(
            block
            for block in commented["blocks"]
            if block["source_path"] == "figures/deep.tex" and block["kind"] == "paragraph"
        )
        highlighted = self.request(
            "/api/article/highlights",
            method="POST",
            payload={
                "expected_hash": commented["hash"],
                "author": "Bob",
                "block_id": deep_block["id"],
                "quote": "Deep paragraph",
                "tone": "amber",
            },
        )

        self.assertIn("%<editor-highlight", nested.read_text(encoding="utf-8"))
        self.assertEqual(highlighted["highlights"][0]["source_path"], "figures/deep.tex")
        self.assertTrue(
            highlighted["highlights"][0]["target"].startswith("figures/deep.tex::ta-")
        )

        addressed = self.request(
            "/api/article/comments/status",
            method="POST",
            payload={
                "expected_hash": highlighted["hash"],
                "id": comment["id"],
                "status": "addressed",
            },
        )
        self.assertEqual(addressed["comments"][0]["status"], "addressed")
        self.assertIn('% status="addressed"', included.read_text(encoding="utf-8"))

    def test_status_api_detects_an_external_update_to_an_included_file(self):
        _included, nested = self.write_multifile_document()
        article = self.request("/api/article")

        nested.write_text(
            "\\section{Deep section}\n\nChanged outside the editor.\n",
            encoding="utf-8",
        )
        changed = self.request("/api/status")

        self.assertNotEqual(changed["hash"], article["hash"])
        self.assertEqual(changed["source_count"], 3)

    def test_missing_and_circular_inputs_report_warnings_without_crashing(self):
        sections = self.root / "sections"
        sections.mkdir()
        (sections / "cycle.tex").write_text(
            "Cycle text.\n\\input{draft/proposal}\n",
            encoding="utf-8",
        )
        self.document.write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "Before.\n"
            "\\input{sections/cycle}\n"
            "\\input{sections/missing}\n"
            "After.\n"
            "\\end{document}\n",
            encoding="utf-8",
        )

        article = self.request("/api/article")

        self.assertTrue(any("Circular include skipped" in item for item in article["warnings"]))
        self.assertTrue(any("Included file not found" in item for item in article["warnings"]))
        self.assertGreaterEqual(len(article["blocks"]), 3)

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
