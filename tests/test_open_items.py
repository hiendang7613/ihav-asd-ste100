"""Offline register context and reply shape; no model-following or activation claim."""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_check_reply import FULL
from check_reply import check
from test_deepquests import ITEM, room_leader

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path('.ihav_space/ihav-asd-ste100/open-items.md')
REGISTER = ("# Register\n\nRules: silence is not consent.\n"
            "## Open — Quests\n"
            "- O7 | Q | first 12:36 | Approve: deploy? | `<a>` later; (b) now\n"
            "- O8 | Q | first 00:42 | Approve: old request? | `<a>` wait; (b) now\n"
            "## Open — Risks\n- O12 | R | 00:49 | Unknown outcome.\n"
            "## Open — Ideas\n- O13 | I | 01:58 | Improve the page.\n"
            "## Open — DeepQuests\n- O14 | D | 00:18 | guess ~70%: shared control | ask: right?\n"
            "## Closed\n- O1 | Q | first 00:01 | answered: `o1.a`\n")
COUNT = '   - **Open items:** 5 earlier open items: 2 Quests, 1 Risks, 1 Ideas, 1 DeepQuests; type `o` to see all.\n'


class OpenHookTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix='ste-open-')
        self.home = Path(self.fixture.name)
        self.project = self.home / 'project'
        self.project.mkdir()
        (self.project / '.git').mkdir()
        self.file = self.project / RELATIVE
        self.file.parent.mkdir(parents=True)
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.home),
                    'CLAUDE_CONFIG_DIR': str(self.home / '.claude'), 'CODEX_HOME': str(self.home / '.codex'),
                    'IHAV_HOME': str(self.home / '.ihav'), 'CLAUDE_PLUGIN_ROOT': str(ROOT)}

    def tearDown(self):
        self.fixture.cleanup()

    def hook(self, prompt='continue', host='claude', event='UserPromptSubmit', cwd=None, **extra):
        env = self.env | extra
        if host == 'codex':
            del env['CLAUDE_PLUGIN_ROOT']; del env['CLAUDE_CONFIG_DIR']
            env['PLUGIN_ROOT'] = str(ROOT)
        payload = {'hook_event_name': event, 'session_id': host, 'prompt': prompt, 'cwd': str(cwd or self.project)}
        result = subprocess.run(['node', str(ROOT / 'hooks/ste-mode.mjs')], input=json.dumps(payload),
                                text=True, capture_output=True, env=env, timeout=10)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        if result.stdout and event == 'UserPromptSubmit':
            data = json.loads(result.stdout)
            self.assertNotIn('decision', data)
            self.assertNotIn('continue', data)
            return data['hookSpecificOutput']['additionalContext']
        return result.stdout

    def block(self, text):
        return text[text.index('Open items ('):].split(' Now ', 1)[0].rstrip()

    def test_absent_file_preserves_short_reminder_and_does_not_create_register(self):
        out = self.hook()
        self.assertIn('Reply shape', out)
        self.assertNotIn('Open items', out)
        self.assertLess(len(out.encode()), 570)
        self.assertFalse(self.file.exists())

    def test_counts_exclude_closed_and_oldest_recorded_quests_are_previewed(self):
        self.file.write_text(REGISTER)
        out = self.hook()
        self.assertIn('5 Open; 2 Quests, 1 Risks, 1 Ideas, 1 DeepQuests', out)
        self.assertLess(out.index('O8 "'), out.index('O7 "'))
        self.assertNotIn('answered:', out)
        self.assertNotIn('O1 ', out)
        self.assertEqual(out.count('Open items ('), 1)
        self.assertEqual(self.file.read_text(), REGISTER)

    def test_both_hosts_use_identical_open_block_and_shared_launcher(self):
        self.file.write_text(REGISTER)
        self.assertEqual(self.block(self.hook(host='claude')), self.block(self.hook(host='codex')))
        manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        self.assertEqual(manifest['hooks'], './hooks/hooks.json')
        hooks = json.loads((ROOT / 'hooks/hooks.json').read_text())['hooks']
        self.assertEqual(hooks['SessionStart'][0]['hooks'][0]['command'], hooks['UserPromptSubmit'][0]['hooks'][0]['command'])

    def test_start_prompt_and_version_update_carry_block_once(self):
        self.file.write_text(REGISTER)
        for out in [self.hook(event='SessionStart'), self.hook(), self.hook(host='codex', IHAV_STE100_BRIDGED='1')]:
            self.assertEqual(out.count('Open items ('), 1)
            self.assertIn('stable O id', out)

    def test_o_is_an_exact_command_for_full_open_not_capped_preview(self):
        self.file.write_text(REGISTER)
        for prompt in ['o', ' O. ']:
            self.assertIn('The user typed o:', self.hook(prompt))
        for prompt in ['`o`', '"o"', 'o7.a', 'o means open', 'show o']:
            self.assertNotIn('The user typed o:', self.hook(prompt))

    def test_block_has_own_utf8_cap_and_at_most_three_quest_previews(self):
        self.file.write_text('## Open — Quests\n' + ''.join(
            '- O%d | Q | first 00:%02d | %s\n' % (n, n, '漢字 ' * 200) for n in range(1, 10)))
        out = self.hook('o')
        self.assertIn('9 Open; 9 Quests, 0 Risks, 0 Ideas, 0 DeepQuests', out)
        self.assertLessEqual(len(self.block(out).encode()), 1536)
        self.assertNotIn('O4 "', out)
        self.assertNotIn('\ufffd', out)
        self.assertEqual(out.count('\n'), 1)

    def test_cap_does_not_change_compass_or_reminder(self):
        compass = self.file.with_name('compass.md')
        compass.write_text('- V1 Keep vendor capability.\n')
        old = self.hook()
        self.file.write_text(REGISTER)
        new = self.hook()
        self.assertEqual(old.split(' Now ')[0], new.split(' Open items (')[0])
        self.assertLessEqual(len(self.block(new).encode()), 1536)

    def test_unicode_preview_is_dropped_whole_when_byte_budget_is_full(self):
        self.file.write_text('## Open — Quests\n' + ''.join(
            '- O%d | Q | first 00:0%d | %s\n' % (n, n, '𐐀' * 500) for n in range(1, 5)))
        out = self.hook('o')
        self.assertIn('4 Open; 4 Quests', out)
        self.assertIn('O1 "', out)
        self.assertNotIn('O3 "', out)
        self.assertLessEqual(len(self.block(out).encode()), 1536)
        self.assertNotIn('\ufffd', out)

    def test_invalid_duplicate_broken_and_huge_files_warn_once_without_losing_reminder(self):
        for raw in [b'not a register', b'## Open\n- broken\n',
                    b'## Open\n- O1 | Q | now | one\n- O1 | R | now | two\n',
                    b'## Open\n- O01 | Q | now | one\n', b'## Open\n\xff', b'x' * (128 * 1024 + 1)]:
            with self.subTest(raw=raw[:25]):
                self.file.write_bytes(raw)
                out = self.hook()
                self.assertIn('Reply shape', out)
                self.assertEqual(out.count('Open items unavailable'), 1)
                self.assertNotIn(' Open;', out)
                self.assertLess(len(out.encode()), 720)

    def test_directory_pipe_and_symlink_do_not_hang_or_expose_target(self):
        self.file.mkdir()
        self.assertIn('Open items unavailable', self.hook())
        self.file.rmdir()
        os.mkfifo(self.file)
        self.assertIn('Open items unavailable', self.hook())
        self.file.unlink()
        outside = self.home / 'outside'; outside.write_text(REGISTER)
        self.file.symlink_to(outside)
        self.assertIn('Open items unavailable', self.hook())
        self.assertNotIn('Appro', self.hook())

    def test_symlinked_preference_directory_is_refused(self):
        folder = self.file.parent
        folder.rmdir()
        outside = self.home / 'outside'; outside.mkdir(); (outside / 'open-items.md').write_text(REGISTER)
        folder.symlink_to(outside, target_is_directory=True)
        self.assertIn('Open items unavailable', self.hook())

    def test_empty_open_is_zero_not_absent_or_broken(self):
        self.file.write_text('## Open — Quests\n\n## Closed\n')
        out = self.hook()
        self.assertIn('0 Open; 0 Quests, 0 Risks, 0 Ideas, 0 DeepQuests', out)
        self.assertNotIn('unavailable', out)

    def test_search_from_child_stops_at_git_root_and_prefers_nearer_file(self):
        self.file.write_text(REGISTER)
        child = self.project / 'src'; child.mkdir()
        self.assertIn('5 Open;', self.hook(cwd=child))
        near = child / RELATIVE; near.parent.mkdir(parents=True); near.write_text('## Open\n')
        self.assertIn('0 Open;', self.hook(cwd=child))
        (child / '.git').write_text('gitdir: /elsewhere\n')
        near.unlink()
        self.assertNotIn('Open items (', self.hook(cwd=child))

    def test_mode_off_suppresses_open_items(self):
        self.file.write_text(REGISTER)
        self.hook('stop ste mode')
        self.assertEqual(self.hook(), '')
        self.assertEqual(self.hook(host='codex', IHAV_ASD_STE100='off'), '')

    def test_rotation_and_intent_policy_preserve_open_deepquests_and_nonconsent(self):
        self.file.write_text(REGISTER)
        policy = (ROOT / 'skills/ihav-asd-ste100/references/open-items.md').read_text()
        skill = (ROOT / 'skills/ihav-asd-ste100/SKILL.md').read_text()
        for phrase in ['up to three older Open items', 'oldest and most blocking first',
                       'DeepQuests remain nonblocking and return in rotation', 'Silence is neither yes nor no',
                       'what, why, for whom, when and how', 'quoted words', 'running on <a>']:
            self.assertIn(phrase, policy)
        self.assertNotIn('Do not repeat the same unanswered item', skill)
        self.assertIn('register rules', skill)
        for _ in range(2):
            self.assertIn('1 DeepQuests', self.hook())
        self.assertEqual(self.file.read_text(), REGISTER)


class OpenReplyTests(unittest.TestCase):
    def test_pending_count_and_local_items_with_stable_references_pass_both_profiles(self):
        full = FULL.replace('4. **Pending:**\n', '4. **Pending:**\n' + COUNT)
        full = full.replace('**Q1.** Approve:', '**Q1.** O7: Approve:')
        for profile, text in [('full', full), ('room', re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', full))]:
            report = check(text, profile)
            self.assertTrue(report['ok'], report)
            self.assertFalse(any('Open items' in warning for warning in report['warnings']), report)

    def test_stable_o_keys_work_in_all_four_kinds_without_resetting(self):
        full = room_leader().replace('**Q1.**', '**O7.**').replace('**R1.**', '**O12.**').replace('**I1.**', '**O13.**').replace('**D1.**', '**O14.**')
        for profile in ['full', 'room']:
            report = check(full, profile)
            self.assertTrue(report['ok'], report)
            self.assertEqual((report['stats']['questions'], report['stats']['deepquests']), (1, 1))

    def test_bad_count_sum_wrong_section_and_duplicate_count_fail(self):
        for text in [FULL.replace('4. **Pending:**\n', '4. **Pending:**\n' + COUNT.replace('5 earlier', '6 earlier')),
                     FULL.replace('1. **Done:**\n', '1. **Done:**\n' + COUNT),
                     FULL.replace('4. **Pending:**\n', '4. **Pending:**\n' + COUNT * 2)]:
            for profile in ['full', 'room']:
                self.assertFalse(check(text, profile)['ok'], check(text, profile))

    def test_o_output_accepts_only_open_rows_without_closed_history(self):
        open_part = REGISTER[REGISTER.index('## Open'):REGISTER.index('## Closed')]
        for profile in ['full', 'room']:
            report = check(open_part, profile)
            self.assertTrue(report['ok'], report)
            self.assertEqual(report['stats']['open_items'], 5)
            self.assertFalse(check(open_part + '## Closed\n', profile)['ok'])
            self.assertFalse(check(open_part + '- O7 | Q | now | duplicate\n', profile)['ok'])
            self.assertTrue(check('No open items.', profile)['ok'])

    def test_local_numbers_still_restart_and_deepquest_cap_and_choices_remain(self):
        self.assertFalse(check(FULL.replace('**Q1.**', '**Q7.**'))['ok'])
        four = ''.join(ITEM.replace('**D1.**', '**O%d.**' % n) for n in range(10, 14))
        self.assertFalse(check(FULL + four)['ok'])
        self.assertFalse(check(FULL + ITEM.replace('**D1.**', '**O14.**').split('     -')[0])['ok'])

    def test_stable_ids_are_positive_ascii_without_leading_zero(self):
        for key in ['O0', 'O07', 'O７']:
            for profile in ['full', 'room']:
                reply = room_leader().replace('**Q1.**', '**%s.**' % key)
                self.assertFalse(check(reply, profile)['ok'], check(reply, profile))


if __name__ == '__main__':
    unittest.main()
