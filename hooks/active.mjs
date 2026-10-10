// Shared by the launcher (hooks/ste-mode.mjs) and scripts/activate.mjs. Importing this file has no side effects.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const PROTOCOL = 1;

// A different plugin's root can leak from the process that launched a Claude worker.
// An own or unidentified root keeps the existing Codex signal, including older callers.
function foreignPluginRoot(root) {
  for (const dir of [".codex-plugin", ".claude-plugin"]) {
    try {
      const name = JSON.parse(fs.readFileSync(path.join(root, dir, "plugin.json"), "utf8")).name;
      if (typeof name === "string" && name) return name !== "ihav-asd-ste100";
    } catch {
      // Missing or unreadable metadata cannot identify a foreign plugin.
    }
  }
  // Native installers can remove the caller's old cache while its environment stays live.
  const [plugins, cache, marketplace, name, version] = path.resolve(root).split(path.sep).slice(-5);
  return plugins === "plugins" && cache === "cache" && Boolean(marketplace && name && version) &&
    name !== "ihav-asd-ste100";
}

export function configDir() {
  if (process.env.PLUGIN_ROOT && !foreignPluginRoot(process.env.PLUGIN_ROOT)) {
    return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
  }
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
}

export function pointerFile() {
  return path.join(process.env.IHAV_HOME || path.join(os.homedir(), ".ihav"), "active", "ihav-asd-ste100.json");
}

export function cacheBase() {
  return path.join(configDir(), "plugins", "cache", "ihav", "ihav-asd-ste100");
}

export function readActivePointer() {
  try {
    const file = pointerFile();
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || (process.getuid && stat.uid !== process.getuid()) || (stat.mode & 0o022)) return null;
    const pointer = JSON.parse(fs.readFileSync(file, "utf8"));
    if (pointer.launcher_protocol !== PROTOCOL || typeof pointer.root !== "string") return null;
    return pointer;
  } catch {
    return null;
  }
}

// Protocol 1 keeps root for old launchers. Updated hosts can resolve the same version in their own cache.
export function pointerCore(pointer) {
  if (!pointer || typeof pointer.root !== "string") return null;
  const direct = coreIn(pointer.root);
  if (direct) return direct;
  try {
    const base = fs.realpathSync(cacheBase());
    // A broken or escaping path in this host's cache must fail, not fall through to a different release.
    const lexical = path.resolve(pointer.root);
    if (lexical === path.resolve(cacheBase()) || lexical.startsWith(path.resolve(cacheBase()) + path.sep)) return null;
    try {
      const root = fs.realpathSync(pointer.root);
      if (root === base || root.startsWith(base + path.sep)) return null;
    } catch { /* A removed other-host cache can still name the version. */ }
    if (!path.isAbsolute(pointer.root) || typeof pointer.version !== "string" ||
        !/^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(pointer.version)) return null;
    const root = path.join(cacheBase(), pointer.version);
    const core = coreIn(root);
    if (!core) return null;
    const manifest = JSON.parse(fs.readFileSync(path.join(root, ".claude-plugin", "plugin.json"), "utf8"));
    return manifest.name === "ihav-asd-ste100" && manifest.version === pointer.version ? core : null;
  } catch { return null; }
}

// Missing or tampered pointers always fall back to the launcher's own copy.
export function activeCore() {
  return pointerCore(readActivePointer());
}

// The core file of a release root inside the cache base, or null.
export function coreIn(rootDir) {
  try {
    const base = fs.realpathSync(cacheBase());
    const root = fs.realpathSync(rootDir);
    if (!root.startsWith(base + path.sep)) return null;
    const core = fs.realpathSync(path.join(root, "hooks", "ste-core.mjs"));
    return core.startsWith(base + path.sep) && fs.statSync(core).isFile() ? core : null;
  } catch {
    return null;
  }
}
