"""The /az installer writes only its own skill and never touches a foreign one."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallAzTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste az ")
        self.config = Path(self.tmp.name) / ".claude"
        self.config.mkdir()
        self.env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "CLAUDE_CONFIG_DIR": str(self.config)}
        self.skill = self.config / "skills/az/SKILL.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args):
        return subprocess.run(["node", str(ROOT / "scripts/install-az.mjs"), *args], capture_output=True, text=True,
                              env=self.env, timeout=30)

    def test_install_update_and_remove_its_own_skill(self):
        self.assertEqual(self.run_script().returncode, 0)
        text = self.skill.read_text()
        self.assertIn("name: az", text)
        self.assertIn("owned-by: ihav-asd-ste100", text)
        self.assertIn("Admin-Zone alone", text)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.run_script("--remove").returncode, 0)
        self.assertFalse(self.skill.parent.exists())

    def test_a_foreign_az_skill_is_never_changed(self):
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("---\nname: az\n---\nsomeone else\n")
        for args in ((), ("--remove",)):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn("left unchanged", result.stderr)
                self.assertEqual(self.skill.read_text(), "---\nname: az\n---\nsomeone else\n")

    def test_remove_keeps_other_files_in_the_folder(self):
        self.assertEqual(self.run_script().returncode, 0)
        (self.skill.parent / "notes.txt").write_text("keep")
        self.assertEqual(self.run_script("--remove").returncode, 0)
        self.assertFalse(self.skill.exists())
        self.assertTrue((self.skill.parent / "notes.txt").exists())

    def test_wrong_usage(self):
        self.assertEqual(self.run_script("--bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
