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
        shutil.copy(ROOT / "CHANGELOG.md", target / "CHANGELOG.md")
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
        if payload.get("hook_event_name") == "UserPromptSubmit" and result.stdout:
            data = json.loads(result.stdout)
            self.assertNotIn("decision", data)
            self.assertNotIn("continue", data)
            specific = data["hookSpecificOutput"]
            self.assertEqual(specific["hookEventName"], "UserPromptSubmit")
            self.assertIsInstance(specific["additionalContext"], str)
            return specific["additionalContext"]
        return result.stdout

    def activate(self, *args):
        return subprocess.run(["node", str(ROOT / "scripts/activate.mjs"), *args], capture_output=True, text=True,
                              env=self.env, timeout=60)

    def legacy_release(self, version, prompt="[ihav-asd-ste100] Reply shape: legacy STE reminder.\n",
                       stderr="", exit_code=0):
        """Replay the old release's output independently of the current JSON core."""
        target = self.release(version)
        (target / "hooks/ste-core.mjs").write_text(
            'import fs from "node:fs";\n'
            'const input = JSON.parse(fs.readFileSync(0, "utf8"));\n'
            'if (input.hook_event_name === "SessionStart") {\n'
            '  process.stdout.write("STE REPLY MODE ACTIVE\\n");\n'
            '} else {\n'
            '  process.stdout.write(%s);\n'
            '  process.stderr.write(%s);\n'
            '  process.exitCode = %d;\n'
            '}\n' % (json.dumps(prompt), json.dumps(stderr), exit_code))
        return target

    def test_no_pointer_runs_the_own_copy(self):
        out = self.hook()
        self.assertIn("Reply shape:", out)

    def test_a_valid_pointer_runs_the_active_release(self):
        self.point(self.release("9.9.9"))
        self.assertIn("Reply shape v9:", self.hook())

    def test_a_foreign_plugin_root_keeps_claude_state_and_pointer(self):
        self.point(self.release("9.9.9"))
        for manifest_dir in (".codex-plugin", ".claude-plugin"):
            with self.subTest(manifest=manifest_dir):
                foreign = self.home / "foreign plugin" / manifest_dir
                manifest = foreign / manifest_dir / "plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"name": "ihav-agent-room", "version": "0.8.1"}))
                self.env["PLUGIN_ROOT"] = str(foreign)
                session = "foreign_" + manifest_dir.lstrip(".")
                self.hook({"hook_event_name": "SessionStart", "session_id": session})
                self.assertIn("Reply shape v9:", self.hook(dict(PROMPT, session_id=session)))
                marker = ".ihav-asd-ste100-sessions/" + session + ".version"
                self.assertEqual((self.home / ".claude" / marker).read_text().strip(), "9.9.9")
                self.assertFalse((self.home / ".codex" / marker).exists())

    def test_a_deleted_foreign_cache_root_keeps_claude_state_and_pointer(self):
        self.point(self.release("9.9.9"))
        foreign = self.home / ".codex/plugins/cache/ihav-agent-room-local/ihav-agent-room/0.8.1"
        self.assertFalse(foreign.exists())
        for i, root in enumerate((str(foreign), str(foreign) + "/")):
            with self.subTest(root=root):
                self.env["PLUGIN_ROOT"] = root
                session = "deleted_foreign_%d" % i
                self.hook({"hook_event_name": "SessionStart", "session_id": session})
                self.assertIn("Reply shape v9:", self.hook(dict(PROMPT, session_id=session)))
                marker = ".ihav-asd-ste100-sessions/" + session + ".version"
                self.assertEqual((self.home / ".claude" / marker).read_text().strip(), "9.9.9")
                self.assertFalse((self.home / ".codex" / marker).exists())

    def test_codex_keeps_its_host_when_active_root_differs_from_caller(self):
        base = self.home / ".codex/plugins/cache/ihav/ihav-asd-ste100"
        caller = self.release("9.9.8", word="v8", where=base)
        current = self.release("9.9.9", where=base)
        alias = self.home / "STE caller link"
        alias.symlink_to(caller, target_is_directory=True)
        for name, root in (("installed", caller), ("symlink", alias)):
            with self.subTest(caller=name):
                self.env.update(PLUGIN_ROOT=str(root), CLAUDE_PLUGIN_ROOT=str(root))
                session = "codex_" + name
                self.point(caller)
                self.hook({"hook_event_name": "SessionStart", "session_id": session})
                self.point(current)
                out = self.hook(dict(PROMPT, session_id=session))
                self.assertTrue(out.startswith("STE REPLY RULES UPDATED to 9.9.9 (was 9.9.8)"), out[:90])
                self.assertIn("Reply shape v9:", out)
                marker = ".ihav-asd-ste100-sessions/" + session + ".version"
                self.assertEqual((self.home / ".codex" / marker).read_text().strip(), "9.9.9")
                self.assertFalse((self.home / ".claude" / marker).exists())

    def test_an_unidentified_plugin_root_retains_legacy_codex_state(self):
        for i, relative in enumerate(("unidentified plugin", "cache/marketplace/ihav-agent-room/0.8.1")):
            with self.subTest(root=relative):
                self.env["PLUGIN_ROOT"] = str(self.home / relative)
                session = "unidentified_%d" % i
                self.hook({"hook_event_name": "SessionStart", "session_id": session})
                marker = ".ihav-asd-ste100-sessions/" + session + ".version"
                self.assertTrue((self.home / ".codex" / marker).exists())
                self.assertFalse((self.home / ".claude" / marker).exists())

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
        rollback = self.activate("--rollback")
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertNotIn("legacy plain-text", rollback.stderr)
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

    def test_activate_recreates_deleted_release_folders(self):
        current = self.release("9.9.9")
        result = self.activate("--root", str(current))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ensure-missing: ok, created", result.stderr)
        self.assertTrue((self.base / "0.14.0/hooks/ste-mode.mjs").exists())
        self.assertTrue((self.base / "0.18.0/.ihav-bridge-created").exists())
        self.assertIn("Reply shape v9:", self.hook({"hook_event_name": "UserPromptSubmit", "session_id": "old", "prompt": "hi"}))

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

    def test_activate_refuses_legacy_plaintext_prompt_and_preserves_pointer(self):
        good = self.release("9.9.8", word="v8")
        self.assertEqual(self.activate("--root", str(good)).returncode, 0)
        pointer = self.home / ".ihav/active/ihav-asd-ste100.json"
        before = pointer.read_bytes()
        legacy = self.release("9.9.9")
        core = legacy / "hooks/ste-core.mjs"
        core.write_text(core.read_text().replace("return promptContext(text);", "return text;"))
        result = self.activate("--root", str(legacy))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("prompt context must be valid UserPromptSubmit JSON", result.stderr)
        self.assertIn("unchanged", result.stderr)
        self.assertEqual(pointer.read_bytes(), before)

    def test_only_explicit_rollback_can_restore_the_legacy_prior_release(self):
        current = self.release("9.9.9")
        self.assertEqual(self.activate("--root", str(current)).returncode, 0)
        legacy = self.legacy_release("9.9.8")
        pointer = self.point(current, previous={"root": str(legacy), "version": "9.9.8"})
        before = pointer.read_bytes()
        forward = self.activate("--root", str(legacy))
        self.assertEqual(forward.returncode, 1)
        self.assertEqual(pointer.read_bytes(), before)
        rollback = self.activate("--rollback")
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertIn("rolled back to legacy plain-text", rollback.stderr)
        self.assertIn("Codex 0.160.0 reports invalid JSON", rollback.stderr)
        self.assertIn("omits this hook context", rollback.stderr)
        written = json.loads(pointer.read_bytes())
        self.assertEqual(json.loads(rollback.stdout), written)
        self.assertEqual(Path(written["root"]), legacy.resolve())
        self.assertEqual(written["version"], "9.9.8")
        self.assertEqual(Path(written["previous"]["root"]), current)

    def test_rollback_still_refuses_bad_output_and_preserves_pointer(self):
        current = self.release("9.9.9")
        self.assertEqual(self.activate("--root", str(current)).returncode, 0)
        legacy = "[ihav-asd-ste100] Reply shape: legacy STE reminder.\n"
        cases = (
            ("arbitrary Reply shape text", "", 0),
            ('{"hookSpecificOutput":', "", 0),
            (json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": legacy}}), "", 0),
            (json.dumps({"continue": False, "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit", "additionalContext": legacy}}), "", 0),
            (json.dumps(legacy), "", 0),
            (legacy + "unexpected second output\n", "", 0),
            (legacy, "hook failure", 0),
            (legacy, "", 1),
        )
        for i, (prompt, stderr, exit_code) in enumerate(cases):
            with self.subTest(prompt=prompt, stderr=stderr, exit_code=exit_code):
                bad = self.legacy_release("9.8.%d" % i, prompt, stderr, exit_code)
                pointer = self.point(current, previous={"root": str(bad), "version": bad.name})
                before = pointer.read_bytes()
                result = self.activate("--rollback")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stdout, "")
                self.assertIn("unchanged", result.stderr)
                self.assertNotIn("rolled back to legacy plain-text", result.stderr)
                self.assertEqual(pointer.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
