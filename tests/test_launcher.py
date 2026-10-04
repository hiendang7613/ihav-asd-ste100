"""The stable launcher runs the active release named by the pointer, and its own copy when any check fails."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
PROMPT = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "hi"}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste launcher ")
        self.home = Path(self.tmp.name)
        for name in (".claude", ".codex", "tmp", ".ihav"):
            (self.home / name).mkdir()
        self.base = self.home / ".claude/plugins/cache/ihav/ihav-asd-ste100"
        self.base.mkdir(parents=True)
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
                    "CODEX_HOME": str(self.home / ".codex"), "TMPDIR": str(self.home / "tmp"),
                    "IHAV_HOME": str(self.home / ".ihav"), "CLAUDE_PLUGIN_ROOT": str(ROOT)}

    def tearDown(self):
        self.tmp.cleanup()

    def release(self, version, word="v9", where=None):
        """Copy this repository's plugin files as an installed release whose reminder carries a marker word."""
        target = (where or self.base) / version
        for part in ("hooks", "skills", "scripts", ".claude-plugin"):
            shutil.copytree(ROOT / part, target / part)
        core = target / "hooks/ste-core.mjs"
        core.write_text(core.read_text().replace("Reply shape:", "Reply shape %s:" % word))
        manifest = target / ".claude-plugin/plugin.json"
        manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {"version": version}))
        return target

    def point(self, root, **fields):
        pointer = self.home / ".ihav/active/ihav-asd-ste100.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"root": str(root), "version": "x", "launcher_protocol": 1} | fields))
        pointer.chmod(0o644)
        return pointer

    def hook(self, payload=PROMPT):
        result = subprocess.run(["sh", "-c", LAUNCH], input=json.dumps(payload), capture_output=True, text=True,
                                env=self.env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def activate(self, *args):
        return subprocess.run(["node", str(ROOT / "scripts/activate.mjs"), *args], capture_output=True, text=True,
                              env=self.env, timeout=60)

    def test_no_pointer_runs_the_own_copy(self):
        out = self.hook()
        self.assertIn("Reply shape:", out)

    def test_a_valid_pointer_runs_the_active_release(self):
        self.point(self.release("9.9.9"))
        self.assertIn("Reply shape v9:", self.hook())

    def test_every_failed_check_falls_back_to_the_own_copy(self):
        outside = self.release("9.9.9", where=self.home / "elsewhere")
        empty = self.base / "8.8.8"
        empty.mkdir()
        cases = {
            "outside the cache": lambda: self.point(outside),
            "no core file": lambda: self.point(empty),
            "wrong protocol": lambda: self.point(self.release("9.9.1"), launcher_protocol=2),
            "group-writable pointer": lambda: self.point(self.release("9.9.2")).chmod(0o664),
            "malformed json": lambda: (self.home / ".ihav/active").mkdir(parents=True, exist_ok=True)
            or (self.home / ".ihav/active/ihav-asd-ste100.json").write_text("{not json"),
        }
        for name, setup in cases.items():
            with self.subTest(case=name):
                setup()
                out = self.hook()
                self.assertIn("Reply shape:", out)
                self.assertNotIn("Reply shape v9", out)

    def test_a_symlink_out_of_the_cache_is_refused(self):
        outside = self.release("9.9.9", where=self.home / "elsewhere")
        (self.base / "9.9.9").symlink_to(outside)
        self.point(self.base / "9.9.9")
        self.assertNotIn("Reply shape v9", self.hook())

    def test_a_broken_active_core_falls_back(self):
        broken = self.release("9.9.9")
        (broken / "hooks/ste-core.mjs").write_text("this is not javascript (")
        self.point(broken)
        self.assertIn("Reply shape:", self.hook())

    def test_a_new_active_version_reinjects_the_rules_once(self):
        self.hook({"hook_event_name": "SessionStart", "session_id": "s1"})
        self.assertNotIn("RULES UPDATED", self.hook())
        self.point(self.release("9.9.9"))
        first = self.hook()
        self.assertTrue(first.startswith("STE REPLY RULES UPDATED to 9.9.9"), first[:80])
        self.assertIn("## The shape", first)
        self.assertIn("Reply shape v9:", first)
        second = self.hook()
        self.assertNotIn("RULES UPDATED", second)
        self.assertIn("Reply shape v9:", second)

    def test_a_bridged_old_session_gets_the_rules_once(self):
        self.point(self.release("9.9.9"))
        self.env["IHAV_STE100_BRIDGED"] = "1"
        first = self.hook()
        self.assertTrue(first.startswith("STE REPLY RULES UPDATED to 9.9.9 (was a release before 0.18.0)"), first[:90])
        self.assertNotIn("RULES UPDATED", self.hook())
        del self.env["IHAV_STE100_BRIDGED"]
        self.assertNotIn("RULES UPDATED", self.hook(dict(PROMPT, session_id="fresh")))

    def test_activate_smoke_checks_writes_previous_and_rolls_back(self):
        first, second = self.release("9.9.8", word="v8"), self.release("9.9.9")
        self.assertEqual(self.activate("--root", str(first)).returncode, 0)
        result = self.activate("--root", str(second))
        self.assertEqual(result.returncode, 0, result.stderr)
        pointer = json.loads((self.home / ".ihav/active/ihav-asd-ste100.json").read_text())
        self.assertEqual((pointer["version"], pointer["launcher_protocol"]), ("9.9.9", 1))
        self.assertEqual(pointer["previous"]["version"], "9.9.8")
        self.assertIn("Reply shape v9:", self.hook())
        self.assertEqual(self.activate("--rollback").returncode, 0)
        self.assertIn("Reply shape v8:", self.hook())

    def test_activating_the_active_release_again_keeps_the_rollback_target(self):
        first, second = self.release("9.9.8", word="v8"), self.release("9.9.9")
        for root in (first, second, second):
            self.assertEqual(self.activate("--root", str(root)).returncode, 0)
        pointer = json.loads((self.home / ".ihav/active/ihav-asd-ste100.json").read_text())
        self.assertEqual(pointer["previous"]["version"], "9.9.8")
        self.assertEqual(self.activate("--rollback").returncode, 0)
        self.assertIn("Reply shape v8:", self.hook())

    def test_an_unreadable_new_skill_body_is_injected_after_repair(self):
        self.hook({"hook_event_name": "SessionStart", "session_id": "s1"})
        new = self.release("9.9.9")
        self.point(new)
        skill = new / "skills/ihav-asd-ste100/SKILL.md"
        body = skill.read_text()
        skill.unlink()
        self.assertEqual(self.hook(), "")
        skill.write_text(body)
        repaired = self.hook()
        self.assertTrue(repaired.startswith("STE REPLY RULES UPDATED to 9.9.9"), repaired[:80])
        self.assertNotIn("RULES UPDATED", self.hook())

    def test_activate_refuses_a_failing_or_outside_release(self):
        good = self.release("9.9.8", word="v8")
        self.assertEqual(self.activate("--root", str(good)).returncode, 0)
        before = (self.home / ".ihav/active/ihav-asd-ste100.json").read_text()
        broken = self.release("9.9.9")
        (broken / "hooks/ste-core.mjs").write_text("process.stdout.write('nothing')\n")
        outside = self.release("9.9.7", where=self.home / "elsewhere")
        for root in (broken, outside):
            with self.subTest(root=root.name):
                result = self.activate("--root", str(root))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("unchanged", result.stderr)
                self.assertEqual((self.home / ".ihav/active/ihav-asd-ste100.json").read_text(), before)
        self.assertEqual(self.activate("--bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
