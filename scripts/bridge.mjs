// Bridge old installed hooks to the active release; originals stay recoverable.
// --list is read-only. --apply DIR / --restore DIR target one cache release;
// --apply-all / --restore-all visit old releases in this host's config cache.
// --ensure DIR recreates a missing hook path; --ensure-missing covers every release from 0.12.0 named in
// this release's CHANGELOG.md, so deleted folders of any later release come back as forwarders too.
// JSON on stdout; exit 0 success, 1 folder failure, 2 invalid arguments.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configDir } from "../hooks/active.mjs";

const MARKER = "// ihav-asd-ste100 bridge forwarder v1";
const CREATED = ".ihav-bridge-created";
const PLUGINS = new Set(["ihav-asd-ste100", "i-have-asd-ste100"]);
const FORWARDER = `${MARKER}
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
process.env.IHAV_STE100_BRIDGED = "1";
function activeCore() {
  try {
    const config = process.env.PLUGIN_ROOT
      ? process.env.CODEX_HOME || path.join(os.homedir(), ".codex")
      : process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
    const file = path.join(process.env.IHAV_HOME || path.join(os.homedir(), ".ihav"), "active", "ihav-asd-ste100.json");
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || (process.getuid && stat.uid !== process.getuid()) || (stat.mode & 0o022)) return null;
    const pointer = JSON.parse(fs.readFileSync(file, "utf8"));
    if (pointer.launcher_protocol !== 1 || typeof pointer.root !== "string") return null;
    const base = fs.realpathSync(path.join(config, "plugins", "cache", "ihav", "ihav-asd-ste100"));
    const root = fs.realpathSync(pointer.root);
    if (!root.startsWith(base + path.sep)) return null;
    const core = fs.realpathSync(path.join(root, "hooks", "ste-core.mjs"));
    return core.startsWith(base + path.sep) && fs.statSync(core).isFile() ? core : null;
  } catch { return null; }
}
try {
  const core = activeCore();
  if (core) {
    try { await import(pathToFileURL(core).href); }
    catch { await import("./ste-mode.orig.mjs"); }
  } else { await import("./ste-mode.orig.mjs"); }
} catch { /* Hooks must not block a prompt, even if the original is broken. */ }
process.exitCode = 0;
`;

function exists(file) {
  try { fs.lstatSync(file); return true; }
  catch (error) { if (error.code === "ENOENT") return false; throw error; }
}

function regular(file) {
  if (!fs.lstatSync(file).isFile()) throw new Error(`not a regular file: ${file}`);
  return fs.readFileSync(file);
}

function cache() { return path.resolve(configDir(), "plugins", "cache"); }

function location(dir) {
  const root = path.resolve(dir);
  const relative = path.relative(cache(), root);
  const parts = relative.split(path.sep);
  if (parts.length !== 3 || parts.some((p) => !p || p === "..") || !PLUGINS.has(parts[1])) {
    throw new Error(`not a supported release in the config cache: ${root}`);
  }
  return { root, parts };
}

function release(dir) {
  const { root, parts } = location(dir);
  // Do not replace files through marketplace, plugin, version or hooks symlinks.
  let cursor = cache();
  for (const part of [...parts, "hooks"]) {
    cursor = path.join(cursor, part);
    if (!fs.lstatSync(cursor).isDirectory()) throw new Error(`not a regular directory: ${cursor}`);
  }
  const hooks = path.join(root, "hooks");
  if (exists(path.join(hooks, "ste-core.mjs"))) throw new Error("release already has ste-core.mjs; bridge refused");
  return { root, parts, hook: path.join(hooks, "ste-mode.mjs"), original: path.join(hooks, "ste-mode.orig.mjs") };
}

function ensure(dir) {
  const { root, parts } = location(dir);
  if (exists(root)) {
    // Validate existing paths, but never modify an existing release in ensure mode.
    release(root);
    return { root, status: "skipped", reason: "release already exists" };
  }
  fs.mkdirSync(cache(), { recursive: true });
  let parent = cache();
  for (const part of parts.slice(0, 2)) {
    parent = path.join(parent, part);
    if (!exists(parent)) fs.mkdirSync(parent);
    if (!fs.lstatSync(parent).isDirectory()) throw new Error(`not a regular directory: ${parent}`);
  }
  fs.mkdirSync(root); // Exclusive: do not adopt a folder created by another process.
  // Record ownership before creating the hook, for recoverable partial setup.
  fs.writeFileSync(path.join(root, CREATED), JSON.stringify({ marker: MARKER, root }) + "\n", { flag: "wx" });
  fs.mkdirSync(path.join(root, "hooks"));
  atomicWrite(path.join(root, "hooks/ste-mode.mjs"), FORWARDER, 0o644);
  return { root, status: "created" };
}

function restoreCreated(entry) {
  const marker = path.join(entry.root, CREATED);
  const owned = JSON.parse(regular(marker).toString("utf8"));
  if (owned.marker !== MARKER || owned.root !== entry.root) throw new Error("created-folder marker does not match");
  if (fs.readdirSync(entry.root).sort().join("|") !== `${CREATED}|hooks` ||
      fs.readdirSync(path.join(entry.root, "hooks")).join("|") !== "ste-mode.mjs" ||
      !regular(entry.hook).equals(Buffer.from(FORWARDER))) {
    throw new Error("created folder changed; preserve added or changed files before restore");
  }
  fs.unlinkSync(entry.hook);
  fs.rmdirSync(path.join(entry.root, "hooks"));
  fs.unlinkSync(marker);
  fs.rmdirSync(entry.root);
  return { root: entry.root, status: "removed" };
}

function discover() {
  const roots = [];
  const base = cache();
  if (!exists(base)) return roots;
  for (const market of fs.readdirSync(base, { withFileTypes: true }).filter((d) => d.isDirectory())) {
    for (const plugin of [...PLUGINS]) {
      const dir = path.join(base, market.name, plugin);
      if (!exists(dir) || !fs.lstatSync(dir).isDirectory()) continue;
      for (const version of fs.readdirSync(dir, { withFileTypes: true }).filter((d) => d.isDirectory())) {
        roots.push(path.join(dir, version.name));
      }
    }
  }
  return roots.sort();
}

function atomicWrite(file, data, mode) {
  const dir = fs.mkdtempSync(path.join(path.dirname(file), ".ste-bridge-"));
  const temp = path.join(dir, "hook");
  try {
    fs.writeFileSync(temp, data, { flag: "wx", mode });
    fs.chmodSync(temp, mode);
    fs.renameSync(temp, file);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function saveCopy(file, data, mode) {
  if (exists(file)) {
    if (!regular(file).equals(data)) throw new Error(`existing recovery copy differs: ${file}`);
  } else { fs.writeFileSync(file, data, { flag: "wx", mode }); }
}

function backupFile(parts) {
  const home = process.env.IHAV_HOME || path.join(os.homedir(), ".ihav");
  // Reject symlinks in the backup subtree rather than writing outside it.
  fs.mkdirSync(home, { recursive: true });
  let dir = home;
  for (const part of ["backups", "ihav-asd-ste100", ...parts]) {
    dir = path.join(dir, part);
    if (!exists(dir)) fs.mkdirSync(dir);
    if (!fs.lstatSync(dir).isDirectory()) throw new Error(`not a regular backup directory: ${dir}`);
  }
  return path.join(dir, "ste-mode.mjs");
}

function operate(dir, action) {
  if (action === "ensure") return ensure(dir);
  const entry = release(dir);
  if (action === "restore" && exists(path.join(entry.root, CREATED))) return restoreCreated(entry);
  const data = regular(entry.hook);
  const bridged = data.toString("utf8").startsWith(MARKER);
  if (action === "list") return { root: entry.root, status: bridged ? "bridged" : "eligible" };
  if (action === "apply") {
    if (bridged) return { root: entry.root, status: "skipped", reason: "already bridged" };
    const mode = fs.statSync(entry.hook).mode & 0o777;
    saveCopy(entry.original, data, mode);
    const backup = backupFile(entry.parts);
    saveCopy(backup, data, mode);
    atomicWrite(entry.hook, FORWARDER, mode);
    return { root: entry.root, status: "applied", backup };
  }
  if (!exists(entry.original)) {
    if (bridged) throw new Error("bridged hook has no original recovery copy");
    return { root: entry.root, status: "skipped", reason: "not bridged" };
  }
  const original = regular(entry.original);
  if (!bridged && !data.equals(original)) throw new Error("hook changed since bridging; preserve it before restore");
  atomicWrite(entry.hook, original, fs.statSync(entry.original).mode & 0o777);
  fs.unlinkSync(entry.original);
  return { root: entry.root, status: "restored" };
}

// Releases from 0.12.0 on, read from the "## X.Y.Z" headings of this release's CHANGELOG.md.
function releases() {
  const log = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "CHANGELOG.md");
  const found = new Set(["0.12.0", "0.13.0", "0.14.0", "0.15.0", "0.16.0", "0.17.0"]);
  try {
    for (const match of fs.readFileSync(log, "utf8").matchAll(/^## ([0-9]+)\.([0-9]+)\.([0-9]+)\b/gm)) {
      const [major, minor] = [Number(match[1]), Number(match[2])];
      if (major > 0 || minor >= 12) found.add(`${match[1]}.${match[2]}.${match[3]}`);
    }
  } catch { /* The fixed list above still applies. */ }
  return [...found].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

function main(argv) {
  const [flag, dir] = argv;
  const single = flag === "--apply" || flag === "--restore" || flag === "--ensure";
  const all = flag === "--apply-all" || flag === "--restore-all" || flag === "--ensure-missing";
  if ((!single && !all && flag !== "--list") || argv.length !== (single ? 2 : 1) || (single && !dir)) {
    process.stdout.write(JSON.stringify({ ok: false, error: "usage: bridge.mjs --list | --apply DIR | --apply-all | --restore DIR | --restore-all | --ensure DIR | --ensure-missing" }) + "\n");
    return 2;
  }
  const action = flag === "--list" ? "list" : flag.startsWith("--apply") ? "apply" : flag.startsWith("--ensure") ? "ensure" : "restore";
  const results = [];
  const roots = single ? [dir] : flag === "--ensure-missing"
    ? releases().map((version) => path.join(cache(), "ihav", "ihav-asd-ste100", version))
    : discover();
  for (const root of roots) {
    try { results.push(operate(root, action)); }
    catch (error) {
      // Modern releases are visible in listings but outside batch migration.
      const modern = error.message === "release already has ste-core.mjs; bridge refused";
      results.push({ root: path.resolve(root), status: modern && !single ? "skipped" : "failed", error: error.message });
    }
  }
  const ok = !results.some((r) => r.status === "failed");
  process.stdout.write(JSON.stringify({ ok, action, results }) + "\n");
  return ok ? 0 : 1;
}

try { process.exitCode = main(process.argv.slice(2)); }
catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: error.message }) + "\n");
  process.exitCode = 1;
}
