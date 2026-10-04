"""Manifests agree, the skill is the single source of truth, and no specification text is shipped."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ihav-asd-ste100/SKILL.md"


def shipped_files():
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and parts[0] not in {"ref_repos", ".git"} and "results" not in parts and "__pycache__" not in parts:
            yield path


class ManifestTests(unittest.TestCase):
    def test_manifests_share_name_version_and_licence(self):
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(claude["name"], "ihav-asd-ste100")
        self.assertEqual((codex["name"], codex["version"], codex["license"]), (claude["name"], claude["version"], claude["license"]))
        self.assertEqual(market["plugins"][0]["name"], claude["name"])
        self.assertTrue((ROOT / codex["skills"] / "ihav-asd-ste100/SKILL.md").is_file())
        self.assertRegex(claude["version"], r"^\d+\.\d+\.\d+$")

    def test_licence_and_third_party_notice_exist(self):
        self.assertIn("Copyright (c) 2026 hiendang7613", (ROOT / "LICENSE").read_text())
        self.assertIn("Ayoub Ghriss", (ROOT / "licenses/i-have-adhd-LICENSE.txt").read_text())
        notice = (ROOT / "licenses/NOTICE.md").read_text()
        self.assertIn("no specification text and no dictionary", notice)
        self.assertIn("not affiliated", notice)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text()
        self.front = self.text.split("---")[1]

    def test_frontmatter_matches_the_directory_and_stays_manual(self):
        self.assertIn("name: ihav-asd-ste100", self.front)
        self.assertIn("disable-model-invocation: true", self.front)

    def test_skill_stays_small_because_always_on_injects_it_every_session(self):
        # 7,100 bytes (6,900 until 0.15.0, 6,500 until 0.11.0): the Goals section with L, G and B lines costs about
        # 50 more tokens per session start than the old eight sections.
        self.assertLessEqual(len(self.text.encode()), 7100)

    def test_required_sections_and_the_numbered_conclusion_part(self):
        for heading in ("## Persistence", "## The shape", "## Format for fast reading", "## Sentences", "## Protect meaning",
                        "## Tone", "## When to break the rules", "## Pre-send check"):
            self.assertIn(heading, self.text)
        positions = [self.text.index(label) for label in ("`**Conclusion:**`", "0. **Goals:**", "1. **Done:**",
                                                          "2. **Doing:**", "3. **Todos:**", "4. **Pending:**",
                                                          "5. **Quests:**", "6. **Risks:**", "7. **Ideas:**")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("`<a>`", self.text)
        self.assertIn("Keep labels exactly as shown in English", self.text)
        self.assertIn("an empty section shows only its label", self.text)
        self.assertIn("Never put text on a section-label line", self.text)
        self.assertIn("starting with a bold key", self.text)
        self.assertIn("An empty Risks label means you checked and found none", self.text)
        self.assertIn("Each risk and idea ends with one choice line", self.text)
        self.assertIn("Start approvals with `Approve:`", self.text)
        self.assertIn("name action and target, and state what cannot be undone", self.text)
        self.assertIn("Never omit a failure, material finding or requested detail", self.text)
        self.assertIn("Count passes; list each failure", self.text)
        for rule in ("Open with the answer or blocker", "Give each item one home",
                     "deferred work as B lines", "Number Q, R and I from 1 in every reply, so Q1.a means the latest reply", "Only the user sets L lines, with no percent",
                     "`round(10 * done / total)` filled, or \"no plan yet\"", "add no new fact or evidence list",
                     "Body, status and question text follow the user's latest language",
                     "A user or project format request changes this shape only when higher rules allow it"):
            self.assertIn(rule, self.text)
        self.assertIn("do not count syllable spaces as words", self.text)
        for zone in ("`**Agents-Zone**`", "`**Result-Zone**`", "`**Admin-Zone**`"):
            self.assertIn(zone, self.text)
        self.assertIn("`` - `4:43 PM` why => what ``", self.text)
        self.assertIn("Take the time only from a clock note or command output", self.text)
        self.assertLess(self.text.index("`**Agents-Zone**`"), self.text.index("`**Result-Zone**`"))
        self.assertLess(self.text.index("`**Admin-Zone**`"), self.text.index("`**Conclusion:**`"))
        self.assertIn("These are targets, not limits", self.text)
        self.assertIn("Do not create a file only to shorten a reply", self.text)
        self.assertIn("For the full format", self.text)
        self.assertIn('"stop ste mode"', self.text)

    def test_fixed_english_labels_do_not_set_the_body_language(self):
        """Labels stay English while the rest of the reply follows the user."""
        body = self.text.split("---", 2)[2]
        self.assertIn("Keep labels exactly as shown in English", body)
        self.assertIn("Body, status and question text follow the user's latest language", body)
        self.assertNotRegex(body, r"(?i)write every reply in English")
        self.assertTrue(body.isascii(), sorted({c for c in body if not c.isascii()}))

    def test_public_skill_does_not_hard_code_one_users_form_of_address(self):
        self.assertNotRegex(self.text, r"\bAnh cần làm\b|\banh\b")

    def test_no_specification_text_or_dictionary_is_shipped(self):
        rule_ids = re.compile(r"\b(?:Rule|RULE)\s+\d+\.\d+\b")
        for path in shipped_files():
            if path.suffix not in {".md", ".json", ".mjs", ".py", ".txt"} or path.name.startswith("test_"):
                continue
            text = path.read_text(errors="ignore")
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(rule_ids.search(text))
                self.assertNotIn("approved word", text.lower())
        self.assertIn("claim no compliance", self.text)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless((ROOT / "evals").is_dir(), "the eval suite is kept locally, not in the repository")
class EvalSuiteTests(unittest.TestCase):
    """The eval suite is only written, never run here (running it calls paid models); it must at least load."""

    def front(self, path):
        return path.read_text().split("---")[1]

    def test_every_case_has_a_prompt_and_graders(self):
        cases = [p for p in (ROOT / "evals").iterdir() if p.is_dir() and p.name != "results"]
        self.assertGreaterEqual(len(cases), 10)
        for case in cases:
            with self.subTest(case=case.name):
                front = self.front(case / "prompt.md")
                self.assertNotIn("EVAL_IHAV_ASD_STE100", front)  # on by default since 0.1.1
                self.assertIn("allowed_tools: []", front)
                self.assertTrue(list((case / "graders").glob("*.md")))

    def test_regex_graders_compile_and_yaml_loads_when_available(self):
        try:
            import yaml
        except ImportError:
            yaml = None
        for grader in (ROOT / "evals").rglob("graders/*.md"):
            front = self.front(grader)
            with self.subTest(grader=str(grader.relative_to(ROOT))):
                data = yaml.safe_load(front) if yaml else dict(
                    line.split(": ", 1) for line in front.strip().splitlines())
                self.assertIn(str(data["type"]).strip("'\""), {"regex", "llm"})
                if str(data["type"]).strip("'\"") == "regex":
                    re.compile(str(data["pattern"]).strip("'"))
