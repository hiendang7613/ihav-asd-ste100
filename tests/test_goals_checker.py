import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_reply import check  # noqa: E402
from test_check_reply import FULL  # noqa: E402

REGISTER = '''# Goals
## L — long-term aims
- L1 | ~80% (was 75) | Login works. | basis: offline tests | moved: 2026-10-11
- L19 | ~5% | Understand the owner. | set by the admin; basis: source review | moved: 2026-10-11
## L20-L25 — improvement tracks
- L25 | ~64% | Customer success. | next: observe ten tasks | moved: not since 2026-10-10
## G — current goals
- G1 Fix login.
## B — deferred
- B1 Update the guide.
'''
L19 = '   - **L19.** [~5%] [#---------] | Understand the owner.\n'
L25 = '   - **L25.** [~64%] [######----] | Customer success.\n'
COMPLETE = FULL.replace('   - **G1.**', L19 + L25 + '   - **G1.**', 1)
GOALS_ALONE = COMPLETE[COMPLETE.index('0. **Goals:**'):COMPLETE.index('1. **Done:**')]


class GoalsCheckerTests(unittest.TestCase):
    def setUp(self):
        evidence = ROOT / '.evidence/w00-21/goals-checker'
        evidence.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=evidence)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.register = self.directory / 'goals.md'
        self.register.write_text(REGISTER)

    def checked(self, reply=COMPLETE, profile='full', register=None):
        return check(reply, profile, goals_register=register or self.register)

    def assertMissing(self, report, *ids):
        self.assertFalse(report['ok'], report)
        self.assertEqual(report['stats']['missing_goal_ids'], list(ids), report)
        self.assertTrue(any('Goals register ids missing from section 0' in message
                            for message in report['violations']), report)

    def test_complete_admin_report_includes_ids_above_l18(self):
        report = self.checked()
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['stats']['goals_register_ids'], ['L1', 'L19', 'L25'])
        self.assertEqual(report['stats']['missing_goal_ids'], [])

    def test_missing_registered_goal_fails(self):
        self.assertMissing(self.checked(COMPLETE.replace(L25, '')), 'L25')

    def test_id_elsewhere_is_not_a_goals_line(self):
        reply = COMPLETE.replace(L25, '').replace('   - **Login fix:** merged.',
                                                  '   - **Login fix:** L25 is still open.')
        self.assertMissing(self.checked(reply), 'L25')

    def test_inline_fenced_and_quoted_goals_cannot_spoof_completeness(self):
        for example in ['`' + L25.strip() + '`',
                        '``' + L25.strip() + '``',
                        '```md\n' + L25 + '```',
                        '~~~md\n' + L25 + '~~~',
                        '"' + L25.strip() + '"',
                        '"Example:\n' + L25 + '"']:
            with self.subTest(example=example):
                reply = COMPLETE.replace(L25, '').replace('**Result-Zone**\n',
                                                           '**Result-Zone**\n\n' + example + '\n\n')
                self.assertMissing(self.checked(reply), 'L25')

    def test_fenced_fake_admin_is_exempt(self):
        report = self.checked('```md\n**Admin-Zone**\n0. **Goals:**\n' + L25 + '```')
        self.assertTrue(report['stats']['goals_register_exempt'], report)
        self.assertNotIn('missing_goal_ids', report['stats'])

    def test_inline_fake_admin_is_exempt(self):
        for profile in ['full', 'room']:
            report = self.checked('Example: `**Admin-Zone** 0. **Goals:**`.', profile)
            self.assertTrue(report['stats']['goals_register_exempt'], report)
            self.assertNotIn('missing_goal_ids', report['stats'])

    def test_goals_literal_inside_admin_cannot_count(self):
        for wrapped in ['   - **G2.** `' + L25.strip() + '`\n',
                        '   - **G2.** "' + L25.strip() + '"\n',
                        '   - **G2.** "example:\n' + L25 + '"\n']:
            with self.subTest(wrapped=wrapped):
                reply = COMPLETE.replace(L25, '').replace('   - **B1.**', wrapped + '   - **B1.**')
                self.assertMissing(self.checked(reply), 'L25')

    def test_nested_goal_key_is_not_a_section_zero_line(self):
        self.assertMissing(self.checked(COMPLETE.replace(L25, '  ' + L25)), 'L25')

    def test_extra_proposed_goal_warns_without_weakening_completeness(self):
        extra = '   - **L26.** [~0%] [----------] | A new aim (proposed).\n'
        report = self.checked(COMPLETE.replace('   - **G1.**', extra + '   - **G1.**'))
        self.assertTrue(report['ok'], report)
        self.assertTrue(any('not in the register: L26' in warning for warning in report['warnings']), report)
        self.assertMissing(self.checked(FULL.replace('   - **G1.**', extra + '   - **G1.**')), 'L19', 'L25')

    def test_duplicate_registered_id_fails(self):
        report = self.checked(COMPLETE.replace(L19, L19 + L19))
        self.assertFalse(report['ok'], report)
        self.assertTrue(any('Repeated L ids in section 0: L19' in v for v in report['violations']), report)

    def test_admin_only_form_uses_same_completeness(self):
        admin = COMPLETE[COMPLETE.index('**Admin-Zone**'):]
        self.assertTrue(self.checked(admin)['ok'], self.checked(admin))
        self.assertMissing(self.checked(admin.replace(L19, '')), 'L19')

    def test_room_raw_and_folded_full_leader_forms_use_same_completeness(self):
        raw = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE)
        for reply in [raw, ' '.join(raw.split())]:
            with self.subTest(reply=reply[:60]):
                report = self.checked(reply, 'room')
                self.assertTrue(report['ok'], report)
                self.assertEqual(report['stats']['missing_goal_ids'], [])
        missing = ' '.join(raw.replace(L25, '').split())
        self.assertMissing(self.checked(missing, 'room'), 'L25')

    def test_room_single_quoted_goal_literals_do_not_count(self):
        quoted = " ' copied - **L19.** [~5%] [#---------] | Understand the owner. '"
        missing = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE.replace(L19, ''))
        for old in ['Users can log in from every client.', 'Fix the login test.', 'Update the login guide later.']:
            raw = missing.replace(old, old + quoted)
            for text in [raw, ' '.join(raw.split())]:
                with self.subTest(location=old, folded='\n' not in text):
                    self.assertMissing(self.checked(text, 'room'), 'L19')

    def test_single_quoted_literal_with_a_contraction_cannot_supply_a_goal(self):
        quoted = " ' the owner's copy isn't real - **L19.** [~5%] [#---------] | Understand the owner. '"
        raw = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE.replace(L19, ''))
        raw = raw.replace('Users can log in from every client.', 'Users can log in from every client.' + quoted)
        for text in [raw, ' '.join(raw.split())]:
            with self.subTest(folded='\n' not in text):
                self.assertMissing(self.checked(text, 'room'), 'L19')

    def test_ambiguous_plural_possessive_literal_never_proves_completeness(self):
        quoted = " 'the users' copy - **L19.** [~5%] [#---------] | Understand the owner. '"
        raw = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE.replace(L19, ''))
        raw = raw.replace('Users can log in from every client.', 'Users can log in from every client.' + quoted)
        for text in [raw, ' '.join(raw.split())]:
            with self.subTest(folded='\n' not in text):
                report = self.checked(text, 'room')
                self.assertFalse(report['ok'], report)
                self.assertEqual(report['stats']['goals_register_ids'], ['L1', 'L19', 'L25'])
                self.assertTrue(report['stats']['goals_completeness_unknown'], report)
                self.assertNotIn('missing_goal_ids', report['stats'])
                self.assertNotIn('goal_ids', report['stats'])
                self.assertTrue(any('ambiguous single-quoted text' in v for v in report['violations']), report)

    def test_ambiguous_curly_possessive_literal_never_proves_completeness(self):
        quoted = ' ‘the users’ copy - **L19.** [~5%] [#---------] | Understand the owner. ’'
        raw = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE.replace(L19, ''))
        raw = raw.replace('Users can log in from every client.', 'Users can log in from every client.' + quoted)
        for text in [raw, ' '.join(raw.split())]:
            with self.subTest(folded='\n' not in text):
                report = self.checked(text, 'room')
                self.assertFalse(report['ok'], report)
                self.assertTrue(report['stats']['goals_completeness_unknown'], report)
                self.assertNotIn('goal_ids', report['stats'])
                self.assertNotIn('missing_goal_ids', report['stats'])

    def test_independent_unambiguous_quoted_phrases_preserve_real_goal_rows(self):
        for opening, closing in [("'", "'"), ('‘', '’'), ('“', '”')]:
            raw = COMPLETE.replace('Users can log in from every client.',
                                   'Users can log in: ' + opening + 'first phrase' + closing + '.')
            raw = raw.replace('Understand the owner.', 'Understand ' + opening + 'second phrase' + closing + '.')
            room = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', raw)
            for profile, text in [('full', raw), ('room', room), ('room', ' '.join(room.split()))]:
                with self.subTest(quotes=opening + closing, profile=profile, folded='\n' not in text):
                    report = self.checked(text, profile)
                    self.assertTrue(report['ok'], report)
                    self.assertEqual(report['stats']['goal_ids'], ['L1', 'L19', 'L25'])
                    self.assertNotIn('goals_completeness_unknown', report['stats'])

    def test_ambiguous_quote_without_admin_is_still_exempt(self):
        for profile in ['full', 'room']:
            report = self.checked("The 'users' copy is ready.", profile)
            self.assertTrue(report['ok'], report)
            self.assertTrue(report['stats']['goals_register_exempt'], report)

    def test_ambiguous_prose_outside_goals_does_not_reject_complete_reports(self):
        for old in ['`verifyToken` now reads the `Authorization` header.', 'merged.']:
            raw = COMPLETE.replace(old, "The 'users' copy remains available.")
            room = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', raw)
            for profile, text in [('full', raw), ('room', room), ('room', ' '.join(room.split()))]:
                with self.subTest(location=old, profile=profile, folded='\n' not in text):
                    report = self.checked(text, profile)
                    self.assertTrue(report['ok'], report)
                    self.assertEqual(report['stats']['goal_ids'], ['L1', 'L19', 'L25'])
                    self.assertNotIn('goals_completeness_unknown', report['stats'])

    def test_result_quote_cannot_hide_actual_admin_or_goals_boundaries(self):
        raw = COMPLETE.replace(L25, '').replace('**Result-Zone**\n',
                    "**Result-Zone**\n- **Quote:** The copy begins 'unfinished.\n")
        raw = raw.replace('Users can log in from every client.', "Users can log in: 'first phrase'.")
        room = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', raw)
        for profile, text in [('full', raw), ('room', room), ('room', ' '.join(room.split()))]:
            with self.subTest(profile=profile, folded='\n' not in text):
                report = self.checked(text, profile)
                self.assertMissing(report, 'L25')
                self.assertNotIn('goals_register_exempt', report['stats'])

    def test_room_typographic_quoted_goal_literals_do_not_count(self):
        missing = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', COMPLETE.replace(L19, ''))
        for opening, closing in [('‘', '’'), ('“', '”')]:
            raw = missing.replace('Users can log in from every client.',
                    'Users can log in from every client. ' + opening +
                    ' copied - **L19.** [~5%] [#---------] | Understand the owner. ' + closing)
            for text in [raw, ' '.join(raw.split())]:
                with self.subTest(quotes=opening + closing, folded='\n' not in text):
                    self.assertMissing(self.checked(text, 'room'), 'L19')

    def test_natural_curly_apostrophes_preserve_real_goal_rows(self):
        raw = COMPLETE.replace('Users can log in from every client.', 'Users’ sessions don’t disappear.')
        raw = raw.replace('Understand the owner.', 'The owner’s view remains.')
        raw = raw.replace('Customer success.', 'Customers’ feedback isn’t lost.')
        room = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', raw)
        for profile, text in [('full', raw), ('room', room), ('room', ' '.join(room.split()))]:
            with self.subTest(profile=profile, folded='\n' not in text):
                report = self.checked(text, profile)
                self.assertTrue(report['ok'], report)
                self.assertEqual(report['stats']['goal_ids'], ['L1', 'L19', 'L25'])

    def test_natural_apostrophes_do_not_mask_real_rows(self):
        raw = COMPLETE.replace('Users can log in from every client.', "Users' sessions don't disappear.")
        raw = raw.replace('Understand the owner.', "The owner's view remains.")
        raw = raw.replace('Customer success.', "Customers' feedback isn't lost.")
        room = re.sub(r'`[0-9]+:[0-9]+ (?:AM|PM)` ', '', raw)
        for profile, text in [('full', raw), ('room', room), ('room', ' '.join(room.split()))]:
            with self.subTest(profile=profile, folded='\n' not in text):
                report = self.checked(text, profile)
                self.assertTrue(report['ok'], report)
                self.assertEqual(report['stats']['goal_ids'], ['L1', 'L19', 'L25'])

    def test_compact_room_admin_still_requires_registered_goals_when_flag_given(self):
        compact = ('**Agents-Zone** - guess => keep the room stable '
                   '**Result-Zone** - **State:** stable. '
                   '**Admin-Zone** **Conclusion:** done - The room is stable. '
                   '3. **Todos:** - **Next:** check later.')
        self.assertMissing(self.checked(compact, 'room'), 'L1', 'L19', 'L25')

    def test_no_admin_reply_is_exempt_even_when_explicit_register_is_missing(self):
        missing = self.directory / 'absent.md'
        for profile in ['full', 'room']:
            report = self.checked('Done.', profile, missing)
            self.assertTrue(report['ok'], report)
            self.assertTrue(report['stats']['goals_register_exempt'], report)

    def test_g_returns_canonical_goals_section_alone(self):
        for profile in ['full', 'room']:
            report = self.checked(GOALS_ALONE, profile)
            self.assertTrue(report['ok'], report)
            self.assertTrue(report['stats']['goals_alone'], report)
            self.assertMissing(self.checked(GOALS_ALONE.replace(L25, ''), profile), 'L25')
        self.assertTrue(check(GOALS_ALONE)['ok'], check(GOALS_ALONE))

    def test_g_ignores_leading_blank_lines_consistently(self):
        for prefix in ['\n\n', ' \n\n', '\t\n']:
            for profile in ['full', 'room']:
                with self.subTest(prefix=prefix, profile=profile):
                    report = self.checked(prefix + GOALS_ALONE, profile)
                    self.assertTrue(report['ok'], report)
                    self.assertTrue(report['stats']['goals_alone'], report)
                    self.assertEqual(report['stats']['goal_ids'], ['L1', 'L19', 'L25'])

    def test_goals_alone_keeps_shape_caps_order_and_only_its_own_section(self):
        for bad in [GOALS_ALONE.replace('[~64%] [######----]', '[~64%] [----------]'),
                    GOALS_ALONE.replace('   - **G1.**', '   - Plain goal.'),
                    GOALS_ALONE + '1. **Done:**\n',
                    GOALS_ALONE.replace('   - **L19.**', '     - **L19.**')]:
            with self.subTest(bad=bad[:70]):
                self.assertFalse(check(bad)['ok'], check(bad))

    def test_empty_declared_register_is_distinct_from_unavailable(self):
        self.register.write_text('## L — long-term aims\n## G — current\n')
        report = self.checked('0. **Goals:**\n')
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['stats']['goals_register_ids'], [])
        self.assertEqual(report['stats']['missing_goal_ids'], [])
        self.assertTrue(any('no L line' in w for w in report['warnings']), report)
        self.assertFalse(check('0. **Goals:**\n1. **Done:**\n')['ok'])

    def test_goal_only_literal_spoofing_does_not_count(self):
        for fake in ['   - **G2.** `' + L25.strip() + '`\n',
                     '   - **G2.** "' + L25.strip() + '"\n',
                     '```md\n' + L25 + '```\n']:
            with self.subTest(fake=fake):
                self.assertMissing(self.checked(GOALS_ALONE.replace(L25, '') + fake), 'L25')

    def test_bad_non_numeric_and_non_ascii_rows_are_not_silently_dropped(self):
        for key in ['Lbad', 'L０', 'L0', 'L０１']:
            with self.subTest(key=key):
                self.register.write_text(REGISTER.replace('- L19', '- ' + key))
                self.assertTrue(any('Goals register unavailable' in v for v in self.checked()['violations']))

    def test_explicit_register_missing_broken_duplicate_and_bad_utf8_fail_without_throw(self):
        for content in [None, '# No goals\n', REGISTER.replace('~80%', '~101%'),
                        REGISTER.replace('- L19', '- L019'), REGISTER + REGISTER,
                        b'\xff']:
            with self.subTest(content=content):
                if self.register.exists():
                    self.register.unlink()
                if isinstance(content, bytes):
                    self.register.write_bytes(content)
                elif content is not None:
                    self.register.write_text(content)
                report = self.checked()
                self.assertFalse(report['ok'], report)
                self.assertTrue(any('Goals register unavailable' in v for v in report['violations']), report)

    def test_fenced_register_rows_cannot_supply_goals(self):
        self.register.write_text('```md\n' + REGISTER + '```\n')
        self.assertFalse(self.checked()['ok'])

    def test_link_directory_fifo_and_huge_register_fail_without_blocking(self):
        symlink = self.directory / 'linked.md'
        symlink.symlink_to(self.register)
        huge = self.directory / 'huge.md'
        huge.write_bytes(REGISTER.encode() + b' ' * (128 * 1024))
        paths = [symlink, self.directory, huge]
        if hasattr(os, 'mkfifo'):
            fifo = self.directory / 'goals.fifo'
            os.mkfifo(fifo)
            paths.append(fifo)
        for path in paths:
            with self.subTest(path=path.name):
                report = self.checked(register=path)
                self.assertFalse(report['ok'], report)
                self.assertTrue(any('Goals register unavailable' in v for v in report['violations']), report)

    def test_linked_preference_directory_is_rejected(self):
        target = self.directory / 'real'; target.mkdir()
        (target / 'goals.md').write_text(REGISTER)
        link = self.directory / 'linked'; link.symlink_to(target, target_is_directory=True)
        report = self.checked(register=link / 'goals.md')
        self.assertFalse(report['ok'], report)
        self.assertTrue(any('Goals register unavailable' in v for v in report['violations']), report)

    def test_cli_json_and_stdin_use_explicit_register_without_treating_it_as_reply(self):
        command = [sys.executable, str(ROOT / 'scripts/check_reply.py'), '--goals-register',
                   str(self.register), '-', '--json']
        success = subprocess.run(command, input=COMPLETE, text=True, capture_output=True, timeout=5)
        self.assertEqual(success.returncode, 0, success.stderr or success.stdout)
        self.assertEqual(json.loads(success.stdout)['stats']['goals_register_ids'], ['L1', 'L19', 'L25'])
        failure = subprocess.run(command, input=FULL, text=True, capture_output=True, timeout=5)
        self.assertEqual(failure.returncode, 1, failure.stderr or failure.stdout)
        self.assertMissing(json.loads(failure.stdout), 'L19', 'L25')
        self.assertEqual(failure.stderr, '')

    def test_cli_invalid_register_reports_json_and_missing_option_value_returns_usage(self):
        command = [sys.executable, str(ROOT / 'scripts/check_reply.py'), '-', '--json',
                   '--goals-register', str(self.directory / 'absent.md')]
        failure = subprocess.run(command, input=COMPLETE, text=True, capture_output=True, timeout=5)
        self.assertEqual(failure.returncode, 1, failure.stderr or failure.stdout)
        self.assertFalse(json.loads(failure.stdout)['ok'])
        self.assertEqual(failure.stderr, '')
        for tail in [['--goals-register'], ['--goals-register', '--json']]:
            usage = subprocess.run(command[:3] + tail, input=COMPLETE, text=True,
                                   capture_output=True, timeout=5)
            self.assertEqual(usage.returncode, 2, usage.stderr or usage.stdout)


if __name__ == '__main__':
    unittest.main()
