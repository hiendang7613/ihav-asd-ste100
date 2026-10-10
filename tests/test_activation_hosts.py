"""One protocol-1 pointer, separate host caches, offline copies and recoverable activation."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
import test_launcher as fixture_module

ROOT, PROMPT = fixture_module.ROOT, fixture_module.PROMPT


class ActivationHostTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.LauncherTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.home, self.env = self.fixture.home, self.fixture.env
        self.claude = self.fixture.base
        self.codex = self.home / ".codex/plugins/cache/ihav/ihav-asd-ste100"
        self.pointer = self.home / ".ihav/active/ihav-asd-ste100.json"

    def release(self, version, host="claude", word=None):
        base = self.claude if host == "claude" else self.codex if host == "codex" else self.home / host
        root = self.fixture.release(version, word=word or version, where=base)
        shutil.copytree(ROOT / ".codex-plugin", root / ".codex-plugin")
        manifest = root / ".codex-plugin/plugin.json"
        manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {"version": version}))
        return root

    def point(self, root, **fields):
        return self.fixture.point(root, version=root.name, **fields)

    def hook(self, root, host="claude", payload=PROMPT):
        self.env["CLAUDE_PLUGIN_ROOT"] = str(root)
        self.env.pop("PLUGIN_ROOT", None)
        if host == "codex":
            self.env["PLUGIN_ROOT"] = str(root)
        return self.fixture.hook(payload)

    def activate(self, *args):
        self.env.pop("PLUGIN_ROOT", None)
        return self.fixture.activate(*args)

    def test_claude_root_resolves_same_version_in_codex_cache(self):
        a, b = self.release("9.1.0"), self.release("9.1.0", "codex")
        self.point(a)
        self.assertIn("Reply shape 9.1.0:", self.hook(b, "codex"))
        self.assertIn("Reply shape 9.1.0:", self.hook(a))

    def test_codex_root_resolves_same_version_in_claude_cache(self):
        caller = self.release("9.0.0")
        a, b = self.release("9.1.0"), self.release("9.1.0", "codex")
        self.point(b)
        self.assertIn("Reply shape 9.1.0:", self.hook(caller))
        self.assertIn("Reply shape 9.1.0:", self.hook(b, "codex"))

    def test_old_root_only_pointer_still_works_in_same_host(self):
        a = self.release("9.1.0")
        self.point(a)
        data = json.loads(self.pointer.read_text())
        del data["version"]
        self.pointer.write_text(json.dumps(data))
        self.assertIn("Reply shape 9.1.0:", self.hook(self.release("9.0.0")))

    def test_missing_other_host_version_falls_back_to_caller(self):
        a, caller = self.release("9.1.0"), self.release("9.0.0", "codex")
        self.point(a)
        self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))

    def test_foreign_root_without_safe_version_cannot_escape(self):
        a, caller = self.release("9.1.0"), self.release("9.0.0", "codex")
        self.release("9.1.0", "codex")
        for version in (None, "../9.1.0", "9.1.0/../../elsewhere", "/9.1.0"):
            with self.subTest(version=version):
                self.fixture.point(a, version=version)
                self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))

    def test_foreign_pointer_modes_protocol_owner_and_file_type_are_checked(self):
        a, caller = self.release("9.1.0"), self.release("9.0.0", "codex")
        self.release("9.1.0", "codex")
        for change in (lambda: self.pointer.chmod(0o666),
                       lambda: self.pointer.write_text(json.dumps({"root": str(a), "version": "9.1.0", "launcher_protocol": 2})),
                       lambda: self.pointer.write_text("not JSON")):
            self.point(a)
            change()
            self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))
        self.point(a)
        target = self.home / "pointer-target"
        self.pointer.rename(target)
        self.pointer.symlink_to(target)
        self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))
        self.pointer.unlink()
        target.rename(self.pointer)
        # Exercise ownership without changing filesystem ownership or needing privilege.
        script = ('import fs from "node:fs"; import {activeCore} from ' +
                  json.dumps((ROOT / "hooks/active.mjs").as_uri()) + ';'
                  'const old=fs.lstatSync; fs.lstatSync=(p)=>{const s=old(p);'
                  'Object.defineProperty(s,"uid",{value:process.getuid()+1});return s};'
                  'process.stdout.write(JSON.stringify(activeCore()));')
        out = subprocess.run(["node", "--input-type=module", "-e", script], env=self.env,
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, "null")

    def test_foreign_version_must_have_matching_manifest_and_contained_core(self):
        a, caller = self.release("9.1.0"), self.release("9.0.0", "codex")
        b = self.release("9.1.0", "codex")
        self.point(a)
        manifest = b / ".claude-plugin/plugin.json"
        saved = manifest.read_text()
        manifest.write_text(json.dumps({"name": "other", "version": "9.1.0"}))
        self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))
        manifest.write_text(saved)
        core = b / "hooks/ste-core.mjs"
        core.unlink()
        core.symlink_to(a / "hooks/ste-core.mjs")
        self.assertIn("Reply shape 9.0.0:", self.hook(caller, "codex"))

    def test_batch_copies_both_hosts_and_reports_missing_install(self):
        self.release("9.0.0")
        self.release("9.0.0", "codex")
        source = self.release("9.1.0", "checkout")
        (source / ".evidence").mkdir()
        result = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([h["status"] for h in data["hosts"]], ["activated", "activated"])
        for host, base in (("claude", self.claude), ("codex", self.codex)):
            self.assertFalse((base / "9.1.0").is_symlink())
            self.assertFalse((base / "9.1.0/.evidence").exists())
            self.assertIn("Reply shape 9.1.0:", self.hook(base / "9.0.0", host))
        # Use a separate fixture without a Codex install.
        other = fixture_module.LauncherTests()
        other.setUp()
        try:
            other.release("9.0.0")
            out = other.activate("--all-hosts", "--root", str(source))
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["hosts"][1]["status"], "not installed")
            self.assertFalse((other.home / ".codex/plugins/cache").exists())
        finally:
            other.tearDown()

    def test_batch_smokes_codex_context_before_touching_either_cache_or_pointer(self):
        a, b = self.release("9.0.0"), self.release("9.0.0", "codex")
        self.point(a)
        before = self.pointer.read_bytes()
        source = self.release("9.1.0", "checkout")
        core = source / "hooks/ste-core.mjs"
        core.write_text('if (process.env.PLUGIN_ROOT) process.exit(1);\n' + core.read_text())
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        self.assertEqual(json.loads(out.stdout)["hosts"][1]["status"], "failed the smoke run")
        self.assertEqual(self.pointer.read_bytes(), before)
        self.assertFalse((a.parent / "9.1.0").exists())
        self.assertFalse((b.parent / "9.1.0").exists())

    def test_batch_preserves_existing_release_and_rejects_symlink_source(self):
        self.release("9.0.0")
        self.release("9.0.0", "codex")
        existing = self.release("9.1.0", word="original")
        source = self.release("9.1.0", "checkout")
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 0, out.stderr)
        backup = Path(json.loads(out.stdout)["hosts"][0]["backup"])
        self.assertIn("Reply shape original:", (backup / "hooks/ste-core.mjs").read_text())
        self.assertEqual(existing.name, "9.1.0")
        before = self.pointer.read_bytes()
        (source / "skills/foreign-link").symlink_to(ROOT / "skills/ihav-asd-ste100/SKILL.md")
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        self.assertIn("symlink", out.stderr)
        self.assertEqual(self.pointer.read_bytes(), before)

    def test_batch_rejects_target_symlink_and_no_hosts_without_creating_caches(self):
        source = self.release("9.1.0", "checkout")
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        self.assertTrue(all(h["status"] == "not installed" for h in json.loads(out.stdout)["hosts"]))
        self.release("9.0.0")
        (self.claude / "9.1.0").symlink_to(source)
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        self.assertIn("symlink", out.stderr)

    def test_batch_rolls_back_both_hosts_and_preserves_previous_on_repeat(self):
        a, b = self.release("9.0.0"), self.release("9.0.0", "codex")
        self.point(a)
        source = self.release("9.1.0", "checkout")
        for _ in range(2):
            out = self.activate("--all-hosts", "--root", str(source))
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["pointer"]["previous"]["version"], "9.0.0")
        out = self.activate("--all-hosts", "--rollback")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["pointer"]["version"], "9.0.0")
        for host, base in (("claude", self.claude), ("codex", self.codex)):
            self.assertIn("Reply shape 9.0.0:", self.hook(base / "9.1.0", host))

    def test_single_host_rollback_resolves_previous_version_in_own_cache(self):
        old_a, old_b = self.release("9.0.0"), self.release("9.0.0", "codex")
        new_b = self.release("9.1.0", "codex")
        self.point(new_b, previous={"root": str(old_a), "version": "9.0.0"})
        self.env["PLUGIN_ROOT"] = str(new_b)
        out = self.fixture.activate("--rollback")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(Path(json.loads(out.stdout)["root"]), old_b.resolve())

    def test_same_version_activation_in_other_host_keeps_rollback_target(self):
        old_a = self.release("9.0.0")
        new_a, new_b = self.release("9.1.0"), self.release("9.1.0", "codex")
        self.point(new_a, previous={"root": str(old_a), "version": "9.0.0"})
        self.env["PLUGIN_ROOT"] = str(new_b)
        out = self.fixture.activate("--root", str(new_b))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["previous"]["version"], "9.0.0")

    def test_prepared_catalogue_is_local_ihav_copy_and_preserves_source(self):
        target = self.home / "local marketplace with spaces"
        before = (ROOT / ".claude-plugin/marketplace.json").read_bytes()
        out = self.activate("--prepare-marketplace", str(target))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads((target / ".claude-plugin/marketplace.json").read_text())["name"], "ihav")
        self.assertEqual((ROOT / ".claude-plugin/marketplace.json").read_bytes(), before)
        self.assertFalse((target / ".evidence").exists())
        self.assertEqual(self.activate("--prepare-marketplace", str(target)).returncode, 1)

    def test_batch_pointer_write_failure_restores_both_releases(self):
        a = self.release("9.1.0", word="claude-original")
        b = self.release("9.1.0", "codex", word="codex-original")
        source = self.release("9.1.0", "checkout")
        # An obstructed pointer parent fails after both caches are staged and replaced.
        (self.home / ".ihav/active").write_text("obstruction")
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        for root, word in ((a, "claude-original"), (b, "codex-original")):
            self.assertIn("Reply shape %s:" % word, (root / "hooks/ste-core.mjs").read_text())
        self.assertEqual((self.home / ".ihav/active").read_text(), "obstruction")

    def test_dangling_cache_and_catalogue_links_are_preserved(self):
        old = self.release("9.0.0")
        self.point(old)
        source = self.release("9.1.0", "checkout")
        target = self.claude / "9.1.0"
        missing = self.home / "missing foreign directory"
        target.symlink_to(missing)
        before = self.pointer.read_bytes()
        out = self.activate("--all-hosts", "--root", str(source))
        self.assertEqual(out.returncode, 1)
        self.assertEqual(target.readlink(), missing)
        self.assertEqual(self.pointer.read_bytes(), before)
        catalogue = self.home / "existing dangling catalogue"
        catalogue.symlink_to(missing)
        out = self.activate("--prepare-marketplace", str(catalogue))
        self.assertEqual(out.returncode, 1)
        self.assertEqual(catalogue.readlink(), missing)
