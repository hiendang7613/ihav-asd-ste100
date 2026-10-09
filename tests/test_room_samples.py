"""The room profile of check_reply.py against the samples that Agent Room shares.

examples/room-report-samples.json is a byte-equal copy of tests/fixtures/report-samples.json in ihav-agent-room-ui;
the two copies must have equal sha256 hashes. A sample with valid true must pass the room profile, one with valid false
must fail it. The room's own tests read the same file and check how the page and the server parse each text.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples/room-report-samples.json"
sys.path.insert(0, str(ROOT / "scripts"))
from check_reply import check  # noqa: E402


def run_cli(text, *flags):
    return subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check_reply.py"), "-", *flags], input=text,
                          capture_output=True, text=True, timeout=30)


class RoomSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = SAMPLES.read_bytes()
        cls.samples = json.loads(raw)
        print("\nroom-report-samples.json sha256 %s (the copy in ihav-agent-room-ui must be equal)" % hashlib.sha256(raw).hexdigest(),
              file=sys.stderr)

    def test_the_file_holds_named_samples_of_both_kinds(self):
        names = [sample["name"] for sample in self.samples]
        self.assertEqual(len(names), len(set(names)))
        for sample in self.samples:
            self.assertEqual({"name", "why", "text", "expect", "valid"} - set(sample), set(), sample["name"])
            self.assertNotIn("\n", sample["text"], "the room stores a post as one line")
        self.assertTrue(any(s["valid"] for s in self.samples) and any(not s["valid"] for s in self.samples))
        self.assertTrue(any(not s["expect"]["zoned"] and s["valid"] for s in self.samples), "posts without zones stay valid")

    def test_a_valid_sample_passes_the_room_profile_and_an_invalid_one_fails(self):
        for sample in self.samples:
            with self.subTest(sample=sample["name"]):
                report = check(sample["text"], "room")
                self.assertEqual(report["ok"], sample["valid"], report)

    def test_the_line_counts_agree_with_what_the_room_expects(self):
        for sample in (s for s in self.samples if s["expect"]["zoned"]):
            with self.subTest(sample=sample["name"]):
                stats = check(sample["text"], "room")["stats"]
                self.assertEqual((stats["agents_lines"], stats["result_lines"]), (sample["expect"]["steps"], len(sample["expect"]["bullets"])))

    def test_every_zoned_sample_opens_its_agents_zone_with_the_guess(self):
        for sample in (s for s in self.samples if s["expect"]["zoned"]):
            with self.subTest(sample=sample["name"]):
                self.assertRegex(sample["text"], r"^\*\*Agents-Zone\*\* - guess => \S")

    def test_the_command_line_flag_picks_the_profile(self):
        valid = next(s["text"] for s in self.samples if s["valid"] and s["expect"]["zoned"])
        invalid = next(s["text"] for s in self.samples if not s["valid"])
        self.assertEqual(run_cli(valid, "--profile", "room").returncode, 0)
        self.assertEqual(run_cli(valid).returncode, 1)  # the same one-line post is not a full-format reply
        failed = run_cli(invalid, "--profile", "room")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("violation: Result-Zone has 6 lines (at most 5).", failed.stdout)
        self.assertEqual(json.loads(run_cli(valid, "--profile", "room", "--json").stdout)["ok"], True)
        self.assertEqual(run_cli(valid, "--profile", "other").returncode, 2)


if __name__ == "__main__":
    unittest.main()
