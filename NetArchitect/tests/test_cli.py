import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from netarchitect.cli import main


class CLITests(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_end_to_end_and_safe_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"export"
            args = ["plan","--preset","campus","--out",str(target)]
            self.assertEqual(self.invoke(args)[0],0)
            self.assertTrue((target/"report.html").is_file())
            self.assertTrue(json.loads((target/"offline_checks.json").read_text())["passed"])
            self.assertEqual(self.invoke(args)[0],2)
            (target/"my-notes.txt").write_text("Keep this")
            self.assertEqual(self.invoke(args+["--force"])[0],0)
            self.assertEqual((target/"my-notes.txt").read_text(),"Keep this")

    def test_malformed_and_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"bad.json"
            path.write_text("{")
            result = self.invoke(["plan","--input",str(path),"--out",str(Path(tmp)/"out")])
            self.assertEqual(result[0],2)
            self.assertNotIn("Traceback",result[2])
            path.write_text("null")
            self.assertEqual(self.invoke(["plan","--input",str(path),"--out",str(Path(tmp)/"out")])[0],2)

    def test_custom_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, text, _ = self.invoke(["preset","metro"])
            self.assertEqual(status,0)
            data = json.loads(text)
            data["sites"][1]["groups"][0]["hosts"] = 120
            input_path = Path(tmp)/"custom.json"
            input_path.write_text(json.dumps(data))
            self.assertEqual(self.invoke(["plan","--input",str(input_path),"--out",str(Path(tmp)/"out")])[0],0)
