// Make an installed ihav-asd-ste100 release the active one for every open session.
//
// Usage:
//   node scripts/activate.mjs                 # activate the release this script belongs to
//   node scripts/activate.mjs --root DIR      # activate another installed release
//   node scripts/activate.mjs --rollback      # go back to the previous release; warn on legacy prompt text
//   node scripts/activate.mjs --status        # print the pointer
//
// The release must sit inside <config dir>/plugins/cache/ihav/ihav-asd-ste100/. Before the pointer changes, a smoke
// run starts the release's hook in a throwaway config directory and checks its SessionStart and prompt output.
// The pointer is written atomically: a temporary file in the same directory, then a rename.
// Exit 0 on success, 1 when the release fails a check (the pointer is left unchanged), 2 on wrong usage.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PROTOCOL, coreIn, pointerFile } from "../hooks/active.mjs";

const OWN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readPointer() {
  try {
    return JSON.parse(fs.readFileSync(pointerFile(), "utf8"));
  } catch {
    return null;
  }
}

function releaseVersion(root) {
  return JSON.parse(fs.readFileSync(path.join(root, ".claude-plugin", "plugin.json"), "utf8")).version;
}

// Forward activation requires JSON. Explicit rollback also recognizes the older STE reminder,
// preserving recovery to a previous release without treating arbitrary malformed output as valid.
function smoke(core, allowLegacy) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ste100-smoke-"));
  try {
    const env = { PATH: process.env.PATH, HOME: home, CLAUDE_CONFIG_DIR: home, CODEX_HOME: home };
    const run = (payload) =>
      spawnSync(process.execPath, [core], { input: JSON.stringify(payload), env, encoding: "utf8", timeout: 10000 });
    const start = run({ hook_event_name: "SessionStart", session_id: "smoke" });
    if (start.status !== 0 || start.stderr.trim() || !start.stdout.startsWith("STE REPLY MODE ACTIVE")) {
      return { error: "SessionStart output is wrong" };
    }
    const prompt = run({ hook_event_name: "UserPromptSubmit", session_id: "smoke", prompt: "hi" });
    if (prompt.status !== 0 || prompt.stderr.trim()) return { error: "prompt reminder is wrong" };
    try {
      const data = JSON.parse(prompt.stdout);
      const specific = data.hookSpecificOutput;
      if (data.decision !== undefined || data.continue !== undefined ||
          specific?.hookEventName !== "UserPromptSubmit" ||
          typeof specific.additionalContext !== "string" ||
          !specific.additionalContext.includes("Reply shape")) return { error: "prompt context contract is wrong" };
    } catch {
      if (allowLegacy && /^\[ihav-asd-ste100\] Reply shape(?: [^:\r\n]+)?:[^\r\n]+$/.test(prompt.stdout.trim())) {
        return { error: "", legacy: true };
      }
      return { error: "prompt context must be valid UserPromptSubmit JSON" };
    }
    return { error: "", legacy: false };
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
}

function sameDir(left, right) {
  try {
    return fs.realpathSync(left) === fs.realpathSync(right);
  } catch {
    return false;
  }
}

function write(pointer) {
  const file = pointerFile();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(pointer, null, 2)}\n`, { mode: 0o644 });
  fs.chmodSync(temp, 0o644);
  fs.renameSync(temp, file);
}

function activate(root, previous, allowLegacy) {
  const core = coreIn(root);
  if (!core) return { error: `not an installed release inside the ihav plugin cache: ${root}` };
  const result = smoke(core, allowLegacy);
  if (result.error) return { error: `smoke run failed: ${result.error}` };
  const resolved = path.dirname(path.dirname(core));
  if (previous && previous.root && sameDir(previous.root, resolved)) {
    // Activating the release that is already active keeps its rollback target.
    previous = previous.previous;
  }
  write({
    root: resolved,
    version: releaseVersion(resolved),
    launcher_protocol: PROTOCOL,
    activated: new Date().toISOString(),
    previous: previous && previous.root ? { root: previous.root, version: previous.version } : null,
  });
  return result;
}

function main(argv) {
  const current = readPointer();
  if (argv[0] === "--status") {
    process.stdout.write(`${JSON.stringify(current, null, 2)}\n`);
    return 0;
  }
  let root = OWN_ROOT;
  let previous = current;
  const rollback = argv[0] === "--rollback";
  if (rollback) {
    if (!current || !current.previous || !current.previous.root) {
      process.stderr.write("no previous release to roll back to\n");
      return 1;
    }
    root = current.previous.root;
  } else if (argv[0] === "--root" && argv[1]) {
    root = argv[1];
  } else if (argv.length) {
    process.stderr.write("usage: activate.mjs [--root DIR | --rollback | --status]\n");
    return 2;
  }
  const result = activate(root, previous, rollback);
  if (result.error) {
    process.stderr.write(`${result.error}; the active release is unchanged\n`);
    return 1;
  }
  process.stdout.write(`${JSON.stringify(readPointer(), null, 2)}\n`);
  if (result.legacy) {
    process.stderr.write("Warning: rolled back to legacy plain-text prompt output; Codex 0.160.0 reports invalid JSON and omits this hook context. Activate a JSON-compatible release to restore it.\n");
  }
  process.stderr.write(`${ensureMissing(readPointer().root)}\n`);
  return 0;
}

// Re-create deleted release folders as forwarders, so sessions that still point at them keep working.
// A failure here never undoes or fails the activation.
function ensureMissing(root) {
  const bridge = path.join(root, "scripts", "bridge.mjs");
  if (!fs.existsSync(bridge)) return "ensure-missing: skipped, this release has no bridge";
  const run = spawnSync(process.execPath, [bridge, "--ensure-missing"], { encoding: "utf8", timeout: 20000 });
  try {
    const created = JSON.parse(run.stdout).results.filter((r) => r.status === "created").map((r) => path.basename(r.root));
    return `ensure-missing: ${run.status === 0 ? "ok" : "failed"}, created ${created.length ? created.join(", ") : "none"}`;
  } catch {
    return `ensure-missing: failed (${(run.stderr || "no output").trim().slice(0, 200)})`;
  }
}

process.exitCode = main(process.argv.slice(2));
