"""Bridge old cache copies in a temporary HOME; never touch real installs."""
import json
import re
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts/bridge.mjs"
MARKER = "// ihav-asd-ste100 bridge forwarder v1"
OLD = b"// old copy\nprocess.stdout.write('OLD REMINDER');\n"
PROMPT = {"hook_event_name": "UserPromptSubmit", "session_id": "bridge-session", "prompt": "hi"}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste bridge ")
        self.home = Path(self.tmp.name)
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.home),
                    "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
                    "CODEX_HOME": str(self.home / ".codex"), "IHAV_HOME": str(self.home / ".ihav")}
        self.cache = self.home / ".claude/plugins/cache"
        self.old = self.old_release()
        self.active = self.cache / "ihav/ihav-asd-ste100/9.9.9"
        for part in ("hooks", "skills", ".claude-plugin"):
            shutil.copytree(ROOT / part, self.active / part)
        core = self.active / "hooks/ste-core.mjs"
        core.write_text(core.read_text().replace("Reply shape:", "Reply shape BRIDGE:"))

    def tearDown(self):
        self.tmp.cleanup()

    def old_release(self, market="old market", plugin="i-have-asd-ste100", version="0.17.0"):
        root = self.cache / market / plugin / version
        (root / "hooks").mkdir(parents=True)
        (root / "hooks/ste-mode.mjs").write_bytes(OLD)
        shutil.copy2(ROOT / "hooks/hooks.json", root / "hooks/hooks.json")
        return root

    def cli(self, *args, code=0):
        result = subprocess.run(["node", str(BRIDGE), *map(str, args)], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def point(self, **fields):
        pointer = self.home / ".ihav/active/ihav-asd-ste100.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"root": str(self.active), "launcher_protocol": 1} | fields))
        pointer.chmod(0o644)
        return pointer

    def hook(self, root=None):
        root = root or self.old
        command = json.loads((root / "hooks/hooks.json").read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        result = subprocess.run(["sh", "-c", command], input=json.dumps(PROMPT),
                                env=self.env | {"CLAUDE_PLUGIN_ROOT": str(root)}, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_apply_forwards_the_old_hooks_json_command_and_sets_bridge_flag(self):
        self.point()
        result = self.cli("--apply", self.old)
        self.assertEqual(result["results"][0]["status"], "applied")
        self.assertIn("Reply shape BRIDGE:", self.hook())
        # A core probe observes the bridge flag without relying on another writer's changes.
        (self.active / "hooks/ste-core.mjs").write_text("process.stdout.write(process.env.IHAV_STE100_BRIDGED || 'missing');")
        self.assertEqual(self.hook(), "1")

    def test_original_and_external_backup_keep_exact_bytes_and_apply_is_idempotent(self):
        original = self.old / "hooks/ste-mode.orig.mjs"
        self.cli("--apply", self.old)
        backup = self.home / ".ihav/backups/ihav-asd-ste100/old market/i-have-asd-ste100/0.17.0/ste-mode.mjs"
        self.assertEqual(original.read_bytes(), OLD)
        self.assertEqual(backup.read_bytes(), OLD)
        forwarder = (self.old / "hooks/ste-mode.mjs").read_bytes()
        self.assertTrue(forwarder.startswith(MARKER.encode()))
        self.assertEqual(self.cli("--apply", self.old)["results"][0]["status"], "skipped")
        self.assertEqual((self.old / "hooks/ste-mode.mjs").read_bytes(), forwarder)
        self.assertEqual(original.read_bytes(), OLD)
        self.cli("--restore", self.old)
        self.assertEqual((self.old / "hooks/ste-mode.mjs").read_bytes(), OLD)
        self.assertFalse(original.exists())
        self.assertEqual(backup.read_bytes(), OLD)
        self.assertEqual(self.cli("--restore", self.old)["results"][0]["status"], "skipped")

    def test_no_pointer_or_invalid_pointer_runs_original(self):
        self.cli("--apply", self.old)
        self.assertEqual(self.hook(), "OLD REMINDER")
        pointer = self.point(launcher_protocol=2)
        self.assertEqual(self.hook(), "OLD REMINDER")
        pointer.write_text("broken JSON")
        self.assertEqual(self.hook(), "OLD REMINDER")
        self.point().chmod(0o666)
        self.assertEqual(self.hook(), "OLD REMINDER")
        pointer = self.point()
        target = pointer.with_suffix(".real")
        pointer.rename(target)
        pointer.symlink_to(target)
        self.assertEqual(self.hook(), "OLD REMINDER")

    def test_escaping_root_or_core_and_import_failure_run_original(self):
        self.cli("--apply", self.old)
        outside = self.home / "outside"
        shutil.copytree(self.active, outside)
        self.point(root=str(outside))
        self.assertEqual(self.hook(), "OLD REMINDER")
        link = self.active.parent / "alias"
        link.symlink_to(outside)
        self.point(root=str(link))
        self.assertEqual(self.hook(), "OLD REMINDER")
        self.point()
        core = self.active / "hooks/ste-core.mjs"
        core.unlink()
        core.symlink_to(outside / "hooks/ste-core.mjs")
        self.assertEqual(self.hook(), "OLD REMINDER")
        core.unlink()
        core.write_text("throw new Error('broken core');")
        self.assertEqual(self.hook(), "OLD REMINDER")
        (self.old / "hooks/ste-mode.orig.mjs").write_text("throw new Error('broken original');")
        self.assertEqual(self.hook(), "")

    def test_modern_or_outside_release_is_refused_without_writes(self):
        before = (self.active / "hooks/ste-mode.mjs").read_bytes()
        self.cli("--apply", self.active, code=1)
        self.cli("--restore", self.active, code=1)
        self.assertEqual((self.active / "hooks/ste-mode.mjs").read_bytes(), before)
        self.assertFalse((self.active / "hooks/ste-mode.orig.mjs").exists())
        outside = self.home / "not cache/i-have-asd-ste100/0.17.0"
        shutil.copytree(self.old, outside)
        self.cli("--apply", outside, code=1)
        self.assertEqual((outside / "hooks/ste-mode.mjs").read_bytes(), OLD)

    def test_list_apply_all_restore_all_include_both_names_and_skip_modern(self):
        other = self.old_release("ihav", "ihav-asd-ste100", "0.16.0")
        listing = self.cli("--list")
        self.assertEqual(len(listing["results"]), 3)
        self.assertFalse((self.old / "hooks/ste-mode.orig.mjs").exists())
        applied = self.cli("--apply-all")
        self.assertEqual(sum(r["status"] == "applied" for r in applied["results"]), 2)
        self.cli("--restore-all")
        for root in (self.old, other):
            self.assertEqual((root / "hooks/ste-mode.mjs").read_bytes(), OLD)

    def test_conflicting_recovery_copies_or_hook_changes_are_preserved(self):
        original = self.old / "hooks/ste-mode.orig.mjs"
        original.write_text("different original")
        self.cli("--apply", self.old, code=1)
        self.assertEqual((self.old / "hooks/ste-mode.mjs").read_bytes(), OLD)
        original.unlink()
        self.cli("--apply", self.old)
        changed = b"// subsequent local change\n"
        (self.old / "hooks/ste-mode.mjs").write_bytes(changed)
        self.cli("--restore", self.old, code=1)
        self.assertEqual((self.old / "hooks/ste-mode.mjs").read_bytes(), changed)
        self.assertEqual(original.read_bytes(), OLD)

    def test_symlink_hook_or_backup_is_refused(self):
        hook = self.old / "hooks/ste-mode.mjs"
        outside = self.home / "original.mjs"
        outside.write_bytes(OLD)
        hook.unlink()
        hook.symlink_to(outside)
        self.cli("--apply", self.old, code=1)
        self.assertEqual(outside.read_bytes(), OLD)
        hook.unlink()
        hook.write_bytes(OLD)
        backups = self.home / ".ihav/backups"
        backups.parent.mkdir(parents=True)
        destination = self.home / "outside backups"
        destination.mkdir()
        backups.symlink_to(destination)
        self.cli("--apply", self.old, code=1)
        self.assertEqual(hook.read_bytes(), OLD)
        self.assertEqual(list(destination.iterdir()), [])

    def test_codex_configuration_selects_codex_cache(self):
        self.env["PLUGIN_ROOT"] = str(ROOT)
        self.cache = self.home / ".codex/plugins/cache"
        old = self.old_release()
        active = self.cache / "ihav/ihav-asd-ste100/9.9.9"
        shutil.copytree(self.active, active)
        self.point(root=str(active))
        self.cli("--apply", old)
        self.assertIn("Reply shape BRIDGE:", self.hook(old))

    def test_usage_is_json_with_exit_two(self):
        for args in ((), ("--bad",), ("--apply",), ("--list", "extra")):
            with self.subTest(args=args):
                self.assertFalse(self.cli(*args, code=2)["ok"])

    def test_ensure_missing_hook_forwards_or_is_silent_and_restore_removes_it(self):
        missing = self.cache / "ihav/ihav-asd-ste100/0.14.0"
        self.assertEqual(self.cli("--ensure", missing)["results"][0]["status"], "created")
        self.assertTrue((missing / ".ihav-bridge-created").is_file())
        self.assertFalse((missing / "hooks/ste-mode.orig.mjs").exists())
        def run():
            result = subprocess.run(["node", str(missing / "hooks/ste-mode.mjs")], env=self.env,
                                    input=json.dumps(PROMPT), text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        self.assertEqual(run(), "")
        self.point()
        self.assertIn("Reply shape BRIDGE:", run())
        self.assertEqual(self.cli("--ensure", missing)["results"][0]["status"], "skipped")
        self.assertEqual(self.cli("--restore", missing)["results"][0]["status"], "removed")
        self.assertFalse(missing.exists())

    def test_ensure_missing_creates_only_missing_versions_and_preserves_existing(self):
        existing = self.old_release("ihav", "ihav-asd-ste100", "0.15.0")
        result = self.cli("--ensure-missing")
        listed = {re.match(r"## ([0-9.]+)", line).group(1) for line in (ROOT / "CHANGELOG.md").read_text().splitlines()
                  if re.match(r"## 0\.(1[2-9]|[2-9][0-9])\.[0-9]+", line)}
        expected = len(listed | {"0.%d.0" % v for v in range(12, 18)}) - 1
        self.assertGreaterEqual(expected, 8)
        self.assertEqual(sum(r["status"] == "created" for r in result["results"]), expected)
        self.assertIn("0.18.0", [Path(r["root"]).name for r in result["results"]])
        self.assertEqual((existing / "hooks/ste-mode.mjs").read_bytes(), OLD)
        self.assertFalse((existing / ".ihav-bridge-created").exists())
        self.assertTrue(all(r["status"] == "skipped" for r in self.cli("--ensure-missing")["results"]))
        self.cli("--restore-all")
        self.assertTrue(existing.exists())
        self.assertTrue(self.active.exists())
        for version in (12, 13, 14, 16, 17):
            self.assertFalse((self.cache / f"ihav/ihav-asd-ste100/0.{version}.0").exists())

    def test_restore_created_folder_refuses_added_or_changed_files(self):
        missing = self.cache / "ihav/ihav-asd-ste100/0.14.0"
        self.cli("--ensure", missing)
        extra = missing / "keep.txt"
        extra.write_text("keep")
        self.cli("--restore", missing, code=1)
        self.assertEqual(extra.read_text(), "keep")
        extra.unlink()
        hook = missing / "hooks/ste-mode.mjs"
        hook.write_text("// changed")
        self.cli("--restore", missing, code=1)
        self.assertEqual(hook.read_text(), "// changed")


if __name__ == "__main__":
    unittest.main()
