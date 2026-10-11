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

## Open items (per project)

The agent records unanswered Quests, Risks, Ideas and DeepQuests in `<project>/.ihav_space/ihav-asd-ste100/open-items.md`. Stable O IDs survive reply numbering; `o` shows only Open, and `o7.a` or words answer an item. The hook reads this file; it does not create, resolve or rewrite it. The same cwd-to-git-root lookup applies as for Compass. Worktrees need their own register.
Missing files add no hook context. Malformed, symlinked, nonregular or over-128-KiB files add at most one warning. The preview is capped independently at 1,536 bytes and is not a complete list. See [register rules](skills/ihav-asd-ste100/references/open-items.md). Actual model persistence and compliance need a separate native check.

## Goals (per project)

Keep confirmed long-term aims, current goals and deferred work in `<project>/.ihav_space/ihav-asd-ste100/goals.md`. Every Admin-Zone lists all L rows, not only goals touched this turn; `g` returns Goals alone. Only the user sets, changes or retires L goals. See [Goals rules](skills/ihav-asd-ste100/references/goals.md) for estimates, basis, last movement and three-day stalls.
The same cwd-to-git-root lookup and per-worktree ownership apply. The hook reads only; a missing file adds nothing. Unsafe, malformed, nonregular, linked or over-128-KiB files produce at most one warning. The separate Goals block is capped at 2,048 bytes; it is not the full register. The hook definition and launcher are unchanged, so both hosts follow the same core after the existing update procedure. Native trust/reload and model behavior remain unverified offline.

## Updating
Run from the release checkout; these commands target existing `ihav-asd-ste100@ihav` installs, not other marketplaces.
```bash
node scripts/activate.mjs --prepare-marketplace "$HOME/.ihav/local-ste100-0.23.0"
codex -c "marketplaces.ihav={source_type=\"local\",source=\"$HOME/.ihav/local-ste100-0.23.0\"}" plugin add ihav-asd-ste100@ihav
node scripts/activate.mjs --all-hosts
```
The Codex command bootstraps an old launcher without replacing the configured marketplace. Later releases need only `--all-hosts`.
The last command copies this release into both installed host caches, smoke-checks each host, then changes one shared pointer. Missing hosts stay uninstalled.
Claude Code uses the same last command; its existing launcher follows the pointer. For a native local registry update, run `claude plugin marketplace add "$HOME/.ihav/local-ste100-0.23.0"`, then `claude plugin update ihav-asd-ste100@ihav`; restore its original catalogue with `claude plugin marketplace add <original-source>` afterward, since the temporary catalogue lists only this plugin.
Manual: in Codex, run `/hooks`, review and trust if requested, then restart or resume the session. Native trust and running-session reload were not tested offline.
An old launcher accepts the same-host root; an old other-host launcher falls back to its own release until the native bootstrap. Native Codex updates can delete old cache folders.
Rollback: `node scripts/activate.mjs --all-hosts --rollback`. It needs the retained previous release and changes active rules, not native registry versions; 0.19.3 restores legacy text and warns that Codex loses prompt context.
Copies use no symlinks. Existing same-version folders are kept as `.before-*` backups; the pointer retains its previous version. The catalogue destination must be new.

## Uninstall

```bash
claude plugin uninstall ihav-asd-ste100
node <plugin folder>/scripts/install-x.mjs --remove   # only if you installed /x
rm -f ~/.claude/.ihav-asd-ste100-off ~/.codex/.ihav-asd-ste100-off
```
