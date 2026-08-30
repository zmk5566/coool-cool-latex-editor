import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.bibliography import (  # noqa: E402
    parse_bibtex,
    update_bibtex_entry,
)


class BibliographyTests(unittest.TestCase):
    def test_parses_nested_bibtex_fields_and_builds_author_year_labels(self):
        source = r"""
@inproceedings{greenberg2001phidgets,
  author = {Greenberg, Saul and Fitchett, Chester},
  title = {Phidgets: Easy Development of {Physical Interfaces}},
  year = {2001},
}
@article{villar2011gadgeteer,
  author = "Villar, Nicolas and Scott, James and Hodges, Steve",
  title = "Gadgeteer",
  year = 2011,
}
"""

        entries = parse_bibtex(source)

        self.assertEqual(entries["greenberg2001phidgets"].label, "Greenberg & Fitchett, 2001")
        self.assertEqual(entries["villar2011gadgeteer"].label, "Villar et al., 2011")
        self.assertIn("Physical Interfaces", entries["greenberg2001phidgets"].tooltip)

    def test_updates_selected_fields_without_reformatting_the_entry(self):
        source = """@article{sample,
  author = {Old, Alice},
  title = {A {Nested} Title},
  year = 2024,
  doi = {10.0000/example}
}
"""

        updated = update_bibtex_entry(
            source,
            "sample",
            {"author": "New, Alice and Other, Bob", "title": "A Revised {Title}", "year": "2026"},
        )

        self.assertIn("author = {New, Alice and Other, Bob}", updated)
        self.assertIn("title = {A Revised {Title}}", updated)
        self.assertIn("year = 2026", updated)
        self.assertIn("doi = {10.0000/example}", updated)

    def test_adds_a_missing_editable_field(self):
        source = "@misc{sample,\n  title = {Only a title}\n}\n"

        updated = update_bibtex_entry(source, "sample", {"year": "2026"})

        self.assertIn("year     = {2026},", updated)


if __name__ == "__main__":
    unittest.main()
