// Make an installed ihav-asd-ste100 release the active one for every open session.
//
// Usage:
//   node scripts/activate.mjs                 # activate the release this script belongs to
//   node scripts/activate.mjs --root DIR      # activate another installed release
//   node scripts/activate.mjs --all-hosts [--root DIR] # copy to installed host caches, smoke both, then activate
//   node scripts/activate.mjs --prepare-marketplace DIR # make a local ihav catalogue for native installers
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
import { PROTOCOL, coreIn, pointerFile, pointerCore, readActivePointer } from "../hooks/active.mjs";

const OWN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const readPointer = readActivePointer;

function releaseVersion(root) {
  return JSON.parse(fs.readFileSync(path.join(root, ".claude-plugin", "plugin.json"), "utf8")).version;
}

// Forward activation requires JSON. Explicit rollback also recognizes the older STE reminder,
// preserving recovery to a previous release without treating arbitrary malformed output as valid.
function smoke(core, allowLegacy, codex = Boolean(process.env.PLUGIN_ROOT)) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ste100-smoke-"));
  try {
    const env = { PATH: process.env.PATH, HOME: home, CLAUDE_CONFIG_DIR: home, CODEX_HOME: home };
    if (codex) env.PLUGIN_ROOT = path.dirname(path.dirname(core));
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
  if (previous?.root && (sameDir(previous.root, resolved) || previous.version === releaseVersion(resolved))) {
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

// Only shipped files: never copy a checkout's Git data, evidence, evals or dependency folders.
const PARTS = ["hooks", "skills", "scripts", ".claude-plugin", ".codex-plugin", "licenses",
  "README.md", "INSTALL.md", "CHANGELOG.md", "LICENSE"];
function entryExists(file) {
  try { fs.lstatSync(file); return true; } catch { return false; }
}
function copyRelease(source, target) {
  const copy = (from, to) => {
    const stat = fs.lstatSync(from);
    if (stat.isSymbolicLink()) throw new Error(`release contains a symlink: ${from}`);
    if (stat.isDirectory()) {
      fs.mkdirSync(to);
      for (const name of fs.readdirSync(from)) {
        if (name !== "__pycache__" && name !== ".DS_Store") copy(path.join(from, name), path.join(to, name));
      }
    } else if (stat.isFile()) fs.copyFileSync(from, to);
    else throw new Error(`release contains a non-file: ${from}`);
  };
  for (const part of PARTS) if (entryExists(path.join(source, part))) copy(path.join(source, part), path.join(target, part));
}

function checkedVersion(root) {
  const manifests = [".claude-plugin", ".codex-plugin"].map(dir =>
    JSON.parse(fs.readFileSync(path.join(root, dir, "plugin.json"), "utf8")));
  const version = manifests[0].version;
  if (manifests.some(m => m.name !== "ihav-asd-ste100" || m.version !== version) ||
      typeof version !== "string" || !/^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version)) {
    throw new Error("release manifests must name this plugin and the same safe version");
  }
  return version;
}

function prepareMarketplace(source, destination) {
  checkedVersion(source);
  if (entryExists(destination)) throw new Error("marketplace destination already exists; choose a new directory");
  if (PARTS.some(part => destination.startsWith(path.resolve(source, part) + path.sep))) {
    throw new Error("marketplace destination must be outside the shipped source folders");
  }
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const stage = fs.mkdtempSync(path.join(path.dirname(destination), ".ste-marketplace-"));
  try {
    copyRelease(source, stage);
    const manifest = path.join(stage, ".claude-plugin", "marketplace.json");
    const data = JSON.parse(fs.readFileSync(manifest, "utf8"));
    data.name = "ihav"; // Preserve the admin's installed plugin ID; the checkout's catalogue has a different name.
    fs.writeFileSync(manifest, JSON.stringify(data, null, 2) + "\n");
    fs.renameSync(stage, destination);
  } finally { fs.rmSync(stage, { recursive: true, force: true }); }
  return { marketplace: path.resolve(destination), version: releaseVersion(source) };
}

function inHost(host, root, action) {
  const before = process.env.PLUGIN_ROOT;
  if (host === "codex") process.env.PLUGIN_ROOT = root;
  else delete process.env.PLUGIN_ROOT;
  try { return action(); }
  finally {
    if (before === undefined) delete process.env.PLUGIN_ROOT;
    else process.env.PLUGIN_ROOT = before;
  }
}

function installedCache(base) {
  try {
    return fs.readdirSync(base).some(name => {
      try {
        const root = path.join(base, name);
        return !fs.existsSync(path.join(root, ".ihav-bridge-created")) &&
          JSON.parse(fs.readFileSync(path.join(root, ".claude-plugin", "plugin.json"), "utf8")).name === "ihav-asd-ste100";
      } catch { return false; }
    });
  } catch { return false; }
}

function allHosts(source, current, rollback) {
  const hosts = [
    { host: "claude", config: process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude") },
    { host: "codex", config: process.env.CODEX_HOME || path.join(os.homedir(), ".codex") },
  ].map(h => {
    const base = path.join(h.config, "plugins/cache/ihav/ihav-asd-ste100");
    return { ...h, base, status: installedCache(base) ? "not activated" : "not installed" };
  });
  const staged = [];
  try {
    const version = checkedVersion(source);
    for (const host of hosts) {
      if (host.status === "not installed") continue;
      const base = fs.realpathSync(host.base);
      host.root = path.join(base, version);
      // Existing cache symlinks may not escape the host's own cache boundary.
      if (entryExists(host.root) && fs.realpathSync(host.root) !== host.root) throw new Error(`${host.host}: target is a symlink`);
      host.stage = fs.mkdtempSync(path.join(base, ".ste-stage-"));
      staged.push(host);
      copyRelease(source, host.stage);
      const result = inHost(host.host, host.stage, () => {
        const core = coreIn(host.stage);
        return core ? smoke(core, rollback, host.host === "codex") : { error: "core escapes or is missing from the cache" };
      });
      if (result.error) {
        host.status = "failed the smoke run";
        throw new Error(`${host.host}: ${result.error}`);
      }
      host.legacy = result.legacy;
    }
    if (!staged.length) throw new Error("this plugin is not installed in either host cache");
    for (const host of staged) {
      if (entryExists(host.root)) {
        host.backup = `${host.root}.before-${Date.now()}-${process.pid}`;
        fs.renameSync(host.root, host.backup); // Preserve pre-existing files, including same-version updates.
      }
      fs.renameSync(host.stage, host.root);
      host.replaced = true;
    }
    const root = staged[0].root;
    const previous = current?.version === version ? current.previous : current;
    write({ root, version, launcher_protocol: PROTOCOL, activated: new Date().toISOString(),
      previous: previous?.root ? { root: previous.root, version: previous.version } : null });
    for (const host of staged) {
      host.status = "activated";
      try { host.repair = inHost(host.host, host.root, () => ensureMissing(host.root)); }
      catch (error) { host.repair = `ensure-missing: failed (${error.message})`; }
    }
    return { pointer: readPointer(), hosts: hosts.map(({ host, status, root, backup, repair, legacy }) =>
      ({ host, status, root, backup, repair, legacy })) };
  } catch (error) {
    for (const host of staged.reverse()) {
      if (host.replaced) fs.renameSync(host.root, host.stage);
      if (host.backup) fs.renameSync(host.backup, host.root);
    }
    return { error: error.message, hosts: hosts.map(({ host, status }) => ({ host, status })) };
  } finally {
    for (const host of staged) fs.rmSync(host.stage, { recursive: true, force: true });
  }
}

function main(argv) {
  const current = readPointer();
  if (argv.length === 1 && argv[0] === "--status") {
    process.stdout.write(`${JSON.stringify(current, null, 2)}\n`);
    return 0;
  }
  let root = OWN_ROOT;
  let previous = current;
  let rollback = false, batch = false, marketplace, rootGiven = false;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--all-hosts" && !batch) batch = true;
    else if (argv[i] === "--rollback" && !rollback) rollback = true;
    else if (argv[i] === "--root" && argv[i + 1] && !rootGiven && !argv[i + 1].startsWith("--")) {
      root = path.resolve(argv[++i]); rootGiven = true;
    }
    else if (argv[i] === "--prepare-marketplace" && argv[i + 1] && !marketplace && !argv[i + 1].startsWith("--")) marketplace = path.resolve(argv[++i]);
    else return usage();
  }
  if ((rollback && rootGiven) || (marketplace && (batch || rollback))) return usage();
  if (marketplace) {
    try { process.stdout.write(JSON.stringify(prepareMarketplace(root, marketplace), null, 2) + "\n"); return 0; }
    catch (error) { process.stderr.write(error.message + "\n"); return 1; }
  }
  if (rollback) {
    if (!current || !current.previous || !current.previous.root) {
      process.stderr.write("no previous release to roll back to\n");
      return 1;
    }
    const core = pointerCore(current.previous);
    root = core ? path.dirname(path.dirname(core)) : current.previous.root;
  }
  if (batch) {
    let result;
    try { result = allHosts(root, current, rollback); }
    catch (error) { result = { error: error.message }; }
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    if (result.error) process.stderr.write(`${result.error}; the active release is unchanged\n`);
    if (result.hosts?.some(h => h.legacy)) process.stderr.write("Warning: rolled back to legacy plain-text prompt output; Codex omits this hook context.\n");
    return result.error ? 1 : 0;
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

function usage() {
  process.stderr.write("usage: activate.mjs [--root DIR] [--all-hosts | --rollback | --prepare-marketplace DIR] | --status\n");
  return 2;
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
