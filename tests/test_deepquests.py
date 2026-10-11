"""DeepQuests is a nonblocking intent probe; old replies remain valid in 0.22.0."""
import json
import re
import unittest
from pathlib import Path

from test_check_reply import FULL, ROOM
from check_reply import check

ROOT = Path(__file__).resolve().parents[1]
ITEM = ("   - **D1.** guess ~70%: you want vendor neutrality long term | ask: keep that direction?\n"
        "     - `<a>` Stay neutral | (b) choose one vendor | (c) later\n")


def with_deepquests(items=ITEM):
    return FULL + items


def room_leader(items=ITEM):
    return re.sub(r"`[0-9]+:[0-9]+ (?:AM|PM)` ", "", with_deepquests(items))


class DeepQuestTests(unittest.TestCase):
    def assert_failure(self, text, expected, profile="full"):
        report = check(text, profile)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any(expected in problem for problem in report["violations"]), report)

    def test_missing_section_only_warns_and_empty_section_passes_cleanly(self):
        old = check(FULL.replace("8. **DeepQuests:**\n", ""))
        self.assertTrue(old["ok"], old)
        self.assertEqual(old["warnings"], ["Section 8 DeepQuests is missing; show its label even when empty (warning only in 0.22.0)."])
        self.assertEqual(check(FULL)["warnings"], [])
        self.assertEqual(check(FULL)["stats"]["deepquests"], 0)

    def test_three_items_pass_four_fail(self):
        three = "".join(ITEM.replace("D1.", "D%d." % n) for n in range(1, 4))
        self.assertTrue(check(with_deepquests(three))["ok"])
        self.assertEqual(check(with_deepquests(three))["stats"]["deepquests"], 3)
        self.assert_failure(with_deepquests(three + ITEM.replace("D1.", "D4.")), "at most 3 D items")

    def test_each_d_item_has_a_bold_key(self):
        for bad in (ITEM.replace("**D1.**", "D1."), ITEM.replace("**D1.**", "**Guess:**")):
            with self.subTest(item=bad):
                self.assert_failure(with_deepquests(bad), "must start with **D1.**")

    def test_deep_items_and_choices_use_three_then_five_spaces(self):
        self.assert_failure(with_deepquests(ITEM.replace("   - **D1.", "     - **D1.")), "indented exactly 3")
        self.assert_failure(with_deepquests(ITEM.replace("     - `<a>`", "   - `<a>`")), "must start with **D1.**")
        self.assert_failure(with_deepquests(ITEM.replace("   - **D1.**", "     - D1.")), "bold **D1.** key")

    def test_numbering_restarts_at_one_and_has_no_gaps(self):
        self.assert_failure(with_deepquests(ITEM.replace("D1.", "D2.")), "from D1 in every reply")
        self.assert_failure(with_deepquests(ITEM + ITEM.replace("D1.", "D3.")), "D1, D3")
        self.assert_failure(with_deepquests(ITEM + ITEM), "from D1 in every reply")

    def test_one_recommended_choice_is_required(self):
        self.assert_failure(with_deepquests(ITEM.split("     -")[0]), "needs a choice line")
        self.assert_failure(with_deepquests(ITEM.replace("`<a>`", "(a)")), "0 options marked")
        self.assert_failure(with_deepquests(ITEM.replace("(b)", "`<a>`")), "2 options marked")

    def test_deepquest_uses_one_choice_line_not_separate_option_lines(self):
        split = ITEM.replace(" | (b) choose one vendor | (c) later", "\n     - (b) choose one vendor\n     - (c) later")
        for profile, text in (("full", with_deepquests(split)), ("room", room_leader(split))):
            self.assert_failure(text, "one deeper choice line", profile)

    def test_percent_has_no_brackets_and_is_in_range(self):
        for percent in ("[~70%]", "~101%", "70%"):
            with self.subTest(percent=percent):
                self.assert_failure(with_deepquests(ITEM.replace("~70%", percent)), "no brackets")

    def test_inline_code_keeps_its_square_brackets(self):
        coded = ITEM.replace("keep that direction?", "keep `config[0]` for this direction?")
        for profile, text in (("full", with_deepquests(coded)), ("room", room_leader(coded))):
            report = check(text, profile)
            self.assertTrue(report["ok"], report)

    def test_words_guess_and_ask_can_follow_the_user_language(self):
        for guess, ask in (("đoán", "hỏi"), ("猜测", "提问"), ("推測", "質問"), ("supongo", "pregunto")):
            with self.subTest(language=guess):
                report = check(with_deepquests(ITEM.replace("guess", guess).replace("ask:", ask + ":")))
                self.assertTrue(report["ok"], report)

    def test_section_eight_follows_ideas_once_with_exact_label(self):
        earlier = FULL.replace("7. **Ideas:**", "8. **DeepQuests:**\n7. **Ideas:**").removesuffix("8. **DeepQuests:**\n")
        self.assert_failure(earlier, "0 to 8, in order")
        self.assert_failure(FULL + "8. **DeepQuests:**\n", "each once")
        self.assert_failure(FULL.replace("DeepQuests", "DeepQuestions"), "label must be 'DeepQuests'")

    def test_d_ids_are_ascii(self):
        self.assert_failure(with_deepquests(ITEM.replace("D1.", "D１.")), "IDs must use ASCII digits")

    def test_adminzone_includes_eight_and_deep_items_do_not_count_as_quests(self):
        reply = with_deepquests()
        report = check(reply[reply.index("**Admin-Zone**"):])
        self.assertTrue(report["ok"], report)
        self.assertEqual((report["stats"]["questions"], report["stats"]["deepquests"]), (1, 1))
        no_quest = reply.replace("   - **Q1.** Approve: deploy to production?\n     - `<a>` After CI passes.\n     - (b) Now.\n", "")
        self.assertEqual(check(no_quest)["stats"]["questions"], 0)

    def test_long_term_and_empty_examples_pass(self):
        for name, count in (("deepquests-en.md", 1), ("deepquests-empty-en.md", 0)):
            with self.subTest(name=name):
                report = check((ROOT / "examples" / name).read_text())
                self.assertTrue(report["ok"], report)
                self.assertEqual(report["warnings"], [])
                self.assertEqual((report["stats"]["questions"], report["stats"]["deepquests"]), (0, count))

    def test_room_full_leader_allows_deepquests_without_counting_a_question(self):
        for text in (room_leader(), " ".join(room_leader().split())):
            with self.subTest(flat="\n" not in text):
                report = check(text, "room")
                self.assertTrue(report["ok"], report)
                self.assertEqual(report["stats"]["sections"], list(range(9)))
                self.assertEqual((report["stats"]["questions"], report["stats"]["deepquests"]), (1, 1))

    def test_room_full_leader_keeps_eight_optional(self):
        for suffix in ("8. **DeepQuests:**\n", ""):
            text = room_leader("").replace("8. **DeepQuests:**\n", suffix)
            report = check(text, "room")
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["stats"]["deepquests"], 0)
            self.assertFalse(any("DeepQuests is missing" in warning for warning in report["warnings"]))

    def test_room_compact_never_allows_deepquests(self):
        for suffix in ("8. **DeepQuests:**", "8. **DeepQuests:** " + ITEM):
            self.assert_failure(ROOM + " " + suffix, "optional only in that full form", "room")

    def test_room_unzoned_post_cannot_carry_a_deepquests_section(self):
        self.assert_failure("8. **DeepQuests:** " + ITEM, "only in the full leader form", "room")
        self.assertTrue(check("The new label is `8. **DeepQuests:**`.", "room")["ok"])

    def test_room_deepquests_must_come_last_and_be_complete(self):
        before_ideas = room_leader().replace("7. **Ideas:**", "8. **DeepQuests:**\n7. **Ideas:**").replace("8. **DeepQuests:**\n" + ITEM, ITEM)
        self.assert_failure(before_ideas, "optional only in that full form", "room")
        partial = room_leader().replace("2. **Doing:**\n   - **CI:** reruns the full suite.\n", "")
        self.assert_failure(partial, "optional only in that full form", "room")

    def test_room_d_items_have_bold_keys_choices_and_the_three_item_cap(self):
        self.assert_failure(room_leader(ITEM.replace("**D1.**", "D1.")), "must start with **D1.**", "room")
        self.assert_failure(room_leader(ITEM.split("     -")[0]), "needs a choice line", "room")
        four = "".join(ITEM.replace("D1.", "D%d." % n) for n in range(1, 5))
        self.assert_failure(room_leader(four), "at most 3 D items", "room")

    def test_deepquests_cannot_supply_a_compass_conflict_choice(self):
        text = (ROOT / "examples/deepquests-en.md").read_text().replace("0. **Goals:**", "X. **Compass:**\n   - **V1.** Keep vendor neutrality.\n   - **X!** V1: change direction; choose in Quests.\n0. **Goals:**")
        for profile in ("full", "room"):
            self.assert_failure(text, "needs its choice in section 5", profile)

    def test_canonical_rules_preserve_the_nonblocking_and_consent_boundaries(self):
        text = (ROOT / "skills/ihav-asd-ste100/SKILL.md").read_text()
        for rule in ("Show all nine", "decisions needed now in Quests", "At most 3 long-term guesses",
                     "Translate guess/ask to the user's language", "percent has no brackets", "`<a>` is your own guess",
                     "continue authorized work on `<a>`", "a guess is never approval or consent",
                     "Unanswered items stay open and return through the register", "Never put text on a section-label line",
                     "including section 8", "DeepQuests alone does not require it"):
            self.assertIn(rule, text)
        template = text.split("   ```", 2)[1]
        self.assertEqual(re.findall(r"(?m)^   ([0-8])\. \*\*[^*]+:\*\*$", template), [str(n) for n in range(9)])

    def test_manifest_version_and_public_section_descriptions_agree(self):
        for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads((ROOT / name).read_text())
            self.assertEqual(manifest["version"], "0.22.0")
            self.assertIn("nine fixed status sections", manifest["description"])

    def test_two_new_eval_shape_graders_match_the_examples_and_reject_the_wrong_home(self):
        for name, example in (("11-deepquests-long-term", "deepquests-en.md"), ("12-deepquests-empty", "deepquests-empty-en.md")):
            with self.subTest(case=name):
                case = ROOT / "evals" / name
                if not case.is_dir():
                    self.skipTest("local evals are ignored; the release examples remain tracked")
                grader = (case / "graders/shape.md").read_text().split("---")[1]
                pattern = re.search(r"(?m)^pattern: '(.+)'$", grader).group(1)
                reply = (ROOT / "examples" / example).read_text()
                self.assertIsNotNone(re.search(pattern, reply))
                bad = reply.replace("5. **Quests:**", "5. **Quests:**\n   - **Q1.** What do you want long term?")
                self.assertIsNone(re.search(pattern, bad))

    def test_all_language_examples_show_translated_deepquest_words(self):
        for language, guess, ask in (("en", "guess", "ask"), ("vi", "đoán", "hỏi"), ("es", "supongo", "pregunto"),
                                     ("ja", "推測", "質問"), ("zh", "猜测", "提问")):
            with self.subTest(language=language):
                text = (ROOT / ("examples/after-%s.md" % language)).read_text()
                self.assertIn("**D1.** %s ~70%%:" % guess, text)
                self.assertIn(" | %s:" % ask, text)
                self.assertTrue(check(text)["ok"], check(text))


if __name__ == "__main__":
    unittest.main()
