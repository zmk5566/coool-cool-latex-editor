import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cool_cool_latex_editor.comments import strip_editor_metadata  # noqa: E402
from cool_cool_latex_editor.framing import parse_framings, strip_framing_metadata  # noqa: E402


SAMPLE = r'''\documentclass{article}
%<editor-framing
% id="abstract-proposal"
% section="abstract"
% section-label="Abstract"
% role="proposal"
% status="confirmed"
% order="30"
% relation="因此提出"
%>
% HexBlocks 连接意图、硬件与可检查行为
%<editor-framing-target source="sections/abstract.tex" target="ta-abstract" quote="We present HexBlocks."/>
%<editor-framing-target source="sections/introduction.tex" target="ta-intro" quote="We introduce HexBlocks." prefix="Therefore, "/>
%</editor-framing>
%<editor-framing
% id="abstract-method"
% section="abstract"
% role="method"
% status="proposed"
% order="40"
% parent="abstract-proposal"
% relation="由以下部分落实"
%>
% 形成性研究、专家会话、机制测试与可行性研究
%</editor-framing>
\begin{document}
Hello.
\end{document}
'''


class FramingTests(unittest.TestCase):
    def test_parses_chinese_argument_relationships_and_repeated_targets(self):
        items, warnings = parse_framings(SAMPLE)

        self.assertEqual(warnings, [])
        self.assertEqual([item.id for item in items], ["abstract-proposal", "abstract-method"])
        proposal, method = items
        self.assertEqual(proposal.section_label, "Abstract")
        self.assertEqual(proposal.role, "proposal")
        self.assertEqual(proposal.status, "confirmed")
        self.assertEqual(proposal.order, 30)
        self.assertEqual(proposal.relation, "因此提出")
        self.assertEqual(proposal.text, "HexBlocks 连接意图、硬件与可检查行为")
        self.assertEqual(len(proposal.targets), 2)
        self.assertEqual(proposal.targets[0].source_path, "sections/abstract.tex")
        self.assertEqual(proposal.targets[0].anchor, "ta-abstract")
        self.assertEqual(proposal.targets[1].prefix, "Therefore, ")
        self.assertEqual(method.parent, "abstract-proposal")

    def test_invalid_status_is_reported_and_record_is_skipped(self):
        source = SAMPLE.replace('% status="confirmed"', '% status="invented"', 1)

        items, warnings = parse_framings(source)

        self.assertEqual([item.id for item in items], ["abstract-method"])
        self.assertTrue(any("abstract-proposal" in warning and "status" in warning for warning in warnings))

    def test_stripping_removes_framing_and_targets_without_touching_latex(self):
        clean = strip_framing_metadata(SAMPLE)

        self.assertNotIn("editor-framing", clean)
        self.assertNotIn("editor-framing-target", clean)
        self.assertIn("\\begin{document}", clean)
        self.assertIn("Hello.", clean)
        self.assertEqual(strip_editor_metadata(SAMPLE), clean)


if __name__ == "__main__":
    unittest.main()
