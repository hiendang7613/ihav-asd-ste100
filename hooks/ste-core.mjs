// ihav-asd-ste100 hook for SessionStart, UserPromptSubmit and PostToolBatch (Claude Code; Codex uses supported common hooks).
//
// On by default once the plugin is installed. Opt out everywhere with the file .ihav-asd-ste100-off in
// $CLAUDE_CONFIG_DIR (default ~/.claude) or $CODEX_HOME (default ~/.codex), or for one process with
// IHAV_ASD_STE100=off (EVAL_IHAV_ASD_STE100=off in `claude plugin eval` cases).
// SessionStart injects the skill body. UserPromptSubmit adds a one-line reminder against style drift,
// "stop ste mode" anywhere outside quotes or code (or the exact prompt "normal mode") turns it off for the session;
// "ste mode" as the whole prompt, or "start ste mode" anywhere, turns it on again. The per-session state lives in
// $CLAUDE_CONFIG_DIR/.ihav-asd-ste100-sessions/ so it survives compaction and resume.
// The model has no clock: the reminder and PostToolBatch give it the local time, so each Agents-Zone step can carry
// a real time. PostToolBatch fires once per batch of tool calls and adds about a dozen tokens of context.
// hooks/ste-mode.mjs is a stable launcher that imports this file from the active release (see that file).
// Compass: when <project>/.ihav_space/ihav-asd-ste100/compass.md exists (searched from the hook input's cwd up to the git
// root, first file wins), SessionStart and UserPromptSubmit also carry its active lines (see compassBlock). No file, no change.
// When the active version differs from the one a session last saw, the next prompt re-injects the skill body once.
// Any failure exits 0 with no output: this hook must never block a session or a prompt.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configDir } from "./active.mjs";
import { OPEN_ITEMS_PATH, openItemsBlock } from "./open-items.mjs";
import { GOALS_PATH, goalsBlock } from "./goals.mjs";

const OFF_FILE = ".ihav-asd-ste100-off";
const OFF_EXACT = new Set(["stop ste mode", "normal mode"]);
const ON_EXACT = new Set(["ste mode", "start ste mode", "ste mode on"]);
const OFF_ANYWHERE = /\bstop ste mode\b/;
const ON_ANYWHERE = /\b(?:start ste mode|ste mode on)\b/;
export const REMINDER =
  "[ihav-asd-ste100] Reply shape: **Agents-Zone** (first `- guess => the user's why and final aim`, then `time` why => what), **Result-Zone** (key-first " +
  "bullets), **Admin-Zone**: **Conclusion:** one sentence, blank line, 0. **Goals:** (`**L1.** [~N%] [bar] | aim`, plain G and B), 1. **Done:**, " +
  "2. **Doing:**, 3. **Todos:**, 4. **Pending:**, 5. **Quests:**, 6. **Risks:**, 7. **Ideas:**, 8. **DeepQuests:**; bold-key sub-items; " +
  '`<a>` = recommended. No emoji/brackets except L progress. "stop ste mode" turns this off.';

const COMPASS_PATH = path.join(".ihav_space", "ihav-asd-ste100", "compass.md");
const COMPASS_READ_MAX = 128 * 1024;  // a larger file is read only this far
const COMPASS_MAX_LINES = 60;
const COMPASS_MAX_BYTES = 4096;
const COMPASS_MAX_LINE = 400;
// "- V1 text" is active, "- V1? text" is proposed. Headings, blank lines and anything else are ignored.
const COMPASS_LINE = /^[-*]\s+([A-Za-z][0-9]+)(\?)?\s+(\S.*)$/;
const COMPASS_ALL = new Set(["x", "compass", "/x", "/compass"]);  // the prompts that ask for the Compass alone
const COMPASS_RULE =
  "Show X. **Compass:** first, above 0. **Goals:**, up to 5 lines this reply touches as `- **ID.** [~N%] text` (copy each percent), then " +
  "``- **More:** N other lines; type `x` to see all.`` if more exist; a conflict with a line adds " +
  "`- **X!** ID: what, why; choose in Quests.` Small or exact-output replies get no X.";

// The first compass file from cwd up to the git root, or "". Without a git root only cwd itself is searched.
function projectFile(cwd, relativePath = COMPASS_PATH) {
  const start = path.resolve(cwd);
  let root = start;
  for (let dir = start, depth = 0; depth < 64; depth++) {
    if (fs.existsSync(path.join(dir, ".git"))) {  // a worktree has .git as a file
      root = dir;
      break;
    }
    if (path.dirname(dir) === dir) break;
    dir = path.dirname(dir);
  }
  for (let dir = start; ; dir = path.dirname(dir)) {
    const file = path.join(dir, relativePath);
    try { fs.lstatSync(file); return file; } catch (error) { if (error.code !== "ENOENT") return file; }
    if (dir === root) return "";
  }
}

// Active and proposed lines of a compass file's text.
export function parseCompass(text) {
  const active = [];
  const proposed = [];
  for (const raw of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    const match = COMPASS_LINE.exec(raw);
    if (!match) continue;
    const clean = match[3].replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().replace(/[.;]+$/, "");
    (match[2] ? proposed : active).push(`${match[1]} ${clean.slice(0, COMPASS_MAX_LINE)}`);
  }
  return { active, proposed };
}

// Joins as many lines as the caps allow. Returns the text and how many lines were left out.
function fit(lines) {
  const shown = [];
  let bytes = 0;
  for (const line of lines) {
    const size = Buffer.byteLength(line) + 2;
    if (shown.length >= COMPASS_MAX_LINES || bytes + size > COMPASS_MAX_BYTES) break;
    shown.push(line);
    bytes += size;
  }
  return { text: shown.join("; "), cut: lines.length - shown.length };
}

// The Compass text for the reminder: the active lines of the project's compass file, and with all=true also the
// proposed ones. Returns "" for no file, an unreadable or huge file, or no lines. Never throws and never reads twice.
function compassBlock(cwd, all) {
  try {
    if (typeof cwd !== "string" || !cwd) return "";
    const file = projectFile(cwd);
    if (!file || !fs.statSync(file).isFile()) return "";
    const fd = fs.openSync(file, "r");
    let text;
    let truncated = false;
    try {
      const size = fs.fstatSync(fd).size;
      const buffer = Buffer.alloc(Math.min(size, COMPASS_READ_MAX));
      text = buffer.toString("utf8", 0, fs.readSync(fd, buffer, 0, buffer.length, 0));
      truncated = size > buffer.length;
    } finally {
      fs.closeSync(fd);
    }
    if (truncated) text = text.slice(0, text.lastIndexOf("\n") + 1);  // drop the partial last line
    const { active, proposed } = parseCompass(text);
    const lines = fit(active);
    const extra = all ? fit(proposed) : { text: "", cut: 0 };
    if (!lines.text && !extra.text) return "";
    const more = (count) => `${count}${truncated ? "+" : ""}`;
    let block = "";
    if (lines.text) {
      block = `Compass (admin's core views, keep every reply consistent with them): ${lines.text}.`;
      if (lines.cut || truncated) block += ` ${more(lines.cut)} more active lines cut (over ${COMPASS_MAX_LINES} lines or 4 KB).`;
    }
    if (extra.text) block += ` Proposed, not enforced (for the x reply only): ${extra.text}.`;
    return `${block} ${COMPASS_RULE}`.trim();
  } catch {
    return "";  // a compass problem must never remove the rest of the reminder
  }
}

// Local wall-clock time as "4:43 PM" (plain ASCII; the Intl formatter can insert a narrow no-break space).
export function clock(now = new Date()) {
  const hour = now.getHours();
  const minute = String(now.getMinutes()).padStart(2, "0");
  return `${hour % 12 || 12}:${minute} ${hour < 12 ? "AM" : "PM"}`;
}

const ENV_SWITCHES = ["IHAV_ASD_STE100", "EVAL_IHAV_ASD_STE100"];

// Returns how to turn the mode off everywhere, or "" when the user already turned it off.
function offSwitch() {
  const env = ENV_SWITCHES.find((name) => String(process.env[name] || "").toLowerCase() === "off");
  if (env) return "";
  const dirs = [
    configDir(),
    process.env.CODEX_HOME || path.join(os.homedir(), ".codex"),
  ];
  if (dirs.some((dir) => fs.existsSync(path.join(dir, OFF_FILE)))) return "";
  return path.join(dirs[0], OFF_FILE);
}

function readInput() {
  if (process.stdin.isTTY) return {};
  const raw = fs.readFileSync(0, "utf8").trim();
  return raw ? JSON.parse(raw) : {};
}

function offMarker(sessionId) {
  const safe = String(sessionId || "default").replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 128) || "default";
  return path.join(configDir(), ".ihav-asd-ste100-sessions", `${safe}.off`);
}

// Text inside code fences, inline code or quotes is quoted material, not a command.
function unquoted(prompt) {
  return prompt
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]*`/g, " ")
    .replace(/"[^\"]*"|“[^”]*”/g, " ")
    .replace(/(?<![\p{L}\p{N}_'])'[^'\r\n]*'(?![\p{L}\p{N}_'])|‘[^’\r\n]*’/gu, " ");
}

const HERE = path.dirname(fileURLToPath(import.meta.url));

// The version of the release this file belongs to.
export function version() {
  try {
    return JSON.parse(fs.readFileSync(path.join(HERE, "..", ".claude-plugin", "plugin.json"), "utf8")).version || "";
  } catch {
    return "";
  }
}

function versionMarker(sessionId) {
  return offMarker(sessionId).replace(/\.off$/, ".version");
}

function remember(sessionId) {
  const marker = versionMarker(sessionId);
  fs.mkdirSync(path.dirname(marker), { recursive: true });
  fs.writeFileSync(marker, `${version()}\n`);
}

function seen(sessionId) {
  try {
    return fs.readFileSync(versionMarker(sessionId), "utf8").trim();
  } catch {
    return "";
  }
}

function skillBody() {
  const file = path.join(HERE, "..", "skills", "ihav-asd-ste100", "SKILL.md");
  return fs
    .readFileSync(file, "utf8")
    .replace(/^---[^\S\r\n]*\r?\n[\s\S]*?\r?\n---[^\S\r\n]*(?:\r?\n|$)/, "")
    .trim();
}

function normalize(prompt) {
  return String(prompt || "").trim().toLowerCase().replace(/[.!\s]+$/, "");
}

function promptContext(text) {
  return `${JSON.stringify({ hookSpecificOutput: {
    hookEventName: "UserPromptSubmit", additionalContext: text
  } })}\n`;
}

function run() {
  const offFile = offSwitch();
  if (!offFile) return "";
  const input = readInput();
  const event = input.hook_event_name || process.argv[2] || "";
  const marker = offMarker(input.session_id);

  if (event === "SessionStart") {
    if (fs.existsSync(marker)) return "";
    const compass = compassBlock(input.cwd, false);
    const items = typeof input.cwd === "string" && input.cwd ? openItemsBlock(projectFile(input.cwd, OPEN_ITEMS_PATH)) : "";
    const goals = typeof input.cwd === "string" && input.cwd ? goalsBlock(projectFile(input.cwd, GOALS_PATH)) : "";
    const text =
      "STE REPLY MODE ACTIVE (on by default). The rules below apply to every reply. " +
      `"stop ste mode" turns them off for this session; create ${offFile} to turn them off everywhere.\n\n${skillBody()}\n` +
      (compass ? `\n${compass}\n` : "") + (items ? `\n${items}\n` : "") + (goals ? `\n${goals}\n` : "");
    remember(input.session_id);  // only after the body was read, so a failed read retries on the next event
    return text;
  }
  if (event === "UserPromptSubmit") {
    const prompt = normalize(input.prompt);
    const free = unquoted(prompt);
    if (OFF_EXACT.has(prompt) || OFF_ANYWHERE.test(free)) {
      fs.mkdirSync(path.dirname(marker), { recursive: true });
      fs.writeFileSync(marker, "off\n");
      return promptContext("[ihav-asd-ste100] STE reply mode is off for this session. Confirm in one line, then use your default style.\n");
    }
    if (ON_EXACT.has(prompt) || ON_ANYWHERE.test(free)) fs.rmSync(marker, { force: true });
    if (fs.existsSync(marker)) return "";
    // A session started on a release older than 0.18.0 has no version marker. When the bridge forwarder runs it,
    // treat it as an old session so it receives the current rules once.
    const known = seen(input.session_id) || (process.env.IHAV_STE100_BRIDGED === "1" ? "a release before 0.18.0" : "");
    const compass = compassBlock(input.cwd, COMPASS_ALL.has(prompt));
    const items = typeof input.cwd === "string" && input.cwd ? openItemsBlock(projectFile(input.cwd, OPEN_ITEMS_PATH), prompt === "o") : "";
    const goals = typeof input.cwd === "string" && input.cwd ? goalsBlock(projectFile(input.cwd, GOALS_PATH), prompt === "g") : "";
    const reminder = `${REMINDER}${compass ? ` ${compass}` : ""}${items ? ` ${items}` : ""}${goals ? ` ${goals}` : ""} Now ${clock()}.\n`;
    const text =
      known && known !== version()
        ? `STE REPLY RULES UPDATED to ${version()} (was ${known}). The rules below replace the earlier ones.\n\n` +
          `${skillBody()}\n\n${reminder}`
        : reminder;
    remember(input.session_id);  // only after the update text was built
    return promptContext(text);
  }
  if (event === "PostToolBatch") {
    if (fs.existsSync(marker)) return "";
    const additionalContext = `ihav-asd-ste100 clock: ${clock()}`;
    return `${JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolBatch", additionalContext } })}\n`;
  }
  return "";
}

try {
  process.stdout.write(run());
} catch {
  // Never block a session or a prompt.
}
process.exitCode = 0;
