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
        # 520 bytes (480 until 0.19.3, 400 until 0.11.0): the L layout keeps agents from drifting back to old habits.
        self.assertLess(len(out.encode()), 520)
        self.assertIn("0. **Goals:** (`**L1.** [~N%] [bar] | aim`, then plain G and B), 1. **Done:**, 2. **Doing:**, 3. **Todos:**, 4. **Pending:**, "
                      "5. **Quests:**, 6. **Risks:**, 7. **Ideas:**", out)
        for zone in ("**Agents-Zone** (short step lines: `time` why => what)", "No emoji or square brackets except L progress.", "**Result-Zone**", "**Admin-Zone**"):
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

    def test_bad_input_and_missing_root_never_fail(self):
        self.opt_in()
        self.assertEqual(self.run_hook("not json"), "")
        env = dict(self.env); env.pop("CLAUDE_PLUGIN_ROOT")
        result = subprocess.run(["sh", "-c", LAUNCH], input="{}", capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
