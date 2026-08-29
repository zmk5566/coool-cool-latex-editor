import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.article import (
    add_article_comment,
    add_article_highlight,
    parse_article,
    update_article_block,
)
from cool_cool_latex_editor.comments import parse_comments, parse_highlights
from cool_cool_latex_editor.bibliography import BibliographyEntry


BS = chr(92)
SAMPLE = "\n".join(
    [
        BS + "documentclass{article}",
        BS + "newcommand{" + BS + "judgment}{Alice}",
        BS + "begin{document}",
        BS + "begin{center}",
        "{" + BS + "small PRELIMINARY PROPOSAL}" + BS + "par",
        "{" + BS + "Large" + BS + "bfseries A Small Proposal}" + BS + "par",
        "{" + BS + "large A readable subtitle}" + BS + "par",
        BS + "end{center}",
        "",
        BS + "section*{First turn}",
        "",
        "Plain text with "
        + BS
        + "emph{protected emphasis}, $x "
        + BS
        + "vdash y$, and "
        + BS
        + "judgment{}.",
        "",
        BS + "begin{itemize}",
        BS + "item One item",
        BS + "end{itemize}",
        BS + "end{document}",
        "",
    ]
)


class ArticleTests(unittest.TestCase):
    def test_keeps_document_title_abstract_label_and_readable_citations(self):
        source = "\n".join(
            [
                BS + "documentclass{article}",
                BS + "newcommand{" + BS + "sysname}{" + BS + "textsc{HexBlocks}" + BS + "xspace}",
                BS + "title{" + BS + "sysname: A useful title}",
                BS + "begin{document}",
                BS + "maketitle",
                BS + "begin{abstract}",
                "An abstract with " + BS + "sysname and prior work~" + BS + "cite{greenberg2001phidgets}.",
                BS + "end{abstract}",
                BS + "end{document}",
            ]
        )
        bibliography = {
            "greenberg2001phidgets": BibliographyEntry(
                key="greenberg2001phidgets",
                author="Greenberg, Saul and Fitchett, Chester",
                year="2001",
                title="Phidgets",
            )
        }

        blocks = parse_article(source, bibliography=bibliography)

        self.assertEqual(
            [block.kind for block in blocks],
            ["title", "abstract-heading", "paragraph"],
        )
        self.assertEqual(
            "".join(str(run["text"]) for run in blocks[0].runs),
            "HexBlocks: A useful title",
        )
        self.assertFalse(blocks[1].public_dict()["editable"])
        paragraph = blocks[2]
        self.assertEqual([token.kind for token in paragraph.tokens], ["macro", "citation"])
        citation = paragraph.tokens[1].public_dict()
        self.assertEqual(citation["text"], "(Greenberg & Fitchett, 2001)")
        self.assertIn("Phidgets", citation["tooltip"])

        updated = update_article_block(
            source,
            paragraph.id,
            [
                {"type": "text", "value": "Revised with "},
                {"type": "token", "index": 0},
                {"type": "text", "value": " and "},
                {"type": "token", "index": 1},
                {"type": "text", "value": "."},
            ],
            bibliography=bibliography,
        )
        self.assertIn(BS + "sysname and " + BS + "cite{greenberg2001phidgets}", updated)

    def test_recovers_a_citation_escaped_by_an_older_editor_version(self):
        source = "\n".join(
            [
                BS + "documentclass{article}",
                BS + "begin{document}",
                "Prior work "
                + BS
                + "textbackslash{}cite"
                + BS
                + "{greenberg2001phidgets"
                + BS
                + "}.",
                BS + "end{document}",
            ]
        )
        bibliography = {
            "greenberg2001phidgets": BibliographyEntry(
                key="greenberg2001phidgets",
                author="Greenberg, Saul and Fitchett, Chester",
                year="2001",
            )
        }

        paragraph = parse_article(source, bibliography=bibliography)[0]

        self.assertEqual(paragraph.tokens[0].kind, "citation")
        self.assertEqual(paragraph.tokens[0].source, BS + "cite{greenberg2001phidgets}")
        self.assertIn("saving this paragraph repairs it", paragraph.tokens[0].tooltip)
        updated = update_article_block(
            source,
            paragraph.id,
            [
                {"type": "text", "value": "Prior work "},
                {"type": "token", "index": 0},
                {"type": "text", "value": "."},
            ],
            bibliography=bibliography,
        )
        self.assertIn(BS + "cite{greenberg2001phidgets}", updated)
        self.assertNotIn(BS + "textbackslash{}cite", updated)

    def test_parses_included_fragment_and_skips_non_prose_figure_source(self):
        fragment = "\n".join(
            [
                BS + "section{A nested section}",
                BS + "label{sec:nested}",
                "Readable prose.",
                BS + "subsection{Nested detail}",
                "Detail prose.",
                BS + "begin{figure*}",
                BS + "begin{tikzpicture}",
                BS + "node {Implementation diagram internals};",
                BS + "end{tikzpicture}",
                BS + "caption{A figure caption}",
                BS + "end{figure*}",
                "Prose after the figure.",
            ]
        )

        blocks = parse_article(fragment, allow_fragment=True)

        self.assertEqual(
            ["".join(str(run["text"]) for run in block.runs) for block in blocks],
            [
                "A nested section",
                "Readable prose.",
                "Nested detail",
                "Detail prose.",
                "Prose after the figure.",
            ],
        )
        self.assertEqual([blocks[0].heading_level, blocks[2].heading_level], [1, 2])

    def test_parses_semantic_blocks_without_latex_scaffolding(self):
        blocks = parse_article(SAMPLE)

        self.assertEqual(
            [block.kind for block in blocks],
            ["title", "subtitle", "heading", "paragraph", "list-item"],
        )
        self.assertEqual(blocks[0].runs[0]["text"], "A Small Proposal")
        paragraph = blocks[3]
        self.assertEqual(
            [token.kind for token in paragraph.tokens],
            ["emphasis", "formula", "formula"],
        )
        self.assertIn(
            "Plain text with protected emphasis, x ⊢ y, and Alice; AI_Collar ⊢ 我 : Dog.",
            "".join(str(run["text"]) for run in paragraph.runs),
        )

    def test_round_trip_edits_text_and_preserves_latex_tokens(self):
        paragraph = parse_article(SAMPLE)[3]
        updated = update_article_block(
            SAMPLE,
            paragraph.id,
            [
                {"type": "text", "value": "Revised & "},
                {"type": "token", "index": 0},
                {"type": "text", "value": " plus "},
                {"type": "token", "index": 1},
                {"type": "text", "value": " and "},
                {"type": "token", "index": 2},
                {"type": "text", "value": "."},
            ],
        )

        expected = (
            "Revised "
            + BS
            + "& "
            + BS
            + "emph{protected emphasis} plus $x "
            + BS
            + "vdash y$ and "
            + BS
            + "judgment{}."
        )
        self.assertIn(expected, updated)
        reparsed = parse_article(updated)[3]
        self.assertEqual(
            [token.source for token in reparsed.tokens],
            [
                BS + "emph{protected emphasis}",
                "$x " + BS + "vdash y$",
                BS + "judgment{}",
            ],
        )

    def test_rejects_removed_or_reordered_protected_tokens(self):
        paragraph = parse_article(SAMPLE)[3]
        with self.assertRaisesRegex(ValueError, "cannot be removed or reordered"):
            update_article_block(
                SAMPLE,
                paragraph.id,
                [{"type": "text", "value": "Only plain text remains."}],
            )

    def test_inline_comment_creates_stable_anchor_and_quote(self):
        paragraph = parse_article(SAMPLE)[3]
        updated = add_article_comment(
            SAMPLE,
            author="Alice",
            body="Make this opening less report-like.",
            scope="inline",
            block_id=paragraph.id,
            quote="Plain text with protected emphasis",
            prefix="Before ",
            suffix=", after",
        )

        anchored = parse_article(updated)[3]
        self.assertTrue(anchored.id.startswith("ta-"))
        self.assertEqual(anchored.comment_count, 1)
        comment = parse_comments(updated)[0]
        self.assertEqual(comment.target, anchored.id)
        self.assertEqual(comment.quote, "Plain text with protected emphasis")
        self.assertEqual(comment.prefix, "Before ")
        self.assertEqual(comment.suffix, ", after")

        edited = update_article_block(
            updated,
            anchored.id,
            [
                {"type": "text", "value": "A gentler opening with "},
                {"type": "token", "index": 0},
                {"type": "text", "value": ", "},
                {"type": "token", "index": 1},
                {"type": "text", "value": ", and "},
                {"type": "token", "index": 2},
                {"type": "text", "value": "."},
            ],
        )
        self.assertEqual(parse_article(edited)[3].id, anchored.id)

    def test_overall_comment_stays_out_of_article_blocks(self):
        updated = add_article_comment(
            SAMPLE,
            author="Bob",
            body="The overall shape works.",
            scope="document",
        )
        self.assertEqual(len(parse_article(updated)), 5)
        self.assertEqual(parse_comments(updated)[0].scope, "document")

    def test_inline_highlight_creates_stable_anchor_and_metadata(self):
        paragraph = parse_article(SAMPLE)[3]
        updated = add_article_highlight(
            SAMPLE,
            author="Alice",
            block_id=paragraph.id,
            quote="protected emphasis",
            prefix="Plain text with ",
            suffix=", x ⊢ y",
        )

        anchored = parse_article(updated)[3]
        highlight = parse_highlights(updated)[0]
        self.assertTrue(anchored.id.startswith("ta-"))
        self.assertEqual(highlight.target, anchored.id)
        self.assertEqual(highlight.author, "Alice")
        self.assertEqual(highlight.quote, "protected emphasis")
        self.assertEqual(highlight.tone, "amber")
        self.assertEqual(len(parse_article(updated)), 5)


if __name__ == "__main__":
    unittest.main()
