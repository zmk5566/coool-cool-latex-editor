import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.comments import (  # noqa: E402
    add_comment,
    format_highlight,
    parse_comments,
    parse_highlights,
    remove_highlight,
    set_comment_status,
    strip_editor_metadata,
)


SAMPLE = """\\documentclass{article}
\\begin{document}
First paragraph.

Second paragraph.
\\end{document}
"""


class CommentTests(unittest.TestCase):
    def test_overall_comment_round_trip_and_clean_export(self):
        updated, comment_id = add_comment(
            SAMPLE,
            author="Alice",
            body="Tighten the abstract.",
            scope="document",
        )
        comments = parse_comments(updated)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].id, comment_id)
        self.assertEqual(comments[0].author, "Alice")
        self.assertEqual(comments[0].scope, "document")
        self.assertEqual(comments[0].body, "Tighten the abstract.")
        self.assertEqual(strip_editor_metadata(updated), SAMPLE)

    def test_inline_comment_targets_selected_line(self):
        updated, _ = add_comment(
            SAMPLE,
            author="Zhengyang",
            body="This turn is too fast.",
            scope="inline",
            line_start=3,
            line_end=3,
        )
        comment = parse_comments(updated)[0]
        self.assertEqual(comment.scope, "inline")
        self.assertEqual(comment.target_line, 4)
        self.assertIn("First paragraph.\n%<editor-comment", updated)
        self.assertEqual(strip_editor_metadata(updated), SAMPLE)

    def test_status_can_be_changed_and_reopened(self):
        updated, comment_id = add_comment(
            SAMPLE,
            author="A",
            body="Comment",
            scope="document",
        )
        addressed = set_comment_status(updated, comment_id, "addressed")
        self.assertEqual(parse_comments(addressed)[0].status, "addressed")
        reopened = set_comment_status(addressed, comment_id, "open")
        self.assertEqual(parse_comments(reopened)[0].status, "open")

    def test_multiline_comment_text_is_preserved(self):
        updated, _ = add_comment(
            SAMPLE,
            author="A",
            body="First line.\n\nSecond line.",
            scope="document",
        )
        self.assertEqual(parse_comments(updated)[0].body, "First line.\n\nSecond line.")

    def test_highlight_round_trip_removal_and_clean_export(self):
        metadata = format_highlight(
            highlight_id="eh-a82f1c",
            author="Alice",
            target="ta-d0518f21",
            quote="First paragraph",
            prefix="Before ",
            suffix=". After",
            created="2026-08-29T12:00:00+00:00",
        )
        updated = SAMPLE.replace(
            "First paragraph.\n",
            '%<text-anchor id="ta-d0518f21"/>\nFirst paragraph.\n' + metadata,
        )

        highlights = parse_highlights(updated)
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0].id, "eh-a82f1c")
        self.assertEqual(highlights[0].author, "Alice")
        self.assertEqual(highlights[0].target, "ta-d0518f21")
        self.assertEqual(highlights[0].quote, "First paragraph")
        self.assertEqual(highlights[0].tone, "amber")
        self.assertEqual(strip_editor_metadata(updated), SAMPLE)

        removed = remove_highlight(updated, "eh-a82f1c")
        self.assertEqual(parse_highlights(removed), [])
        self.assertIn('%<text-anchor id="ta-d0518f21"/>', removed)


if __name__ == "__main__":
    unittest.main()
