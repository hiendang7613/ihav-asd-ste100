// ihav-asd-ste100 stable launcher. hooks/hooks.json always runs this file; it runs the hook logic of the active
// release, so a new release reaches open sessions at their next prompt without /reload-plugins.
//
// The active release is named in $IHAV_HOME/active/ihav-asd-ste100.json (default ~/.ihav), which
// scripts/activate.mjs writes after a smoke run. The launcher uses that release only when every check passes:
// the pointer is a regular file owned by this user and not writable by group or others, launcher_protocol is 1,
// its root resolves inside <config dir>/plugins/cache/ihav/ihav-asd-ste100/, and root/hooks/ste-core.mjs exists.
// Otherwise it runs its own hooks/ste-core.mjs. Any failure falls back silently: a hook must never block a prompt.

import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { activeCore } from "./active.mjs";

const OWN = path.join(path.dirname(fileURLToPath(import.meta.url)), "ste-core.mjs");

async function load() {
  const active = activeCore();
  if (active && active !== OWN) {
    try {
      return await import(pathToFileURL(active).href);
    } catch {
      // A broken active release falls through to this copy.
    }
  }
  return import(pathToFileURL(OWN).href);
}

const core = await load();
export const REMINDER = core.REMINDER;
export const clock = core.clock;
export const version = core.version;
