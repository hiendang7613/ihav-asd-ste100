"""The session audit reads transcripts only and checks the last full-format reply of each recent session."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_check_reply import FULL  # noqa: E402


def line(kind, text, stamp="2026-10-04T08:00:00Z"):
    return json.dumps({"type": kind, "timestamp": stamp, "message": {"content": [{"type": "text", "text": text}]}})


class AuditSessionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste audit ")
        self.projects = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, project, name, *lines, age_minutes=0):
        folder = self.projects / project
        folder.mkdir(exist_ok=True)
        path = folder / ("%s.jsonl" % name)
        path.write_text("\n".join(lines) + "\n")
        stamp = time.time() - age_minutes * 60
        os.utime(path, (stamp, stamp))
        return path

    def run_audit(self, *args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/audit_sessions.py"), "--projects-dir",
                                 str(self.projects), "--json", *args], capture_output=True, text=True, timeout=30)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip().startswith("[") else result.stdout

    def test_checks_the_last_full_reply_of_each_recent_session(self):
        old_shape = FULL.replace("0. **Goals:**", "0. **Done:**")
        self.session("room-a", "s1", line("assistant", old_shape), line("user", "next"), line("assistant", FULL),
                     line("assistant", "Short answer."))
        self.session("room-b", "s2", line("assistant", old_shape), "not json")
        self.session("room-c", "s3", line("assistant", old_shape), age_minutes=500)
        before = {p: p.read_bytes() for p in self.projects.rglob("*.jsonl")}
        code, rows = self.run_audit()
        self.assertEqual(code, 1)
        by_project = {row["project"]: row for row in rows}
        self.assertEqual(set(by_project), {"room-a", "room-b"})
        self.assertTrue(by_project["room-a"]["ok"], by_project["room-a"])
        self.assertFalse(by_project["room-b"]["ok"])
        self.assertTrue(any("Section 0 label must be 'Goals'" in v for v in by_project["room-b"]["violations"]))
        self.assertEqual({p: p.read_bytes() for p in self.projects.rglob("*.jsonl")}, before)

    def test_text_output_shows_warnings_and_nothing_is_written(self):
        copy = Path(self.tmp.name) / "copy"
        (copy / "scripts").mkdir(parents=True)
        for name in ("audit_sessions.py", "check_reply.py"):
            (copy / "scripts" / name).write_bytes((ROOT / "scripts" / name).read_bytes())
        no_aims = FULL.replace("   - **L1.** [~80%] [########--] | Users can log in from every client.\n", "")
        self.session("room-a", "s1", line("assistant", no_aims))
        before = sorted(p for p in Path(self.tmp.name).rglob("*"))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        result = subprocess.run([sys.executable, str(copy / "scripts/audit_sessions.py"), "--projects-dir",
                                 str(self.projects)], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK   room-a", result.stdout)
        self.assertIn("warning: Goals has no L line", result.stdout)
        self.assertEqual(sorted(p for p in Path(self.tmp.name).rglob("*")), before)

    def test_window_and_usage(self):
        self.session("room-c", "s3", line("assistant", FULL), age_minutes=500)
        self.assertEqual(self.run_audit(), (0, []))
        code, rows = self.run_audit("--since-minutes", "600")
        self.assertEqual((code, len(rows)), (0, 1))
        self.assertEqual(self.run_audit("--since-minutes", "soon")[0], 2)
        self.assertEqual(self.run_audit("--bogus", "1")[0], 2)


if __name__ == "__main__":
    unittest.main()
