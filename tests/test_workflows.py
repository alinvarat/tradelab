"""Structure checks for the workflow files (stdlib only), so a misplaced edit fails CI instead of silently disabling
the workflow (2026-11-24: the l4f job was inserted inside workflow_dispatch inputs and GitHub dropped the workflow)."""
import re
import unittest
from pathlib import Path

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def keys_at(lines, start, indent):
    """Keys at exactly `indent` spaces from line `start` until the block ends (a line with less indentation)."""
    out = []
    for line in lines[start:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        if ind < indent:
            break
        m = re.match(r"^ {%d}([A-Za-z0-9_-]+):" % indent, line)
        if m:
            out.append(m.group(1))
    return out


class ResearchWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = (WF / "research.yml").read_text()
        self.lines = self.text.splitlines()

    def block(self, key, indent):
        i = next(n for n, l in enumerate(self.lines) if re.match(r"^ {%d}%s:\s*$" % (indent, re.escape(key)), l))
        return keys_at(self.lines, i + 1, indent + 2)

    def test_triggers_and_inputs(self):
        self.assertEqual(self.block("on", 0), ["workflow_dispatch", "schedule"])   # no push trigger
        self.assertEqual(self.block("inputs", 4), ["study"])

    def test_jobs(self):
        self.assertEqual(sorted(self.block("jobs", 0)), ["forward", "l4f", "options", "study"])

    def test_every_matrix_study_exists_in_run_py(self):
        run = (WF.parent.parent / "research" / "studies" / "run.py").read_text()
        studies = re.search(r"study: \[([^\]]+)\]", self.text).group(1).split(",")
        for s in (x.strip() for x in studies):
            self.assertIn(f'"{s}":', run, s)

    def test_no_tabs(self):
        self.assertNotIn("\t", self.text)


if __name__ == "__main__":
    unittest.main()
