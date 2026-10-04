// ihav-asd-ste100 hook for SessionStart, UserPromptSubmit and PostToolBatch (Claude Code; Codex runs no plugin hooks).
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
// Any failure exits 0 with no output: this hook must never block a session or a prompt.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OFF_FILE = ".ihav-asd-ste100-off";
const OFF_EXACT = new Set(["stop ste mode", "normal mode"]);
const ON_EXACT = new Set(["ste mode", "start ste mode", "ste mode on"]);
const OFF_ANYWHERE = /\bstop ste mode\b/;
const ON_ANYWHERE = /\b(?:start ste mode|ste mode on)\b/;
export const REMINDER =
  "[ihav-asd-ste100] Reply shape: **Agents-Zone** (every step: `time` why => what), **Result-Zone** (key-first " +
  "bullets), **Admin-Zone**: **Conclusion:** one sentence, blank line, 0. **Goals:** (L, G with bar, B), 1. **Done:**, " +
  "2. **Doing:**, 3. **Todos:**, 4. **Pending:**, 5. **Quests:**, 6. **Risks:**, 7. **Ideas:**; items are sub-items with a bold key; " +
  '`<a>` = recommended. No emoji or square brackets. "stop ste mode" turns this off.';

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

function configDir() {
  if (process.env.PLUGIN_ROOT) return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
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

function skillBody() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const file = path.join(here, "..", "skills", "ihav-asd-ste100", "SKILL.md");
  return fs
    .readFileSync(file, "utf8")
    .replace(/^---[^\S\r\n]*\r?\n[\s\S]*?\r?\n---[^\S\r\n]*(?:\r?\n|$)/, "")
    .trim();
}

function normalize(prompt) {
  return String(prompt || "").trim().toLowerCase().replace(/[.!\s]+$/, "");
}

function run() {
  const offFile = offSwitch();
  if (!offFile) return "";
  const input = readInput();
  const event = input.hook_event_name || process.argv[2] || "";
  const marker = offMarker(input.session_id);

  if (event === "SessionStart") {
    if (fs.existsSync(marker)) return "";
    return (
      "STE REPLY MODE ACTIVE (on by default). The rules below apply to every reply. " +
      `"stop ste mode" turns them off for this session; create ${offFile} to turn them off everywhere.\n\n${skillBody()}\n`
    );
  }
  if (event === "UserPromptSubmit") {
    const prompt = normalize(input.prompt);
    const free = unquoted(prompt);
    if (OFF_EXACT.has(prompt) || OFF_ANYWHERE.test(free)) {
      fs.mkdirSync(path.dirname(marker), { recursive: true });
      fs.writeFileSync(marker, "off\n");
      return "[ihav-asd-ste100] STE reply mode is off for this session. Confirm in one line, then use your default style.\n";
    }
    if (ON_EXACT.has(prompt) || ON_ANYWHERE.test(free)) fs.rmSync(marker, { force: true });
    return fs.existsSync(marker) ? "" : `${REMINDER} Now ${clock()}.\n`;
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
