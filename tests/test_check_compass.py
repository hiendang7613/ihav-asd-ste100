"""The Compass lint warns about long lines, repeated IDs and ignored bullets, and agrees with the hook on what is active."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_compass import lint  # noqa: E402

LAUNCH = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
SAMPLE = ("# Header comment\n## V Vision\n- V1 Connect many vendors; own no complex harness.\n- V2 The admin chats only through the UI.\n"
          "## W Work habits\n- W5? A proposed line.\n- c1 Lower case letters work too.\n")


class CompassLintTests(unittest.TestCase):
    def test_counts_active_and_proposed_lines_without_warnings(self):
        report = lint(SAMPLE)
        self.assertEqual((report["active"], report["proposed"], report["warnings"]), (3, 1, []))
        self.assertEqual(report["tokens_per_turn"], round(report["injected_bytes"] / 4))

    def test_a_line_over_fifteen_words_is_kept_but_warned(self):
        long = "- V3 " + " ".join(["word"] * 16) + "\n"
        report = lint(SAMPLE + long)
        self.assertEqual(report["active"], 4)
        self.assertTrue(any("line 8 (V3) has 16 words (limit 15)" in w for w in report["warnings"]), report["warnings"])
        self.assertEqual(lint(SAMPLE + "- V3 " + " ".join(["word"] * 15) + "\n")["warnings"], [])

    def test_repeated_ids_and_ignored_bullets_are_warned(self):
        report = lint(SAMPLE + "- V1 Again.\n- V3: colon after the ID.\n-V4 no space.\n- 5 digit first.\n")
        self.assertTrue(any("repeats the ID V1" in w for w in report["warnings"]), report["warnings"])
        self.assertTrue(any("without a valid ID" in w and "V3:" in w for w in report["warnings"]), report["warnings"])
        self.assertEqual(sum("without a valid ID" in w for w in report["warnings"]), 2)  # "-V4" is not a bullet

    def test_the_hook_caps_are_reported(self):
        many = "".join("- V%d Line number %d.\n" % (n, n) for n in range(1, 70))
        self.assertTrue(any("at most 60 active lines" in w for w in lint(many)["warnings"]))

    def test_the_command_line_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "compass.md"
            file.write_text(SAMPLE)
            run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts/check_compass.py"), *a], capture_output=True, text=True)  # noqa: E731
            result = run(str(file))
            self.assertEqual((result.returncode, result.stdout.splitlines()[0][:23]), (0, "active 3, proposed 1, a"))
            self.assertEqual(json.loads(run(str(file), "--json").stdout)["active"], 3)
            self.assertEqual(run(str(Path(folder) / "missing.md")).returncode, 1)
            self.assertEqual(run().returncode, 2)

    def test_the_lint_and_the_hook_agree_on_the_active_lines(self):
        with tempfile.TemporaryDirectory(prefix="ste lint ") as folder:
            home = Path(folder)
            for name in (".claude", ".codex", "project/.git", "project/.ihav_space/ihav-asd-ste100"):
                (home / name).mkdir(parents=True)
            (home / "project/.ihav_space/ihav-asd-ste100/compass.md").write_text(SAMPLE)
            env = {"PATH": os.environ["PATH"], "HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                   "CODEX_HOME": str(home / ".codex"), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
            payload = {"hook_event_name": "UserPromptSubmit", "session_id": "l", "prompt": "hi", "cwd": str(home / "project")}
            out = subprocess.run(["sh", "-c", LAUNCH], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=30)
            context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("harness; V2 The admin chats only through the UI; c1 Lower case letters work too. Show X.", context)
            self.assertNotIn("W5", context)


if __name__ == "__main__":
    unittest.main()
