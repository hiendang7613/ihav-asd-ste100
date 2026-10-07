"""Regression through the shipped launcher against the common host wire contract."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PromptOutputContractTests(unittest.TestCase):
    def test_prompt_context_mode_sequence_on_both_host_environments(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host), tempfile.TemporaryDirectory(prefix='ste-wire-') as fixture:
                fixture_root = Path(fixture)
                env = {'PATH': os.environ['PATH'], 'HOME': str(fixture_root),
                       'IHAV_HOME': str(fixture_root / '.ihav'),
                       'CODEX_HOME': str(fixture_root / '.codex')}
                if host == 'claude':
                    env.update(CLAUDE_CONFIG_DIR=str(fixture_root / '.claude'), CLAUDE_PLUGIN_ROOT=str(ROOT))
                else:
                    env['PLUGIN_ROOT'] = str(ROOT)
                def run(prompt):
                    payload = {'hook_event_name': 'UserPromptSubmit', 'session_id': 'wire-test', 'prompt': prompt}
                    result = subprocess.run(['node', str(ROOT / 'hooks/ste-mode.mjs')], input=json.dumps(payload),
                                            capture_output=True, text=True, env=env, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, '')
                    if not result.stdout:
                        return ''
                    value = json.loads(result.stdout)
                    self.assertNotIn('decision', value)
                    self.assertNotIn('continue', value)
                    specific = value['hookSpecificOutput']
                    self.assertEqual(specific['hookEventName'], 'UserPromptSubmit')
                    self.assertIsInstance(specific['additionalContext'], str)
                    return specific['additionalContext']
                self.assertIn('Reply shape', run('hello'))
                self.assertIn('off for this session', run('stop ste mode'))
                self.assertEqual(run('next'), '')
                self.assertIn('Reply shape', run('ste mode'))
                self.assertIn('Reply shape', run('next'))

if __name__ == '__main__':
    unittest.main()
