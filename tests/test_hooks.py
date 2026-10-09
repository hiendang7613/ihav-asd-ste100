"""The hook runs through the exact launcher in hooks/hooks.json, in a throwaway home directory."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = json.loads((ROOT / "hooks/hooks.json").read_text())
LAUNCH = HOOKS["hooks"]["SessionStart"][0]["hooks"][0]["command"]
# 570 bytes for the whole prompt reminder (520 until the guess line, 480 until 0.19.3, 400 until 0.11.0): the L layout and
# the first Agents-Zone line "- guess => ..." keep agents from drifting back to old habits.
REMINDER_LIMIT = 570


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ste hook ")
        home = Path(self.tmp.name)
        for name in (".claude", ".codex", "tmp"):
            (home / name).mkdir()
        self.home = home
        self.env = {"PATH": os.environ["PATH"], "HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                    "CODEX_HOME": str(home / ".codex"), "TMPDIR": str(home / "tmp"), "CLAUDE_PLUGIN_ROOT": str(ROOT)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload, command=LAUNCH, environment=None, **env):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        result = subprocess.run(["sh", "-c", command], input=text, capture_output=True, text=True,
                                env=self.env | (environment or {}) | env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        if isinstance(payload, dict) and payload.get("hook_event_name") == "UserPromptSubmit" and result.stdout:
            data = json.loads(result.stdout)
            self.assertNotIn("decision", data)
            self.assertNotIn("continue", data)
            specific = data["hookSpecificOutput"]
            self.assertEqual(specific["hookEventName"], "UserPromptSubmit")
            self.assertIsInstance(specific["additionalContext"], str)
            return specific["additionalContext"]
        return result.stdout

    def opt_in(self):
        """On by default since 0.1.1: nothing to do."""

    def opt_out(self, where=".claude"):
        (self.home / where / ".ihav-asd-ste100-off").write_text("")

    def test_both_events_use_the_same_launcher(self):
        prompt_command = HOOKS["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertEqual(prompt_command, LAUNCH)
        self.assertEqual(HOOKS["hooks"]["PostToolBatch"][0]["hooks"][0]["command"], LAUNCH)
        self.assertIn("startup", HOOKS["hooks"]["SessionStart"][0]["matcher"])

    def test_on_by_default_after_install(self):
        self.assertTrue(self.run_hook({"hook_event_name": "SessionStart", "session_id": "a"}).startswith("STE REPLY MODE ACTIVE"))
        self.assertIn("Reply shape", self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "hi"}))

    def test_session_start_injects_the_skill_body_without_frontmatter(self):
        self.opt_in()
        out = self.run_hook({"hook_event_name": "SessionStart", "session_id": "a"})
        self.assertTrue(out.startswith("STE REPLY MODE ACTIVE"))
        self.assertIn("## The shape", out)
        self.assertNotIn("disable-model-invocation", out)

    def test_opt_out_file_in_either_home_or_environment_silences_both_events(self):
        start = {"hook_event_name": "SessionStart", "session_id": "a"}
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "hi"}
        self.assertIn(str(self.home / ".claude/.ihav-asd-ste100-off"), self.run_hook(start))
        for where in (".claude", ".codex"):
            with self.subTest(where=where):
                self.opt_out(where)
                self.assertEqual((self.run_hook(start), self.run_hook(prompt)), ("", ""))
                (self.home / where / ".ihav-asd-ste100-off").unlink()
        for name in ("IHAV_ASD_STE100", "EVAL_IHAV_ASD_STE100"):
            with self.subTest(name=name):
                self.assertEqual(self.run_hook(start, **{name: "OFF"}), "")
                self.assertEqual(self.run_hook(prompt, **{name: "off"}), "")
        self.assertIn("STE REPLY MODE ACTIVE", self.run_hook(start, IHAV_ASD_STE100="on"))

    def test_prompt_reminder_is_one_line_and_short(self):
        self.opt_in()
        out = self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "fix the bug"})
        self.assertEqual(out.count("\n"), 1)
        self.assertLess(len(out.encode()), REMINDER_LIMIT)
        self.assertIn("0. **Goals:** (`**L1.** [~N%] [bar] | aim`, then plain G and B), 1. **Done:**, 2. **Doing:**, 3. **Todos:**, 4. **Pending:**, "
                      "5. **Quests:**, 6. **Risks:**, 7. **Ideas:**", out)
        for zone in ("**Agents-Zone** (first `- guess => the user's why and final aim`, then step lines: `time` why => what)",
                     "No emoji or square brackets except L progress.", "**Result-Zone**", "**Admin-Zone**"):
            self.assertIn(zone, out)
        self.assertRegex(out, r" Now (1[0-2]|[1-9]):[0-5][0-9] (AM|PM)\.\n$")
        self.assertIn("items are sub-items with a bold key", out)
        self.assertTrue(out.isascii())

    def test_post_tool_batch_gives_the_local_time_unless_the_mode_is_off(self):
        batch = {"hook_event_name": "PostToolBatch", "session_id": "t", "tool_calls": [{"tool_name": "Read"}]}
        data = json.loads(self.run_hook(batch))
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PostToolBatch")
        self.assertRegex(data["hookSpecificOutput"]["additionalContext"],
                         r"^ihav-asd-ste100 clock: (1[0-2]|[1-9]):[0-5][0-9] (AM|PM)$")
        self.assertTrue(data["hookSpecificOutput"]["additionalContext"].isascii())
        self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "t", "prompt": "stop ste mode"})
        self.assertEqual(self.run_hook(batch), "")
        self.assertEqual(self.run_hook(dict(batch, session_id="u"), IHAV_ASD_STE100="off"), "")
        self.opt_out()
        self.assertEqual(self.run_hook(dict(batch, session_id="u")), "")

    def test_clock_uses_twelve_hour_ascii_time(self):
        script = ("import('./hooks/ste-mode.mjs').then(m => console.log([0, 9, 12, 16, 23].map(h => "
                  "m.clock(new Date(2026, 9, 2, h, 5))).join('|')))")
        out = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30,
                             env=self.env | {"IHAV_ASD_STE100": "off"})
        self.assertEqual(out.stdout.strip().splitlines()[-1], "12:05 AM|9:05 AM|12:05 PM|4:05 PM|11:05 PM")

    def test_stop_and_restart_work_per_session(self):
        self.opt_in()
        stop = self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": " Stop STE mode. "})
        self.assertIn("off for this session", stop)
        self.assertEqual(self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "next"}), "")
        self.assertEqual(self.run_hook({"hook_event_name": "SessionStart", "session_id": "a"}), "")
        self.assertIn("Reply shape", self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "b", "prompt": "next"}))
        prose = {"hook_event_name": "UserPromptSubmit", "session_id": "b", "prompt": "in normal mode the app crashes"}
        self.assertIn("Reply shape", self.run_hook(prose))
        self.assertIn("Reply shape", self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "ste mode"}))
        self.assertIn("Reply shape", self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "next"}))

    def test_odd_session_ids_cannot_escape_the_state_directory(self):
        self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "../../evil", "prompt": "normal mode"})
        written = [p for p in self.home.rglob("*.off")]
        self.assertEqual([p.parent for p in written], [self.home / ".claude/.ihav-asd-ste100-sessions"])
        self.assertEqual(list((self.home / "tmp").iterdir()), [])

    def test_stop_phrase_inside_a_longer_prompt_counts_unless_quoted(self):
        def prompt(session, text):
            return self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": text})
        self.assertIn("off for this session", prompt("c", "Stop STE mode and fix the login test"))
        self.assertEqual(prompt("c", "next"), "")
        self.assertIn("Reply shape", prompt("c", "ok, start ste mode again please"))
        for quoted in ('the docs say "stop ste mode" turns it off', "the docs say 'stop ste mode' turns it off",
                       "the docs say ‘stop ste mode’ turns it off", "run `stop ste mode` later",
                       "```\nstop ste mode\n```"):
            with self.subTest(quoted=quoted):
                self.assertIn("Reply shape", prompt("d", quoted))

    def test_codex_root_and_session_marker_use_codex_home(self):
        environment = self.env.copy()
        environment.pop("CLAUDE_CONFIG_DIR")
        environment.pop("CLAUDE_PLUGIN_ROOT")
        environment["PLUGIN_ROOT"] = str(ROOT)

        start = {"hook_event_name": "SessionStart", "session_id": "codex-session"}
        self.assertIn("STE REPLY MODE ACTIVE", self.run_hook(start, environment=environment))
        stop = {"hook_event_name": "UserPromptSubmit", "session_id": "codex-session", "prompt": "stop ste mode"}
        self.assertIn("off for this session", self.run_hook(stop, environment=environment))
        marker = self.home / ".codex/.ihav-asd-ste100-sessions/codex-session.off"
        self.assertTrue(marker.is_file())
        self.assertEqual(self.run_hook({**stop, "prompt": "next"}, environment=environment), "")

    # --- Compass: <project>/.ihav_space/ihav-asd-ste100/compass.md --------------------------------------------------

    COMPASS = ("# Compass of the sample project. Edit: remove the ? to activate a line, delete a line to strike it.\n"
               "## V Vision\n- V1 Connect many vendors; own no complex harness.\n- V2 The admin chats only through the UI.\n"
               "\nnot a line\n- V3: a colon after the ID is ignored\n- W5? A proposed line stays out.\n"
               "## C Code\n* C1 Names are easy to read.\n")

    def project(self, text=None, name="project", git=".git", where=""):
        """A project folder with a git root marker and, unless text is None, a compass file. Returns the project path."""
        project = self.home / name
        folder = project / where if where else project
        (project / git).mkdir(parents=True) if git == ".git" else project.mkdir(parents=True, exist_ok=True)
        if git == "gitfile":
            (project / ".git").write_text("gitdir: /elsewhere\n")
        if text is not None:
            (folder / ".ihav_space/ihav-asd-ste100").mkdir(parents=True)
            (folder / ".ihav_space/ihav-asd-ste100/compass.md").write_text(text, encoding="utf-8")
        return project

    def prompt(self, cwd, text="fix the bug", session="c", **extra):
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": text}
        if cwd is not None:
            payload["cwd"] = str(cwd)
        return self.run_hook(payload, **extra)

    def test_compass_file_adds_the_active_lines_to_the_reminder_and_nothing_else(self):
        plain = self.prompt(None)
        out = self.prompt(self.project(self.COMPASS), session="d")
        self.assertTrue(out.startswith(plain.split(" Now ")[0]))
        self.assertEqual(out.count("\n"), 1)
        self.assertRegex(out, r" Now (1[0-2]|[1-9]):[0-5][0-9] (AM|PM)\.\n$")
        self.assertIn("Compass (admin's core views, keep every reply consistent with them): "
                      "V1 Connect many vendors; own no complex harness; V2 The admin chats only through the UI; C1 Names are easy to read.", out)
        self.assertIn("Show X. **Compass:** first, above 0. **Goals:**", out)
        self.assertIn("**X!** ID: what, why; choose in Quests.", out)
        for ignored in ("W5", "A proposed line", "Proposed", "V3", "colon", "not a line", "Edit:"):
            self.assertNotIn(ignored, out)

    def test_no_compass_file_leaves_the_reminder_exactly_as_before(self):
        reference = self.prompt(None).split(" Now ")[0]
        for cwd in (None, self.project(None), "/no/such/folder", 5, ""):
            with self.subTest(cwd=cwd):
                out = self.prompt(cwd, session="e")
                self.assertEqual(out.split(" Now ")[0], reference)
                self.assertNotIn("Compass", out)
                self.assertLess(len(out.encode()), REMINDER_LIMIT)
        only_proposed = self.project("- W5? Only a proposed line.\n## no active line\n", name="proposed")
        self.assertEqual(self.prompt(only_proposed, session="f").split(" Now ")[0], reference)

    def test_compass_is_searched_from_cwd_up_to_the_git_root_and_the_first_file_wins(self):
        project = self.project("- V1 Root line.\n")
        deep = project / "src/deep"
        deep.mkdir(parents=True)
        self.assertIn("V1 Root line", self.prompt(deep))
        near = project / "src"
        (near / ".ihav_space/ihav-asd-ste100").mkdir(parents=True)
        (near / ".ihav_space/ihav-asd-ste100/compass.md").write_text("- V9 Nearer line.\n")
        out = self.prompt(deep, session="g")
        self.assertIn("V9 Nearer line", out)
        self.assertNotIn("Root line", out)
        # A worktree has a .git file; a folder without any git root searches only itself.
        worktree = self.project("- V1 Worktree line.\n", name="worktree", git="gitfile")
        (worktree / "sub").mkdir()
        self.assertIn("V1 Worktree line", self.prompt(worktree / "sub", session="h"))
        loose = self.home / "loose"
        (loose / "child").mkdir(parents=True)
        (loose / ".ihav_space/ihav-asd-ste100").mkdir(parents=True)
        (loose / ".ihav_space/ihav-asd-ste100/compass.md").write_text("- V1 Parent of a folder with no git root.\n")
        self.assertNotIn("Compass", self.prompt(loose / "child", session="i"))
        self.assertIn("Compass", self.prompt(loose, session="i"))

    def test_the_x_prompt_also_lists_the_proposed_lines_and_no_other_prompt_does(self):
        project = self.project(self.COMPASS)
        for index, text in enumerate(("x", " Compass. ", "/x", "/compass")):
            with self.subTest(prompt=text):
                out = self.prompt(project, text, session="x%d" % index)
                self.assertIn("Proposed, not enforced (for the x reply only): W5 A proposed line stays out.", out)
                self.assertIn("V1 Connect many vendors", out)
        for index, text in enumerate(("x marks the spot", "show the compass", "xx")):
            with self.subTest(prompt=text):
                self.assertNotIn("Proposed", self.prompt(project, text, session="y%d" % index))

    def test_session_start_and_a_rules_update_carry_the_compass_once(self):
        project = self.project(self.COMPASS)
        start = self.run_hook({"hook_event_name": "SessionStart", "session_id": "s", "cwd": str(project)})
        self.assertTrue(start.startswith("STE REPLY MODE ACTIVE"))
        self.assertEqual(start.count("Compass (admin's core views"), 1)
        self.assertIn("V2 The admin chats only through the UI", start)
        self.assertNotIn("W5", start)
        bare = self.run_hook({"hook_event_name": "SessionStart", "session_id": "t", "cwd": str(self.project(None, name="bare"))})
        self.assertNotIn("Compass (admin's", bare)
        update = self.prompt(project, session="u", IHAV_STE100_BRIDGED="1")
        self.assertIn("STE REPLY RULES UPDATED", update)
        self.assertEqual(update.count("Compass (admin's core views"), 1)

    def test_the_compass_follows_the_mode_switches(self):
        project = self.project(self.COMPASS)
        self.assertIn("Compass (admin's", self.prompt(project, session="m"))
        self.prompt(project, "stop ste mode", session="m")
        self.assertEqual(self.prompt(project, session="m"), "")
        self.assertEqual(self.prompt(project, session="n", IHAV_ASD_STE100="off"), "")

    def test_compass_percent_marks_reach_the_reminder_as_written(self):
        text = "- V1 [~95%] Connect many vendors; own no complex harness.\n- V2 No percent on this older line.\n- V4? [~50%] A guess.\n"
        project = self.project(text)
        out = self.prompt(project, session="pc")
        self.assertIn("): V1 [~95%] Connect many vendors; own no complex harness; V2 No percent on this older line. Show X.", out)
        self.assertIn("as `- **ID.** [~N%] text` (copy each percent)", out)
        self.assertNotIn("A guess", out)
        self.assertIn("Proposed, not enforced (for the x reply only): V4 [~50%] A guess.", self.prompt(project, "x", session="pc"))

    def test_compass_lines_are_cleaned_and_a_foreign_file_format_is_ignored(self):
        text = "\ufeff- V1\tA  spaced\t line.\r\n- V2 Two sentences. Kept;\r\n## - V3 heading\r\n  - V4 indented\r\n-V5 no space\r\n- 7 digit first\r\n- VV1 two letters\r\n"
        out = self.prompt(self.project(text), session="p")
        self.assertIn("): V1 A spaced line; V2 Two sentences. Kept. Show X.", out)
        self.assertNotIn("V3", out)
        self.assertNotIn("V4", out)
        self.assertNotIn("V5", out)
        self.assertNotIn("VV1", out)

    def test_an_unreadable_compass_file_never_removes_the_reminder(self):
        project = self.project(self.COMPASS)
        file = project / ".ihav_space/ihav-asd-ste100/compass.md"
        file.chmod(0)
        try:
            if os.access(file, os.R_OK):
                self.skipTest("this user can read a mode 000 file")
            out = self.prompt(project)
            self.assertIn("Reply shape", out)
            self.assertNotIn("Compass", out)
            self.assertIn("STE REPLY MODE ACTIVE", self.run_hook({"hook_event_name": "SessionStart", "session_id": "r", "cwd": str(project)}))
        finally:
            file.chmod(0o644)

    def test_a_folder_or_a_pipe_in_place_of_the_compass_file_is_ignored_without_waiting(self):
        folder = self.project(None, name="folder")
        (folder / ".ihav_space/ihav-asd-ste100/compass.md").mkdir(parents=True)
        self.assertNotIn("Compass", self.prompt(folder))
        pipe = self.project(None, name="pipe")
        (pipe / ".ihav_space/ihav-asd-ste100").mkdir(parents=True)
        os.mkfifo(pipe / ".ihav_space/ihav-asd-ste100/compass.md")
        out = self.prompt(pipe, session="q")
        self.assertIn("Reply shape", out)
        self.assertNotIn("Compass", out)

    def test_a_long_or_huge_compass_is_capped_and_the_reminder_says_how_many_lines_were_cut(self):
        lines = "".join("- V%d Line number %d of the long project list.\n" % (n, n) for n in range(1, 101))
        out = self.prompt(self.project(lines))
        self.assertIn("V60 Line number 60", out)
        self.assertNotIn("V61 ", out)
        self.assertIn("40 more active lines cut (over 60 lines or 4 KB).", out)
        wide = "".join("- A%d %s\n" % (n, "word " * 70) for n in range(1, 40))
        out = self.prompt(self.project(wide, name="wide"), session="w")
        self.assertLess(len(out.encode()), REMINDER_LIMIT + 4096 + 700)
        self.assertRegex(out, r"\d+ more active lines cut")
        huge = "- V1 First line stays.\n" + "".join("- V%d Filler line number %d.\n" % (n, n) for n in range(2, 300000))
        self.assertGreater(len(huge), 5_000_000)
        out = self.prompt(self.project(huge, name="huge"), session="z")
        self.assertIn("V1 First line stays", out)
        self.assertRegex(out, r"\d+\+ more active lines cut")
        self.assertLess(len(out.encode()), REMINDER_LIMIT + 4096 + 700)

    def test_codex_gets_the_compass_from_the_same_core(self):
        environment = self.env.copy()
        environment.pop("CLAUDE_CONFIG_DIR")
        environment.pop("CLAUDE_PLUGIN_ROOT")
        environment["PLUGIN_ROOT"] = str(ROOT)
        project = self.project(self.COMPASS)
        out = self.prompt(project, environment=environment)
        self.assertIn("Compass (admin's core views, keep every reply consistent with them): V1 Connect many vendors", out)
        start = self.run_hook({"hook_event_name": "SessionStart", "session_id": "k", "cwd": str(project)}, environment=environment)
        self.assertIn("V2 The admin chats only through the UI", start)
        self.assertNotIn("W5", start)


    def test_bad_input_and_missing_root_never_fail(self):
        self.opt_in()
        self.assertEqual(self.run_hook("not json"), "")
        env = dict(self.env); env.pop("CLAUDE_PLUGIN_ROOT")
        result = subprocess.run(["sh", "-c", LAUNCH], input="{}", capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
