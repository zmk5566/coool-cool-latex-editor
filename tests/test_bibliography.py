import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.bibliography import parse_bibtex  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
