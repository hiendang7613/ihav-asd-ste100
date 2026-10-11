"""Goals preview through the shared hook; these checks do not prove model obedience."""
import json
import os
import subprocess
import unittest
from pathlib import Path

import test_open_items as existing

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ("# Goals\n## L — confirmed\n"
            "- L1 | ~88% (was 85) | Keep vendor capabilities. | basis: source only | moved: 2026-10-11\n"
            "- L7 | ~38% (was 36) | Simplify. | basis: source | moved: not since 2026-10-10 (needs permission)\n"
            "## L20-L25 — dimensions\nShared basis: offline coverage, not a quality score.\n"
            "- L20 | ~64% | Product 01 84%, 02 55% | next: observe real use | moved: 2026-10-11 (small)\n"
            "## G — current\n- G1 Keep goals visible.\n## B — deferred\n- B1 Provider run paused.\n")


class GoalsHookTests(unittest.TestCase):
    def setUp(self):
        existing.OpenHookTests.setUp(self)
        self.file = self.file.with_name("goals.md")

    def tearDown(self):
        self.fixture.cleanup()

    def hook(self, *args, **kwargs):
        return existing.OpenHookTests.hook(self, *args, **kwargs)

    def block(self, text):
        self.assertIn("Goals (register text", text)
        return text[text.index("Goals (register text"):].split(" Now ", 1)[0].rstrip()

    def direct(self, expression):
        program = "import {parseGoals,goalsBlock} from './hooks/goals.mjs'; console.log(JSON.stringify(" + expression + "));"
        result = subprocess.run(["node", "--input-type=module", "-e", program], cwd=ROOT,
                                capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        return json.loads(result.stdout)

    def test_absent_goals_keeps_reminder_and_never_creates_file(self):
        out = self.hook()
        self.assertIn("Reply shape", out)
        self.assertNotIn("Goals (register text", out)
        self.assertNotIn("Goals unavailable", out)
        self.assertFalse(self.file.exists())
        self.assertLess(len(out.encode()), 570)

    def test_present_shape_uses_current_percent_and_shared_basis(self):
        self.file.write_text(REGISTER)
        block = self.block(self.hook())
        self.assertIn("3 L lines; ids L1, L7, L20; 1 G, 1 B", block)
        for text in ("L1 ~88%;", "L7 ~38%;", "L20 ~64%;", "EVERY L", "after summaries", "Only the user", "proposed until answered"):
            self.assertIn(text, block)
        for text in ("was 85", "L20 ~84%", "source only"):
            self.assertNotIn(text, block)
        self.assertEqual(self.file.read_text(), REGISTER)

    def test_twenty_five_ids_are_complete_without_a_length_limit_of_eighteen(self):
        self.file.write_text("## L\n" + "".join(
            f"- L{n} | ~{n}% | Goal {n} | basis: source | moved: 2026-10-11\n" for n in range(1, 26)))
        block = self.block(self.hook())
        self.assertIn("25 L lines; ids " + ", ".join(f"L{n}" for n in range(1, 26)), block)
        self.assertIn("L25 ~25%;", block)
        self.assertLessEqual(len(block.encode()), 2048)

    def test_both_hosts_and_start_prompt_use_the_same_goals_block(self):
        self.file.write_text(REGISTER)
        self.assertEqual(self.block(self.hook()), self.block(self.hook(host="codex")))
        for event in ("SessionStart", "UserPromptSubmit"):
            out = self.hook(event=event)
            self.assertEqual(out.count("Goals (register text"), 1)
            self.assertIn("3 L lines", out)
        self.assertIn("RULES UPDATED", self.hook(host="codex", IHAV_STE100_BRIDGED="1", CODEX_HOME=str(self.home / "old-codex")))

    def test_g_is_exact_and_requests_full_goals_not_a_preview(self):
        self.file.write_text(REGISTER)
        for prompt in ("g", " G. "):
            self.assertIn("The user typed g:", self.hook(prompt))
            self.assertIn("not this preview", self.hook(prompt))
        for prompt in ("`g`", '"g"', "g means goals", "show g", "g1.a"):
            self.assertNotIn("The user typed g:", self.hook(prompt))

    def test_still_means_three_calendar_days_not_a_repeat_or_old_percent(self):
        self.file.write_text(REGISTER)
        source = json.dumps(str(self.file))
        at_two = self.direct(f"goalsBlock({source},false,new Date(2026,9,12,12))")
        at_three = self.direct(f"goalsBlock({source},false,new Date(2026,9,13,12))")
        self.assertIn("Still >=3 calendar days: none with a known date", at_two)
        self.assertIn("Still >=3 calendar days: L7;", at_three)
        self.assertIn("cheapest next step", at_three)
        self.assertEqual(self.file.read_text(), REGISTER)

    def test_unknown_or_invalid_moved_date_is_not_claimed_stale(self):
        self.file.write_text(REGISTER.replace("2026-10-11", "2026-02-30").replace("not since 2026-10-10 (needs permission)", "unknown"))
        block = self.direct(f"goalsBlock({json.dumps(str(self.file))},false,new Date(2026,9,14,12))")
        self.assertIn("Still >=3 calendar days: none with a known date", block)
        self.assertIn("moved date unknown: L1, L7, L20", block)

    def test_broken_duplicate_invalid_utf8_and_huge_files_warn_once(self):
        for raw in (b"not a register", b"## L\n- L7 broken\n", b"## L\n- L01 | ~1% | bad\n",
                    b"## L\n- L1 | ~101% | bad\n", b"## L\n\xff", b"x" * (128 * 1024 + 1),
                    REGISTER.encode() + b"- L1 | ~88% | duplicate\n"):
            with self.subTest(raw=raw[:32]):
                self.file.write_bytes(raw)
                out = self.hook()
                self.assertIn("Reply shape", out)
                self.assertEqual(out.count("Goals unavailable"), 1)
                self.assertNotIn("Goals (register text", out)

    def test_link_directory_and_pipe_refused_without_reading_target(self):
        self.file.mkdir(); self.assertIn("Goals unavailable", self.hook()); self.file.rmdir()
        os.mkfifo(self.file); self.assertIn("Goals unavailable", self.hook()); self.file.unlink()
        outside = self.home / "outside"; outside.write_text(REGISTER)
        self.file.symlink_to(outside)
        out = self.hook()
        self.assertIn("Goals unavailable", out)
        self.assertNotIn("3 L lines", out)

    def test_linked_preference_directories_are_refused(self):
        self.file.parent.rmdir()
        outside = self.home / "outside"; outside.mkdir(); (outside / "goals.md").write_text(REGISTER)
        self.file.parent.symlink_to(outside, target_is_directory=True)
        self.assertIn("Goals unavailable", self.hook())

    def test_nested_lookup_prefers_nearest_and_respects_worktree_boundary(self):
        self.file.write_text(REGISTER)
        child = self.project / "src"; child.mkdir()
        self.assertIn("3 L lines", self.hook(cwd=child))
        near = child / ".ihav_space/ihav-asd-ste100/goals.md"; near.parent.mkdir(parents=True)
        near.write_text("## L\n- L99 | ~1% | nearer | moved: unknown\n")
        self.assertIn("1 L lines; ids L99", self.hook(cwd=child))
        (child / ".git").write_text("gitdir: /elsewhere\n"); near.unlink()
        self.assertNotIn("Goals (register text", self.hook(cwd=child))

    def test_empty_l_section_is_zero_and_not_absent_or_broken(self):
        self.file.write_text("## L\n## G\n- G1 Ask about direction.\n")
        out = self.hook()
        self.assertIn("0 L lines; ids none; 1 G, 0 B", out)
        self.assertNotIn("Goals unavailable", out)

    def test_fenced_rows_are_examples_not_goals(self):
        self.file.write_text(REGISTER + "```md\n- L99 | ~99% | example\n```\n")
        self.assertIn("3 L lines", self.hook())
        self.assertNotIn("L99", self.block(self.hook()))

    def test_same_marker_with_info_text_does_not_close_a_fence(self):
        for marker in ("```", "~~~"):
            with self.subTest(marker=marker):
                self.file.write_text(REGISTER + f"{marker}md\n{marker}js\n- L99 | ~99% | example\n{marker}\n")
                block = self.block(self.hook())
                self.assertIn("3 L lines", block)
                self.assertNotIn("L99", block)

    def test_unfittable_id_list_warns_without_silently_truncating(self):
        self.file.write_text("## L\n" + "".join(f"- L{n} | ~1% | goal | moved: unknown\n" for n in range(1, 500)))
        out = self.hook("g")
        self.assertEqual(out.count("Goals unavailable"), 1)
        self.assertNotIn("Goals (register text", out)
        self.assertLess(len(out.encode()), 800)

    def test_goal_budget_does_not_change_existing_compass_or_open_block(self):
        self.file.with_name("compass.md").write_text("- V1 Keep vendor capability.\n")
        self.file.with_name("open-items.md").write_text(existing.REGISTER)
        before = self.hook().split(" Now ", 1)[0]
        self.file.write_text(REGISTER)
        after = self.hook().split(" Goals (register text", 1)[0]
        self.assertEqual(before, after)
        self.assertLessEqual(len(self.block(self.hook("g")).encode()), 2048)
        self.assertNotIn("\ufffd", self.hook())

    def test_mode_off_suppresses_goals_and_post_tool_batch_stays_clock_only(self):
        self.file.write_text(REGISTER)
        self.assertNotIn("Goals (register text", self.hook(event="PostToolBatch"))
        self.hook("stop ste mode"); self.assertEqual(self.hook(), "")
        self.assertEqual(self.hook(host="codex", IHAV_ASD_STE100="off"), "")


if __name__ == "__main__":
    unittest.main()
