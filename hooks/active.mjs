// Shared by the launcher (hooks/ste-mode.mjs) and scripts/activate.mjs. Importing this file has no side effects.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const PROTOCOL = 1;

export function configDir() {
  if (process.env.PLUGIN_ROOT) return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
}

export function pointerFile() {
  return path.join(process.env.IHAV_HOME || path.join(os.homedir(), ".ihav"), "active", "ihav-asd-ste100.json");
}

export function cacheBase() {
  return path.join(configDir(), "plugins", "cache", "ihav", "ihav-asd-ste100");
}

// Returns the core file of the active release, or null when the pointer is missing or fails a check.
export function activeCore() {
  try {
    const file = pointerFile();
    const stat = fs.lstatSync(file);
    if (!stat.isFile() || (process.getuid && stat.uid !== process.getuid()) || (stat.mode & 0o022)) return null;
    const pointer = JSON.parse(fs.readFileSync(file, "utf8"));
    if (pointer.launcher_protocol !== PROTOCOL || typeof pointer.root !== "string") return null;
    return coreIn(pointer.root);
  } catch {
    return null;
  }
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
