# Install

## Claude Code

From GitHub:

```bash
claude plugin marketplace add hiendang7613/ihav-asd-ste100
claude plugin install ihav-asd-ste100@ihav-asd-ste100
```

From a local checkout, pass the directory path instead of `hiendang7613/ihav-asd-ste100`.

Restart Claude Code. From then on every new session uses the rules: the SessionStart hook injects them and a one-line
reminder is added to each prompt. Nothing needs to be turned on. The manual command is `/ihav-asd-ste100:ihav-asd-ste100`.

### Turning it off

```bash
touch ~/.claude/.ihav-asd-ste100-off          # every session (Codex: $CODEX_HOME/.ihav-asd-ste100-off)
IHAV_ASD_STE100=off claude                     # this process only
```

Delete the file or unset the variable to turn it on again. Inside a session, "stop ste mode" anywhere in a prompt
(outside quotes and code), or the exact prompt "normal mode", stops it for that session; "ste mode" starts it again.
The format uses no emoji, so it works in every terminal.

The hooks need Node.js on the PATH. Without Node they do nothing; the manual command still works.

## Codex

```bash
codex plugin marketplace add hiendang7613/ihav-asd-ste100
codex plugin add ihav-asd-ste100@ihav-asd-ste100
```

Codex loads the skill and the plugin hooks from `hooks/hooks.json`. On first install, and after the hook definition changes, run `/hooks`, review the plugin hooks, and trust them. Codex skips plugin hooks until you trust the current definition. Start a new session after trusting the hooks: `SessionStart` loads the reply rules, and `UserPromptSubmit` adds the short reminder with the local time. The per-step clock uses Claude Code's `PostToolBatch` event; in Codex, Agents-Zone steps carry a time only when a clock reading is available. Without hook trust, the skill remains available for manual use.

The commands above use the Codex CLI. The ChatGPT web app does not deploy local hook scripts into its runtime.

## Compass (optional, per project)

A project that wants its core views kept in front of the agent adds one file, `<project>/.ihav_space/ihav-asd-ste100/compass.md`, with lines such as `- V1 text` (active) and `- V1? text` (proposed). The hook finds it from the session's working folder up to the git root. Projects without the file are unchanged. A git worktree needs its own copy (or a committed file), because `.ihav_space/` is not shared between worktrees. Details: [README](README.md#compass).

```bash
node <plugin folder>/scripts/install-x.mjs      # optional: a personal /x command that shows the Compass alone
python3 <plugin folder>/scripts/check_compass.py <project>/.ihav_space/ihav-asd-ste100/compass.md
```

After updating the plugin, run `node <its cache folder>/scripts/activate.mjs` (see the README) so open sessions get the new rules once.

## Uninstall

```bash
claude plugin uninstall ihav-asd-ste100
node <plugin folder>/scripts/install-x.mjs --remove   # only if you installed /x
rm -f ~/.claude/.ihav-asd-ste100-off ~/.codex/.ihav-asd-ste100-off
```
