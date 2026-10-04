import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_reply import check  # noqa: E402

FULL = """**Agents-Zone**
- `4:12 PM` the login test fails => read `src/auth.ts`
- `4:18 PM` check the fix => ran `npm test`

**Result-Zone**
- **Fix:** `verifyToken` now reads the `Authorization` header.
- **Tests:** 214 ran and 213 pass.

**Admin-Zone**

**Conclusion:** Login is fixed; one payment test still fails, cause not checked.

0. **Goals:**
   - **L1.** Users can log in from every client.
   - **G1.** Fix the login test -> L1 `########--` 4/5
   - **B1.** Update the login guide later.
1. **Done:**
   - **Login fix:** merged.
2. **Doing:**
   - **CI:** reruns the full suite.
3. **Todos:**
   - **Payment test:** check `payment.spec.ts:88`.
4. **Pending:**
   - **Review:** waiting for the other agent.
5. **Quests:**
   - **Q1.** Approve: deploy to production?
     - `<a>` After CI passes.
     - (b) Now.
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 is older than the 9.0.0 security release.
     - `<a>` update it in a separate change | (b) skip | (c) later
7. **Ideas:**
   - **I1.** Add a test for the `Authorization` header.
     - `<a>` plan it | (b) skip | (c) later
"""


class ShapeTests(unittest.TestCase):
    def test_full_shape_passes(self):
        report = check(FULL)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["stats"]["sections"], list(range(8)))

    def test_shipped_examples_pass_and_the_old_style_fails(self):
        for name in ("after-en.md", "after-vi.md", "after-zh.md", "after-ja.md", "after-es.md", "compare/3-ihav-asd-ste100.md"):
            with self.subTest(name=name):
                self.assertTrue(check((ROOT / "examples" / name).read_text())["ok"])
        before = check((ROOT / "examples/before.md").read_text())
        self.assertFalse(before["ok"])
        self.assertTrue(any("No conclusion part" in v for v in before["violations"]))

    def test_all_eight_sections_are_always_shown_and_empty_ones_show_only_the_label(self):
        alone = ("**Agents-Zone**\n\n**Result-Zone**\n- **Rename:** done.\n\n**Admin-Zone**\n\n"
                 "**Conclusion:** The file is renamed.\n")
        self.assertTrue(any("must be shown" in v for v in check(alone)["violations"]))
        labels = ["Goals", "Done", "Doing", "Todos", "Pending", "Quests", "Risks", "Ideas"]
        minimal = alone + "\n" + "\n".join("%d. **%s:**" % (n, label) for n, label in enumerate(labels)) + "\n"
        self.assertTrue(check(minimal)["ok"], check(minimal))
        no_pending = FULL.replace("2. **Doing:**\n   - **CI:** reruns the full suite.\n", "")
        self.assertNotEqual(no_pending, FULL)
        self.assertTrue(any("2 must be shown" in v for v in check(no_pending)["violations"]))
        empty = FULL.replace("2. **Doing:**\n   - **CI:** reruns the full suite.", "2. **Doing:**")
        self.assertNotEqual(empty, FULL)
        self.assertTrue(check(empty)["ok"], check(empty))
        filler = empty.replace("2. **Doing:**", "2. **Doing:** None")
        self.assertTrue(any("show its label only" in v for v in check(filler)["violations"]))

    def test_items_are_sub_items_that_start_with_a_bold_key(self):
        inline = FULL.replace("1. **Done:**\n   - **Login fix:** merged.", "1. **Done:** Login fix merged.")
        self.assertNotEqual(inline, FULL)
        self.assertTrue(any("Section 1 must show its label only" in v for v in check(inline)["violations"]))
        plain = FULL.replace("   - **Payment test:** check", "   - Check")
        self.assertNotEqual(plain, FULL)
        self.assertTrue(any("Section 3 item must start with **Key:**" in v for v in check(plain)["violations"]))
        unnumbered = FULL.replace("   - **Q1.** Approve:", "   - Approve:")
        self.assertNotEqual(unnumbered, FULL)
        self.assertTrue(any("Section 5 item must start with **Q1.**" in v for v in check(unnumbered)["violations"]))
        detail = FULL.replace("   - **CI:** reruns the full suite.", "   - **CI:** reruns the full suite.\n     - job 812, about 9 minutes left")
        self.assertNotEqual(detail, FULL)
        self.assertTrue(check(detail)["ok"], check(detail))

    def test_small_answers_need_nothing(self):
        self.assertTrue(check("102.")["ok"])
        self.assertTrue(check('```json\n{"status": "ok", "count": 3}\n```')["ok"])

    def test_sections_out_of_order_repeated_or_out_of_range_fail(self):
        swapped = FULL.replace("3. **Todos:**", "9. **Todos:**").replace("2. **Doing:**", "3. **Doing:**").replace("9. **Todos:**", "2. **Todos:**")
        self.assertNotEqual(swapped, FULL)
        self.assertFalse(check(swapped)["ok"])
        self.assertFalse(check(FULL.replace("7. **Ideas:**", "8. **Ideas:**"))["ok"])
        self.assertFalse(check(FULL.replace("2. **Doing:**", "1. **Doing:**"))["ok"])

    def test_one_blank_line_after_the_conclusion_and_none_between_sections(self):
        glued = FULL.replace("cause not checked.\n\n0.", "cause not checked.\n0.")
        self.assertNotEqual(glued, FULL)
        self.assertTrue(any("blank line between the Conclusion line" in v for v in check(glued)["violations"]))
        loose = FULL.replace("\n4. **Pending:**", "\n\n4. **Pending:**")
        self.assertNotEqual(loose, FULL)
        self.assertTrue(any("without blank lines" in v for v in check(loose)["violations"]))

    def test_each_question_with_options_marks_exactly_one_recommended(self):
        none = FULL.replace("`<a>` After CI passes.", "(a) After CI passes.")
        two = FULL.replace("(b) Now.", "`<a>` Now.")
        for text in (none, two):
            with self.subTest(text=text[-260:-200]):
                self.assertNotEqual(text, FULL)
                self.assertTrue(any("options marked" in v for v in check(text)["violations"]))

    def test_conclusion_first_on_request_still_parses(self):
        body, rest = FULL.split("\n\n**Conclusion:**", 1)
        line, sections = rest.split("\n\n", 1)
        first = "**Conclusion:**" + line + "\n\n" + body + "\n\n" + sections
        report = check(first)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["stats"]["sections"], list(range(8)))
        self.assertEqual(report["stats"]["body_words"], check(FULL)["stats"]["body_words"])
        glued = first.replace("**Admin-Zone**\n\n0.", "**Admin-Zone**\n0.")
        self.assertNotEqual(glued, first)
        self.assertTrue(any("blank line" in v for v in check(glued)["violations"]))
        self.assertTrue(any("No valid Conclusion" in v for v in check(body + "\n\n" + sections)["violations"]))

    def test_three_zone_labels_in_order_with_timed_step_lines(self):
        self.assertTrue(check(FULL)["ok"], check(FULL))
        for zone in ("**Agents-Zone**", "**Result-Zone**", "**Admin-Zone**"):
            with self.subTest(missing=zone):
                self.assertTrue(any("three zone labels" in v for v in check(FULL.replace(zone + "\n", ""))["violations"]))
        swapped = FULL.replace("**Agents-Zone**", "**X**").replace("**Result-Zone**", "**Agents-Zone**").replace("**X**", "**Result-Zone**")
        self.assertTrue(any("three zone labels" in v for v in check(swapped)["violations"]))
        no_time = FULL.replace("- `4:12 PM` the login", "- the login")
        self.assertTrue(check(no_time)["ok"], check(no_time))
        for bad in ("- `16:12` the login test fails => read", "- `4:12 PM` the login test fails, read",
                    "- [4:12 PM] the login test fails => read", "* `4:12 PM` the login test fails => read"):
            with self.subTest(bad=bad):
                wrong = FULL.replace("- `4:12 PM` the login test fails => read", bad)
                self.assertNotEqual(wrong, FULL)
                self.assertFalse(check(wrong)["ok"])
        glued = FULL.replace("`npm test`\n\n**Result-Zone**", "`npm test`\n**Result-Zone**")
        self.assertNotEqual(glued, FULL)
        self.assertTrue(any("blank line before **Result-Zone**" in v for v in check(glued)["violations"]))
        joined = FULL.replace("**Admin-Zone**\n\n**Conclusion:**", "**Admin-Zone**\n**Conclusion:**")
        self.assertNotEqual(joined, FULL)
        self.assertTrue(any("blank line after **Admin-Zone**" in v for v in check(joined)["violations"]))
        prose = FULL.replace("**Result-Zone**\n- **Fix:**", "**Result-Zone**\nThe fix: ")
        self.assertNotEqual(prose, FULL)
        self.assertTrue(any("start a list or leave a blank line" in v for v in check(prose)["violations"]))
        late = FULL.replace("\n\n**Admin-Zone**\n\n**Conclusion:**", "\n\n**Conclusion:**").replace("\n0. **Goals:**", "\n**Admin-Zone**\n\n0. **Goals:**", 1)
        self.assertFalse(check(late)["ok"])
        extra = FULL.replace("**Admin-Zone**\n\n**Conclusion:**", "**Admin-Zone**\n\n- **Note:** one more fact.\n\n**Conclusion:**")
        self.assertNotEqual(extra, FULL)
        self.assertTrue(any("must be followed by the Conclusion line" in v for v in check(extra)["violations"]))
        fenced = "```\n**Agents-Zone**\n```\n\n" + FULL
        self.assertTrue(check(fenced)["ok"], check(fenced))

    def test_long_body_warning_does_not_ask_for_a_file(self):
        long_body = FULL.replace("- **Tests:** 214 ran and 213 pass.", "- **Tests:** " + "word " * 260 + "end.")
        warnings = check(long_body)["warnings"]
        self.assertTrue(any(w.startswith("Body has") for w in warnings), warnings)
        self.assertFalse(any("file" in w for w in warnings), warnings)

    def test_risks_and_ideas_are_numbered_and_offer_one_line_choices(self):
        for letter, section in (("R", 6), ("I", 7)):
            with self.subTest(letter=letter):
                wrong = FULL.replace("   - **%s1.**" % letter, "   - **Item:**")
                self.assertNotEqual(wrong, FULL)
                self.assertTrue(any("Section %d item must start with **%s1.**" % (section, letter) in v
                                    for v in check(wrong)["violations"]))
        for line in ("     - `<a>` plan it | (b) skip | (c) later\n", "     - `<a>` update it in a separate change | (b) skip | (c) later\n"):
            with self.subTest(removed=line[9:20]):
                no_choice = FULL.replace(line, "")
                self.assertNotEqual(no_choice, FULL)
                self.assertTrue(any("needs a choice line" in v for v in check(no_choice)["violations"]))
        single = FULL.replace("`<a>` plan it | (b) skip | (c) later", "`<a>` plan it")
        self.assertNotEqual(single, FULL)
        self.assertTrue(any("needs a choice line" in v for v in check(single)["violations"]))
        unmarked = FULL.replace("`<a>` plan it | (b) skip", "(a) plan it | (b) skip")
        self.assertNotEqual(unmarked, FULL)
        self.assertTrue(any("0 options marked" in v for v in check(unmarked)["violations"]))
        twice = FULL.replace("| (b) skip | (c) later\n7.", "| `<a>` skip | (c) later\n7.")
        self.assertNotEqual(twice, FULL)
        self.assertTrue(any("2 options marked" in v for v in check(twice)["violations"]))
        nested = FULL.replace("     - `<a>` plan it | (b) skip | (c) later", "     - `<a>` plan it\n     - (b) skip")
        self.assertNotEqual(nested, FULL)
        self.assertTrue(check(nested)["ok"], check(nested))
        one_line_question = FULL.replace("     - `<a>` After CI passes.\n     - (b) Now.", "     - `<a>` after CI passes | (b) now")
        self.assertNotEqual(one_line_question, FULL)
        self.assertTrue(check(one_line_question)["ok"], check(one_line_question))
        open_question = FULL.replace("     - `<a>` After CI passes.\n     - (b) Now.\n", "")
        self.assertNotEqual(open_question, FULL)
        self.assertTrue(check(open_question)["ok"], check(open_question))

    def test_an_item_listed_in_two_sections_is_warned(self):
        twice = FULL.replace("4. **Pending:**\n   - **Review:** waiting for the other agent.",
                             "4. **Pending:**\n   - **Payment test:** waiting for the other agent.")
        self.assertNotEqual(twice, FULL)
        report = check(twice)
        self.assertTrue(report["ok"], report)
        self.assertTrue(any("'payment test' appears in sections 3 and 4" in w for w in report["warnings"]), report["warnings"])
        self.assertFalse(any("appears in sections" in w for w in check(FULL)["warnings"]))
        nested = FULL.replace("   - **CI:** reruns the full suite.", "   - **CI:** reruns the full suite.\n     - **Payment test:** included in this run.")
        self.assertNotEqual(nested, FULL)
        self.assertFalse(any("appears in sections" in w for w in check(nested)["warnings"]), check(nested)["warnings"])

    def test_conclusion_line_length(self):
        long_line = FULL.replace("Login is fixed; one payment test still fails, cause not checked.", " ".join(["word"] * 26) + ".")
        self.assertTrue(any("Conclusion line has 26" in v for v in check(long_line)["violations"]))

    def test_structural_markers_use_ascii_digits_and_colons(self):
        variants = (
            FULL.replace("**Conclusion:**", "**Conclusion：**"),
            FULL.replace("1. **Done:**", "١. **Done:**"),
            FULL.replace("**Payment test:**", "**Payment test：**"),
            FULL.replace("**Q1.**", "**Q١.**"),
        )
        for text in variants:
            with self.subTest(fragment=text.splitlines()[0]):
                report = check(text)
                self.assertFalse(report["ok"], report)
                self.assertTrue(any("ASCII" in violation for violation in report["violations"]), report)

        prose_punctuation = FULL.replace("Login is fixed;", "Login： is fixed;")
        self.assertTrue(check(prose_punctuation)["ok"], check(prose_punctuation))

    def test_duplicate_conclusion_is_rejected(self):
        pasted = FULL.replace(
            "**Conclusion:** Login is fixed;",
            "**Conclusion:** A pasted peer report says all tests pass.\n\n**Conclusion:** Login is fixed;",
        )
        report = check(pasted)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("more than one Conclusion" in violation for violation in report["violations"]), report)

    def test_attempted_section_format_cannot_use_the_small_answer_exception(self):
        labels = ["Goals", "Done", "Doing", "Todos", "Pending", "Quests", "Risks", "Ideas"]
        no_conclusion = "Renamed.\n\n" + "\n".join(
            "%d. **%s:**" % (number, label) for number, label in enumerate(labels)
        )
        report = check(no_conclusion)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("No valid Conclusion" in violation for violation in report["violations"]), report)

    def test_top_level_items_and_choice_lines_use_the_declared_indentation(self):
        variants = (
            FULL.replace("   - **Q1.**", "    - **Q1.**"),
            FULL.replace("     - `<a>` After CI passes.", "    - `<a>` After CI passes."),
        )
        for text in variants:
            with self.subTest(text=text[text.index("**Q1.**") - 8:text.index("**Q1.**") + 30]):
                report = check(text)
                self.assertFalse(report["ok"], report)
                self.assertTrue(any("indent" in violation.lower() for violation in report["violations"]), report)


class StyleTests(unittest.TestCase):
    def test_emoji_and_square_brackets_fail_but_code_spans_may_hold_anything(self):
        self.assertFalse(check(FULL.replace("**Login fix:** merged.", "**Login fix:** merged ✅"))["ok"])
        self.assertFalse(check(FULL.replace("**Conclusion:**", "\U0001F3AF **Conclusion:**"))["ok"])
        self.assertFalse(check(FULL.replace("1. **Done:**", "1. **[Done]:**"))["ok"])
        bracket_body = FULL.replace("- **Fix:**", "- **[Fix]:**")
        self.assertNotEqual(bracket_body, FULL)
        self.assertTrue(any("square brackets" in v for v in check(bracket_body)["violations"]))
        self.assertTrue(check(FULL.replace("check `payment.spec.ts:88`.", "check `arr[0]` in `payment.spec.ts:88`."))["ok"])

    def test_a_code_block_in_the_body_is_not_a_wrapped_conclusion(self):
        body_code = FULL.replace("**Result-Zone**\n", "**Result-Zone**\n- **Command:** run this:\n\n```sh\nnpm test\n```\n\n")
        self.assertNotEqual(body_code, FULL)
        self.assertTrue(check(body_code)["ok"], check(body_code))

    def test_conclusion_wrapped_in_a_code_block_fails(self):
        wrapped = "Here is the status.\n\n```markdown\n" + FULL + "```\n\n**Conclusion:** See above.\n"
        self.assertTrue(any("inside a code block" in v for v in check(wrapped)["violations"]))

    def test_openers_closers_and_long_sentences(self):
        self.assertTrue(any("opener" in v for v in check("Great question! " + FULL)["violations"]))
        closer = FULL.replace("- **Tests:** 214 ran and 213 pass.", "- **Tests:** 214 ran and 213 pass. Hope this helps.")
        self.assertTrue(any("pleasantry" in v for v in check(closer)["violations"]))
        long_body = FULL.replace("- **Tests:** 214 ran and 213 pass.", "- **Note:** " + " ".join(["word"] * 29) + ".")
        report = check(long_body)
        self.assertTrue(report["ok"])
        self.assertTrue(any("Long sentence (30 words)" in w for w in report["warnings"]))

    def test_goals_list_aims_current_goals_with_a_bar_and_deferred_work(self):
        G1 = "   - **G1.** Fix the login test -> L1 `########--` 4/5"
        for bad, message in (("`#######---` 4/5", "bar must be ########--"), ("`########--` 6/5", "6 of 5 steps"),
                             ("`----------` 0/0", "0 of 0 steps"), ("`##-#######` 4/5", "bar must be"),
                             ("`########` 4/5", "ends with a bar"), ("", "ends with a bar")):
            with self.subTest(bar=bad):
                text = FULL.replace(G1, G1.replace("`########--` 4/5", bad).rstrip())
                self.assertNotEqual(text, FULL)
                self.assertTrue(any(message in v for v in check(text)["violations"]), check(text)["violations"])
        for good in ("`#####-----` 1/2", "`###-------` 1/4", "`##--------` 1/4", "no plan yet", "no plan yet."):
            with self.subTest(bar=good):
                text = FULL.replace("`########--` 4/5", good)
                self.assertTrue(check(text)["ok"], check(text))
        missing = FULL.replace("-> L1 ", "")
        self.assertTrue(any("must name the L line" in v for v in check(missing)["violations"]))
        unknown = FULL.replace("-> L1", "-> L2")
        self.assertTrue(any("names L2, which Goals does not show" in v for v in check(unknown)["violations"]))
        second = FULL.replace("-> L1", "-> L1 -> L2")
        self.assertTrue(any("names L2, which Goals does not show" in v for v in check(second)["violations"]))
        two_aims = second.replace("   - **G1.**", "   - **L2.** Login stays fast.\n   - **G1.**")
        self.assertTrue(check(two_aims)["ok"], check(two_aims))
        no_aims = missing.replace("   - **L1.** Users can log in from every client.\n", "")
        self.assertTrue(check(no_aims)["ok"], check(no_aims))
        percent = FULL.replace("from every client.", "from every client, 80% done.")
        self.assertTrue(any("no percent" in v for v in check(percent)["violations"]))
        order = FULL.replace("   - **B1.** Update the login guide later.\n", "").replace(
            "   - **L1.**", "   - **B1.** Update the login guide later.\n   - **L1.**")
        self.assertTrue(any("L lines, then G lines, then B lines" in v for v in check(order)["violations"]))
        keyed = FULL.replace("   - **B1.** Update", "   - **Docs:** Update")
        self.assertTrue(any("Section 0 item must start with **L1.** or **G1.** or **B1.**" in v
                            for v in check(keyed)["violations"]))
        empty = FULL[:FULL.index("   - **L1.**")] + FULL[FULL.index("1. **Done:**"):]
        self.assertTrue(check(empty)["ok"], check(empty))

    def test_q_r_and_i_restart_at_1_in_every_reply(self):
        for old, new in (("**Q1.**", "**Q50.**"), ("**R1.**", "**R30.**"), ("**I1.**", "**I2.**")):
            with self.subTest(item=new):
                text = FULL.replace(old, new)
                self.assertTrue(any("from %s1 in every reply" % new[2] in v for v in check(text)["violations"]))
        gap = FULL.replace("     - (b) Now.\n", "     - (b) Now.\n   - **Q3.** Merge the docs too?\n")
        self.assertTrue(any("Q1, Q3" in v for v in check(gap)["violations"]))
        two = FULL.replace("     - (b) Now.\n", "     - (b) Now.\n   - **Q2.** Merge the docs too?\n")
        self.assertTrue(check(two)["ok"], check(two))
        stable = FULL.replace("**L1.**", "**L3.**").replace("-> L1", "-> L3").replace("**G1.**", "**G7.**").replace("**B1.**", "**B4.**")
        self.assertTrue(check(stable)["ok"], check(stable))

    def test_adminzone_reply_has_the_admin_zone_alone(self):
        admin_only = FULL[FULL.index("**Admin-Zone**"):]
        self.assertTrue(check(admin_only)["ok"], check(admin_only))
        partial = FULL[:FULL.index("**Result-Zone**")] + admin_only
        self.assertTrue(any("three zone labels" in v for v in check(partial)["violations"]))
        preface = "**Status:** see below.\n\n" + admin_only
        self.assertTrue(any("Admin-Zone-only" in v for v in check(preface)["violations"]))
        no_blank = admin_only.replace("**Admin-Zone**\n\n", "**Admin-Zone**\n")
        self.assertTrue(any("blank line after" in v for v in check(no_blank)["violations"]))

    def test_conclusion_is_one_sentence(self):
        two = FULL.replace("cause not checked.", "cause not checked. Deploy waits for CI.")
        self.assertTrue(any("2 sentences" in v for v in check(two)["violations"]))
        cjk = FULL.replace("cause not checked.", "cause not checked。还要等 CI。")
        self.assertTrue(any("sentences" in v for v in check(cjk)["violations"]))
        for one in ("cause not checked, e.g. in `check_reply.py`.", "version 0.4.2 is not checked.",
                    "cause in `a.py. B.py` not checked.", "cause not checked, e.g. CI is red.",
                    "cause not checked, e.g. `CI` is red.", "cause i.e. CI not checked.", "Codex vs. Claude not checked."):
            same = FULL.replace("cause not checked.", one)
            self.assertNotEqual(same, FULL)
            self.assertTrue(check(same)["ok"], check(same))

    def test_result_bullets_are_key_first(self):
        plain = FULL.replace("- **Tests:** 214 ran", "- 214 tests ran")
        self.assertTrue(any("Result-Zone bullets" in v for v in check(plain)["violations"]))
        path = FULL.replace("- **Tests:** 214 ran and 213 pass.", "- `tests/auth.spec.ts`: 214 ran and 213 pass.")
        self.assertTrue(check(path)["ok"], check(path))
        nested = FULL.replace("213 pass.", "213 pass.\n   - one detail without a key.")
        self.assertTrue(check(nested)["ok"], check(nested))

    def test_square_brackets_outside_code_fail(self):
        prose = FULL.replace("213 pass.", "213 pass [see CI].")
        self.assertTrue(any("square brackets outside code" in v for v in check(prose)["violations"]))
        link = FULL.replace("213 pass.", "213 pass, see [CI](https://example.com).")
        self.assertFalse(check(link)["ok"])
        code = FULL.replace("213 pass.", "213 pass in `items[0]`.")
        self.assertTrue(check(code)["ok"], check(code))
        fenced = FULL.replace("**Result-Zone**\n", "**Result-Zone**\n- **Data:** shown below.\n\n```json\n[1, 2]\n```\n\n")
        self.assertTrue(check(fenced)["ok"], check(fenced))

    def test_code_blocks_do_not_count_as_sentences(self):
        code = "```\n" + " ".join(["token"] * 60) + "\n```\n\n" + FULL
        self.assertEqual(check(code)["warnings"], [])
        odd_backtick = "```sh\necho `date\n" + " ".join(["word"] * 40) + "\n```\n\n" + FULL
        self.assertEqual(check(odd_backtick)["warnings"], [])


class MultilingualTests(unittest.TestCase):
    def test_body_can_be_multilingual_but_labels_stay_english(self):
        swahili = ("- **Kurekebisha:** Kuingia kumerekebishwa.\n\n**Hitimisho:** Jaribio moja la malipo bado linashindwa.\n\n"
                   "0. **Imekamilika:**\n   - **Kuingia:** kumerekebishwa.\n1. **Inaendelea:**\n2. **Inasubiri:**\n3. **Maswali:**\n"
                   "   - **Q1.** Niangalie sasa?\n     - `<a>` Ndiyo.\n     - (b) Baadaye.\n"
                   "4. **Kazi zijazo:**\n5. **Yaliyobaki:**\n   - **jsonwebtoken:** kusasisha.\n6. **Hatari:**\n7. **Mawazo:**\n")
        report = check(swahili)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("conclusion label must be exactly" in v for v in report["violations"]))
        self.assertTrue(any("Section 0 label must be" in v for v in report["violations"]))
        self.assertEqual(report["stats"]["sections"], list(range(8)))

    def test_length_counts_characters_in_scripts_without_spaces(self):
        long_ja = "- **説明：** " + "これはとても長い説明の文で" * 6 + "す。\n\n**Conclusion：** 完了しました。\n"
        self.assertTrue(any(w.startswith("Long sentence") for w in check(long_ja)["warnings"]))
        two = ("- **测试：** 测试已经在预发布环境中全部运行完毕并且全部通过了没有问题。"
               "支付模块的一个测试仍然失败但是它的原因到现在还没有检查过。\n\n**Conclusion：** 完成。\n")
        self.assertEqual(check(two)["warnings"], [])

    def test_fullwidth_colons_are_rejected_only_in_structural_markers(self):
        wide = FULL.replace("**Conclusion:**", "**Conclusion：**").replace("**Done:**", "**Done：**").replace("**Login fix:**", "**登录修复：**")
        self.assertNotEqual(wide, FULL)
        report = check(wide)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("ASCII" in violation for violation in report["violations"]), report)
        prose = FULL.replace("Login is fixed;", "Login： is fixed;")
        self.assertTrue(check(prose)["ok"], check(prose))


if __name__ == "__main__":
    unittest.main()
