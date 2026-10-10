# Agent guide

Map for agents working on this repository. The behavior lives in `skills/ihav-asd-ste100/SKILL.md`; this file does not replace it.

| Area | Location | Purpose |
| --- | --- | --- |
| Canonical rules | `skills/ihav-asd-ste100/SKILL.md` | The only source of truth for the reply rules. Change it first. |
| Claude Code | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin and local marketplace manifests. |
| Codex | `.codex-plugin/plugin.json` | Codex manifest; skills from `./skills/`. |
| Hooks | `hooks/hooks.json`, `hooks/ste-mode.mjs` (stable launcher), `hooks/ste-core.mjs`, `hooks/active.mjs`, `scripts/activate.mjs` | The launcher uses the checked root in `~/.ihav/active/ihav-asd-ste100.json`, or that version inside its own host cache when the root belongs to another host, else its own copy. `--all-hosts` copies to installed ihav caches; [Updating](INSTALL.md#updating) covers the first native bootstrap. Keep `hooks.json` and the launcher stable. On by default after install (opt-out file or `IHAV_ASD_STE100=off`): SessionStart injects the skill; UserPromptSubmit adds a one-line reminder with the local time and handles "stop ste mode" / "ste mode"; PostToolBatch (Claude Code) adds the local time after each batch of tool calls, for the Agents-Zone step times. A project Compass file (`.ihav_space/ihav-asd-ste100/compass.md`, found from the hook input's `cwd` up to the git root) adds its active lines to SessionStart and every prompt; no file, no change. |
| Offline checker | `scripts/check_reply.py`, `scripts/check_compass.py` | Counts shape (including the optional `X. **Compass:**` section and the Compass-alone reply), line and sentence length, openers and closers; lints a Compass file. No model call. |
| Personal skills | `scripts/install-az.mjs`, `scripts/install-x.mjs`, `scripts/install-skill.mjs` | Install or remove the `/az` and `/x` skills; never overwrite a foreign skill. |
| Evals | `evals/` (local only, not in the repository) | Suite for `claude plugin eval`. Running it calls paid models. |
| Examples | `examples/` | Before and after replies used by the README and the tests. |
| Licences | `LICENSE`, `licenses/` | MIT, plus the i-have-adhd notice and the ASD-STE100 non-affiliation note. |
| References | `ref_repos/` | Upstream repositories for reading only. Ignored by Git and never shipped. |

## Rules for changes

- Keep `SKILL.md` under 7,800 bytes: the SessionStart hook injects it into every session.
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
