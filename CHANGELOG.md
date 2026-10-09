# Changelog

## Unreleased
One reply wording for this plugin and for Agent Room (branch `reply-sync`). No version is set yet.
- X Compass lines may carry the assistant's confidence: `- **V1.** [~95%] text`. The admin's compass files read `- V1 [~95%] text` (active) and `- V4? [~50%] text` (proposed); the hook already printed them as written. The checker accepts the percent in the X section and in the reply to `x`, fails one over 100 or in another form, and keeps lines without a percent valid. `scripts/check_compass.py` no longer counts the percent as a word and warns about one over 100.
- Evidence marks: write `(inferred)` or `(not checked)` after a fact you did not verify, and name the source for the rest; there is no `(checked)`. The checker warns about `(checked)`, `(verified)`, `(unverified)`, `(unchecked)` and `(not verified)` outside code.
- Pending items open with `Waiting on <who or what>:`, as the bold key or right after it. The checker warns, and does not fail, about one that does not.
- The first Agents-Zone line is `- guess => the user's why and final aim` (up to 12 words, no time), and a real ambiguity asks one short question only when a wrong guess costs much. The prompt reminder says the same; its test limit rises from 520 to 570 bytes. The checker warns when the guess line is missing or longer than 12 words.
- `python3 scripts/check_reply.py POST.txt --profile room` checks a post of Agent Room: the same three zones, with no clock, only the sections Todos, Pending and Quests (each only with items), a status word allowed at the start of the Conclusion, at most 5 lines per zone, one `<a>` per question, and the `- guess =>` first line required. A post without zone labels passes. `examples/room-report-samples.json` is a byte-equal copy of the samples file in ihav-agent-room-ui; `tests/test_room_samples.py` runs it, and the two copies must have equal sha256 hashes.
- `SKILL.md` stays at 7,790 bytes (7,793 before): about 180 bytes of text that the template or the checker already said were cut to pay for the new rules.
- Not in this change: Conclusion first by default, Done as work since the last turn, length limits for bullets and questions (they need the admin's own session data), and `wip/0.20.0-compact`.

## 0.20.0 — 2026-10-09
New optional section `X. **Compass:**`, chosen by the admin of the first user project. A project without a Compass file sees no change in the hook output or in the reply shape.
- A project keeps its core views, from code style to what the app is for, in `<project>/.ihav_space/ihav-asd-ste100/compass.md`. `- V1 text` is an active line and `- V1? text` is a proposed line; the ID is one letter and digits and never changes. Common groups: V Vision, A Architecture, W Work habits, C Code, S Style. A line has at most 15 words. Headings and blank lines are ignored. Only the admin edits the file.
- The hook looks for the file from the hook input's `cwd` up to the git root; the first file wins. SessionStart and every prompt add the active lines, not the proposed ones, to the context. The caps are 60 lines and 4 KB (400 characters a line, 128 KB read); the reminder says how many lines were cut. An unreadable or odd file never removes the rest of the reminder. Codex uses the same core. Cost: nothing without a file; with one, about 17 tokens per active line and 90 tokens of intro and rule text on every prompt.
- The reply: `X. **Compass:**` comes first in the list, above Goals, with at most 5 lines that this reply touches (`- **V1.** text`) and, when more exist, `- **More:** N other lines; type `x` to see all.` A step, plan or request that conflicts with a line adds `- **X!** V1: what, why; choose in Quests.` and the choice goes to Quests; with no conflict nothing is written. Small and exact-output replies get no X.
- `x` or `compass` asks for the Compass alone: all active lines under a bold label per group, then the proposed lines marked `(proposed, not enforced)`. For that prompt only, the hook adds the proposed lines to the context. `node scripts/install-x.mjs` installs a personal `/x` skill the way `install-az.mjs` installs `/az`; both now share `scripts/install-skill.mjs`.
- The checker accepts a reply with an X section and a Compass-alone reply. It fails an X section that is not first, has more than 5 compass lines, has a `More` item without its count or not last, or has an `X!` item without a line ID or without a choice in Quests. Replies without X pass as before.
- `scripts/check_compass.py FILE` lints a Compass file: it warns about a line over 15 words, a repeated ID, a bullet the parser would ignore and a file the hook would cut. Warnings never fail.
- The skill size limit rises from 7,100 to 7,800 bytes, about 175 more tokens per session start in every project, with or without a Compass file.

## 0.19.4 — 2026-10-08
- Codex keeps the prompt reminder. The UserPromptSubmit hook now prints its text as `hookSpecificOutput` JSON. Codex 0.160 read the old plain line, which starts with `[`, as broken JSON and dropped it. Claude Code accepts both forms.
- `scripts/activate.mjs` requires that JSON in its smoke run before it moves the pointer. `--rollback` can still return to a release that prints the old plain line; it then warns on stderr that Codex loses the reminder.
- A `PLUGIN_ROOT` inherited from another plugin, for example when ihav-agent-room starts a Claude worker from Codex, no longer moves a Claude session to Codex state. The hook reads the plugin name from `plugin.json` or from the plugin cache path.
- The skill states the 35-word Conclusion limit that the checker already enforces. CONTRIBUTING now gives the same 7,100-byte skill budget as the tests.
- `tests/test_prompt_output_contract.py` runs the shipped launcher as Claude Code and as Codex and requires valid JSON with `hookSpecificOutput`.

## 0.19.3 — 2026-10-04
- The checker allows a Conclusion line of up to 35 words, up from 25. An audit of every room found replies of 26 to 56 words, and the first user chose 35.
- The prompt reminder now shows the L layout, `**L1.** [~N%] [bar] | aim`, and says that G and B lines are plain. One audited room still drew bars on G lines after receiving the new rules. The reminder limit in the tests rises from 480 to 520 bytes.
- `scripts/audit_sessions.py` checks the last full-format reply of every Claude Code session active in a time window (default 120 minutes) with the checker, and prints a table or JSON. It only reads `~/.claude/projects/*/*.jsonl`.

## 0.19.2 — 2026-10-04
- A proposed L line lives only in Quests, as plain text with no percent or bar. The checker already fails an L line in Goals that lacks `[~N%] [bar] |`.
- `bridge.mjs --ensure-missing` covers every release from 0.12.0 named in the release's `CHANGELOG.md`, so a deleted launcher folder such as 0.18.0 comes back as a forwarder too.
- `activate.mjs` runs `bridge.mjs --ensure-missing` after each activation and reports the folders it created. A failure there never undoes the activation.
- The Result-Zone rule on long lists is shorter; it keeps the same meaning.

## 0.19.1 — 2026-10-04
- `scripts/bridge.mjs` brings open sessions on releases before 0.18.0 to the active release without `/reload-plugins`. `--apply DIR` or `--apply-all` replaces an old `hooks/ste-mode.mjs` with a small forwarder and keeps the original as `ste-mode.orig.mjs` and in `~/.ihav/backups/ihav-asd-ste100/`. `--ensure DIR` and `--ensure-missing` recreate deleted release folders (0.12.0 to 0.17.0) with only the forwarder. `--restore DIR` and `--restore-all` undo both. The forwarder runs the active release only when the pointer passes the same checks as the launcher, and falls back to the original hook or stays silent. Written by CODEX_01, reviewed by CLAUDE_01.

## 0.19.0 — 2026-10-04
- Goals always has an L line. Only the user sets L aims; with none, the agent proposes one in Quests. A finished aim stays at `[~100%] [##########]` instead of disappearing. The checker warns, and does not fail, when Goals has no L line.
- `az` is a short form of `adminzone`: the Admin-Zone alone. A reply that has a Quest always ends with the Admin-Zone, so a decision never hides in a short answer.
- `node scripts/install-az.mjs` installs a personal `/az` skill in `<config dir>/skills/az/`. The file carries an ownership marker; the script never overwrites or removes an `az` skill it did not write. `--remove` deletes only its own file.
- A session that an old release started, and that the bridge forwarder runs (`IHAV_STE100_BRIDGED=1`), gets the current rules once at its next prompt.
- The skill stays under 7,100 bytes: the intro, the conclusion-first rule and the summary line are shorter.

## 0.18.0 — 2026-10-04
New releases reach open Claude Code sessions without `/reload-plugins`. The reply rules do not change.
- `hooks/ste-mode.mjs` is now a stable launcher, and the hook logic moves to `hooks/ste-core.mjs`. The launcher runs the release named in `$IHAV_HOME/active/ihav-asd-ste100.json` (default `~/.ihav`), the same pointer format that ihav-agent-room uses. It runs that release only when the pointer is a regular file owned by the user, is not writable by group or others, has `launcher_protocol` 1, and names a root inside `<config dir>/plugins/cache/ihav/ihav-asd-ste100/` whose real path holds `hooks/ste-core.mjs`. Any failed check or a broken release falls back to the launcher's own copy.
- When a session's active version changes, its next prompt receives the new skill body once, marked "STE REPLY RULES UPDATED".
- `scripts/activate.mjs` smoke-runs a release in a throwaway config directory, then writes the pointer atomically with the previous release. `--rollback` and `--status` are supported.
- `hooks/hooks.json` does not change. Claude Code's `reloadSkills` hook field is not used: its documentation covers SessionStart skill discovery only, and these rules arrive through hook context, not the skill loader.
- Limit: sessions still running 0.17.0 or older have no launcher, so this release itself needs one last `/reload-plugins` or a new session.

## 0.17.0 — 2026-10-04
**Breaking for Goals:** the progress bar moves from G lines to L lines, chosen by the first user.
- An L line opens with the agent's estimate and a ten-character bar, then a pipe and the aim: `**L1.** [~80%] [########--] | aim`. The `~` marks the percent as an estimate; the bar has one `#` per 10 percent. These are the only square brackets the rules allow.
- G and B lines are plain text, with no bar, step count, percent or `-> L` link.
- Agents-Zone lines are short: about 12 words, with only the result or the proving ID; details go to the Result-Zone. The checker warns above 16 words and counts a code span as one word.
- The checker checks the L layout and that the bar matches the percent. It cannot check that the estimate is right.

## 0.16.0 — 2026-10-04
- Q, R and I items restart at 1 in every reply, so a short answer such as `Q1.a` always means the latest reply. L, G and B lines keep stable IDs while the goal exists. The checker fails a decision list that does not run 1, 2, 3 in order, such as `Q50` or `Q1`, `Q3`. Reported in the `ihav-web-visit-counter` room, where the numbers had grown to `Q50` and `R30`.

## 0.15.0 — 2026-10-04
**Breaking:** a new eight-section list with Goals first, chosen by the first user. Replies in the old shape fail the checker.

| No. | Before | Now |
| --- | --- | --- |
| 0 | Done | Goals (new) |
| 1 | InProgress | Done |
| 2 | Pending | Doing (was InProgress) |
| 3 | Questions | Todos |
| 4 | Todos | Pending |
| 5 | Backlog | Quests (was Questions) |
| 6 | Risks | Risks |
| 7 | AIIdeas | Ideas (was AIIdeas) |

- Goals lists **L** lines, then **G** lines, then **B** lines. L lines are long-term aims that only the user sets; they carry no percent. A G line is a current goal. It names the L it serves (`-> L1`) when an L exists, and ends with a 10-character ASCII bar and a count, such as `` `#######---` 2/3 ``, with `round(10 * done / total)` marks over the agent's own planned steps, or with "no plan yet". B lines hold deferred work, which was the Backlog section.
- The checker checks the bar arithmetic, `0 < total`, `done <= total`, the `-> Ln` target and the L, G, B order. It cannot check that the step counts are real. A `%` anywhere in an L line fails, and so does text after the count, such as a final period.
- The skill size limit rises from 6,900 to 7,100 bytes, about 50 more tokens per session start. The prompt reminder lists the new sections.

## 0.14.0 — 2026-10-04
- New short form, chosen by the first user: "adminzone" asks for the Admin-Zone alone, with the Conclusion line and all eight sections. The checker accepts a reply that starts with **Admin-Zone** and has no other zone.

## 0.13.0 — 2026-10-04
The checker now enforces three rules that the skill already states. The reply rules do not change.
- The Conclusion line must be one sentence. A Latin stop followed by a capital letter, or a CJK stop followed by more text, starts a new sentence. Abbreviations such as `e.g.`, `i.e.` and `vs.`, versions, file names and inline code after a stop do not.
- Top-level Result-Zone bullets must start with a bold key or a code path. Nested bullets are not checked.
- Square brackets outside code are a violation, including Markdown links. Brackets inside code spans and fences stay allowed.

## 0.12.0 — 2026-10-03
The plugin is renamed from `i-have-asd-ste100` to `ihav-asd-ste100`. The reply rules do not change.
- New repository: https://github.com/hiendang7613/ihav-asd-ste100. The plugin, marketplace, skill folder and Codex names use the new name.
- Breaking for opt-outs: the opt-out file is now `.ihav-asd-ste100-off`, the session markers live in `.ihav-asd-ste100-sessions/`, and the switches are `IHAV_ASD_STE100=off` and `EVAL_IHAV_ASD_STE100=off`. The old file and variables no longer turn the hooks off.
- The checker scans tilde and long backtick fences as code.

## 0.11.0 — 2026-10-03
Three zones, chosen by the first user. The eight sections do not change.
- Each full reply has three zones, each under a bold label line: **Agents-Zone** (every step this turn, one line each: `` - `4:43 PM` why => what ``), **Result-Zone** (key-first bullets) and **Admin-Zone** (the Conclusion line and the eight sections).
- Step times come from a real clock only. In Claude Code, the prompt reminder carries the local time and a new `PostToolBatch` hook adds it after each batch of tool calls, about a dozen tokens per batch. Without a clock reading, a step has no time.
- The checker requires the three labels in order with blank lines around them, checks step lines and their time format, and no longer mistakes a code block in the body for a wrapped conclusion part.
- The skill size limit rises from 6,500 to 6,900 bytes and the reminder limit from 400 to 480 bytes, for the zone rules and the time.

## 0.10.0 — 2026-10-02
- Keep every requested review finding and failure visible; the five-item target applies only to ordinary scan lists. The many-findings eval now checks all nine supplied findings and locations.
- Require ASCII digits and colons in structural markers, three-space section items and five-space options. The checker rejects duplicate Conclusion markers and malformed short replies that attempt the full section format.
- Clarify approval wording, higher-priority output contracts, exact-output replies with explanations, and peer-report attribution.

## 0.9.0 — 2026-10-02
Rule clarifications from the Codex review of 0.8.1; the eight-section format does not change.
- The body opens with the direct answer, action or blocker. The Conclusion gives the overall state and the decisive caveat; it may restate the core result but adds no new fact or evidence list.
- Each item sits in one section only, with a routing rule for every section. Once the user decides, the item moves: accepted to Todos, deferred to Backlog. The checker warns when the same bold key appears in two sections.
- Status words follow the user's language; only the section labels and the Q, R, I and `<a>` markers stay fixed.
- Harness and project rules on tools, safety and permissions outrank the skill; only a format the user or project asks for replaces the shape.
- The pre-send check points back to the shape instead of repeating it, which keeps the skill under its size limit.

## 0.8.1 — 2026-10-02
- README tagline and research notes now say eight sections; no rule change.

## 0.8.0 — 2026-10-02
- Two new sections, chosen by the first user: 6. Risks and 7. AIIdeas. The list is now 0. Done, 1. InProgress, 2. Pending, 3. Questions, 4. Todos, 5. Backlog, 6. Risks, 7. AIIdeas.
- Risks and ideas are numbered **R1.** and **I1.** and end with one choice line, such as `` `<a>` fix it now | (b) skip | (c) later ``, so the reader answers "R1 c" in one line. An empty Risks label means the agent checked and found none.
- Questions now holds approvals, choices and steps only the user can do. Work the agent may do without asking goes to Todos.
- The checker knows the eight sections, the Q, R and I numbering, one-line choices, and that every risk and idea offers a choice.
- The skill drops text that repeated other rules, to stay under its size limit.

## 0.7.1 — 2026-10-02
- The checker reads a reply whose Conclusion line comes first, as the skill allows on request; the six sections still end it. Found by the Codex review.
- The long-body warning no longer asks for a file; it says to trim optional detail and keep every needed fact, as the skill says.

## 0.7.0 — 2026-10-02
- New section order, chosen by the first user: 0. Done, 1. InProgress, 2. Pending, 3. Questions, 4. Todos, 5. Backlog. Work that waits on others now sits next to the work that runs.
- Each item is a sub-item under its label that starts with a bold key (`   - **Login fix:** merged.`). The label line stays bare, so every section reads the same way.
- The checker follows the new order, finds Questions at 3, and rejects text on a label line, an item without a bold key, and a question without `**Q1.**`.
- Examples, README, hero image and the per-prompt reminder use the new shape.

## 0.6.2 — 2026-10-02
- Keep the six section labels in English in every reply language, as specified by the admin's global format.
- Keep empty sections label-only; do not use `None` as a filler.
- The offline checker now rejects translated labels and a `None` placeholder. Vietnamese sentence-length guidance no longer treats spaces as word boundaries.
- Treat reply length and action-count guidance as targets; do not create an unrequested file only to shorten a reply.
- Clarify that the Conclusion follows the body and precedes the status list. The pre-send check now respects one-fact, short-answer and exact-output exceptions.

## 0.6.1 — 2026-10-02
- An empty section shows only its label, with nothing after it (no "None"), as the first user asked. All six sections are still always shown.

## 0.6.0 — 2026-10-02
- All six sections are always shown (None when empty), written as one numbered list from 0 to 5 with no blank lines between sections, as the first user asked.
- One blank line separates the list from the Conclusion line: a list that starts at 0 cannot interrupt a paragraph, so without it item 0 merges into the Conclusion (checked with the GitHub Markdown API).
- The checker requires all six sections, the blank line after the Conclusion and no blank lines inside the list.

## 0.5.1 — 2026-10-02
- 1.InProgress and 3.Todos are always shown, with None when empty, so a reader always sees whether anything runs or comes next (requested by the first user). Other empty sections are still left out; the checker enforces both rules.

## 0.5.0 — 2026-10-02
- Six sections, as chosen by the first user: 0.Done, 1.InProgress, 2.Questions, 3.Todos, 4.Pending, 5.Backlog.
- 3.Todos holds the work of the current task the agent does next, in order; 5.Backlog now holds only work deferred to later or optional. 4 is always Pending.

## 0.4.1 — 2026-10-02
- Sections start their own line with the number first (`**0.Done:**`), not as list items, with one blank line between sections. Without the blank line, Markdown merges a section into the list above it (checked with the GitHub Markdown API); the checker now reports that case.

## 0.4.0 — 2026-10-02
- New closing shape, designed with the first user: a one-sentence **Conclusion:** line, then numbered sections in a fixed order: 0.Done, 1.InProgress, 2.Questions, 3.Pending, 4.Backlog. Empty sections are left out; numbers never move.
- Questions hold everything that needs the user, including approvals ("Approve: ..."). The recommended option is `<a>` in a code span, because a bare `<a>` or `<b>` is an HTML tag that Markdown renderers delete (checked on GitHub); other options are (b), (c).
- No emoji and no square brackets anywhere in a reply; status is written in words. Section numbers replace icons as the same anchor in every language.
- The checker understands the new shape: section order and range, empty sections, exactly one `<a>` per question with options, emoji, square brackets, and replies wrapped in a code block.
- README, hero image, examples in five languages and social preview follow the new shape.

## 0.3.0 — 2026-10-02
- Format layer for fast reading: the five block lines carry fixed icons (🎯 🔑 👉 ❓ 📌) that mean the same in every language; status icons ✅ ❌ ⏳ always come with words; every bullet starts with its key; code spans only for exact strings; a bold budget; tables only for comparisons; no headings in normal replies.
- The block lines are list items, so Markdown renderers never merge them into one paragraph.
- All icons are single wide code points without variation selectors, so terminal columns stay aligned; a test enforces it.
- "no icons" removes the icons for a session.
- The checker reads a line's role from its icon in any language, so the order is checked even for unknown labels.
- README redesign: SVG before and after hero, format table, comparison table with measured word and sentence counts, FAQ; new social preview.

## 0.2.0 — 2026-10-02
- Language-neutral rules: the labels are written in the user's language; the injected rules name no language and use only ASCII, because a named language pulls replies toward it.
- Sentence length for scripts without spaces is measured in characters; the checker finds the block by structure, knows label sets in ten languages, and splits sentences on CJK punctuation.
- Scope: the block goes only in the final message of a turn and only in text a person reads, never in agent messages, commits or files.
- Errors: state the cause only when checked; otherwise "cause not known" plus the check that would find it.
- Abbreviations are spelled out at first use; no telegraphic style; the five-item cap applies to lists the reader must act on.
- "stop ste mode" now works anywhere in a prompt, except inside quotes or code; the per-session state moved from the temp directory to the Claude config directory.
- Examples in Chinese, Japanese and Spanish; README with a direct comparison to i-have-adhd.

## 0.1.1 — 2026-10-02
- On by default after install: the SessionStart hook injects the rules and a one-line reminder is added to each prompt.
- Opt out everywhere with `.i-have-asd-ste100-off` in `~/.claude` or `$CODEX_HOME`, or per process with `I_HAVE_ASD_STE100=off`.

## 0.1.0 — 2026-10-02
- First version: skill, opt-in hooks, offline reply checker, ten eval cases, Claude Code and Codex manifests.
