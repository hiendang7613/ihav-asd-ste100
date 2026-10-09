"""The /x installer writes only its own skill, never touches a foreign one, and shares no folder with /az."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallXTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste x ")
        self.config = Path(self.tmp.name) / ".claude"
        self.config.mkdir()
        self.env = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "CLAUDE_CONFIG_DIR": str(self.config)}
        self.skill = self.config / "skills/x/SKILL.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, script="install-x.mjs"):
        return subprocess.run(["node", str(ROOT / "scripts" / script), *args], capture_output=True, text=True,
                              env=self.env, timeout=30)

    def test_install_update_and_remove_its_own_skill(self):
        self.assertEqual(self.run_script().returncode, 0)
        text = self.skill.read_text()
        self.assertIn("name: x", text)
        self.assertIn("owned-by: ihav-asd-ste100 install-x", text)
        self.assertIn("Compass alone", text)
        self.assertIn("(proposed, not enforced)", text)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.run_script("--remove").returncode, 0)
        self.assertFalse(self.skill.parent.exists())

    def test_a_foreign_x_skill_is_never_changed(self):
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("---\nname: x\n---\nsomeone else\n")
        for args in ((), ("--remove",)):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn("left unchanged", result.stderr)
                self.assertEqual(self.skill.read_text(), "---\nname: x\n---\nsomeone else\n")

    def test_x_and_az_are_independent_and_wrong_usage_fails(self):
        self.assertEqual(self.run_script(script="install-az.mjs").returncode, 0)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.run_script("--remove").returncode, 0)
        self.assertTrue((self.config / "skills/az/SKILL.md").is_file())
        self.assertFalse(self.skill.exists())
        result = self.run_script("--bogus")
        self.assertEqual((result.returncode, result.stderr), (2, "usage: install-x.mjs [--remove]\n"))


if __name__ == "__main__":
    unittest.main()
