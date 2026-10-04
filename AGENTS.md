# Agent guide

Map for agents working on this repository. The behavior lives in `skills/ihav-asd-ste100/SKILL.md`; this file does not replace it.

| Area | Location | Purpose |
| --- | --- | --- |
| Canonical rules | `skills/ihav-asd-ste100/SKILL.md` | The only source of truth for the reply rules. Change it first. |
| Claude Code | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin and local marketplace manifests. |
| Codex | `.codex-plugin/plugin.json` | Codex manifest; skills from `./skills/`. |
| Hooks | `hooks/hooks.json`, `hooks/ste-mode.mjs` | On by default after install (opt-out file or `IHAV_ASD_STE100=off`): SessionStart injects the skill; UserPromptSubmit adds a one-line reminder with the local time and handles "stop ste mode" / "ste mode"; PostToolBatch (Claude Code) adds the local time after each batch of tool calls, for the Agents-Zone step times. |
| Offline checker | `scripts/check_reply.py` | Counts shape, line and sentence length, openers and closers. No model call. |
| Evals | `evals/` (local only, not in the repository) | Suite for `claude plugin eval`. Running it calls paid models. |
| Examples | `examples/` | Before and after replies used by the README and the tests. |
| Licences | `LICENSE`, `licenses/` | MIT, plus the i-have-adhd notice and the ASD-STE100 non-affiliation note. |
| References | `ref_repos/` | Upstream repositories for reading only. Ignored by Git and never shipped. |

## Rules for changes

- Keep `SKILL.md` under 7,100 bytes: the SessionStart hook injects it into every session.
- Keep versions equal in both manifests.
- Never add ASD-STE100 specification text or its dictionary. Paraphrase principles only.
- Never create or delete the opt-out file in a real home directory as part of a change or a test.

## Verification

```bash
python3 -m unittest discover -s tests -v      # offline: hooks, manifests, skill, checker, eval files
claude plugin validate --strict .              # offline, no model call
```

`claude plugin eval .` runs the eval suite against real models and costs money. Run it only with the owner's approval,
for example: `claude plugin eval . --model haiku --runs 1 --max-cost-usd 2 --no-publish`.
