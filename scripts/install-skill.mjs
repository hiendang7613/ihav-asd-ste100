// Shared by install-az.mjs and install-x.mjs: install or remove one personal skill in <config dir>/skills/<name>/SKILL.md.
//
// The file carries an ownership marker. A skill with the same name that lacks the marker belongs to someone else, so
// this never overwrites or removes it. Returns the exit code: 0 on success, 1 when a foreign skill blocks the change,
// 2 on wrong usage.

import fs from "node:fs";
import path from "node:path";
import { configDir } from "../hooks/active.mjs";

export function installSkill({ name, marker, skill, script, argv }) {
  const file = path.join(configDir(), "skills", name, "SKILL.md");
  const exists = fs.existsSync(path.dirname(file));
  if (argv.length > 1 || (argv.length === 1 && argv[0] !== "--remove")) {
    process.stderr.write(`usage: ${script} [--remove]\n`);
    return 2;
  }
  let owned = false;
  try {
    owned = fs.readFileSync(file, "utf8").includes(marker);
  } catch {
    // No readable file: nothing of ours is there.
  }
  if (exists && !owned) {
    process.stderr.write(`${path.dirname(file)} belongs to another skill; left unchanged\n`);
    return 1;
  }
  if (argv[0] === "--remove") {
    fs.rmSync(file, { force: true });
    if (exists && fs.readdirSync(path.dirname(file)).length === 0) fs.rmdirSync(path.dirname(file));
    process.stdout.write(`removed ${file}\n`);
    return 0;
  }
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, skill);
  process.stdout.write(`installed ${file}\n`);
  return 0;
}
