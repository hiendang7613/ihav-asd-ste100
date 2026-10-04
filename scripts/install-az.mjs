// Install or remove the personal /az skill: typing /az asks for the Admin-Zone alone.
//
// Usage:
//   node scripts/install-az.mjs            # install or update <config dir>/skills/az/SKILL.md
//   node scripts/install-az.mjs --remove   # remove it, only if this plugin wrote it
//
// The file carries an ownership marker. A skill named az that lacks the marker belongs to someone else, so this
// script never overwrites or removes it. Exit 0 on success, 1 when a foreign skill blocks the change, 2 on wrong usage.

import fs from "node:fs";
import path from "node:path";
import { configDir } from "../hooks/active.mjs";

export const MARKER = "<!-- owned-by: ihav-asd-ste100 install-az -->";
const SKILL = `---
name: az
description: Show only the Admin-Zone of the current work, the same as typing "az" or "adminzone".
---

${MARKER}

az

Reply with the Admin-Zone alone: the bold Admin-Zone label, the Conclusion line and all eight sections, in the
ihav-asd-ste100 shape, for the current state of the work. Add no other zone.
`;

function target() {
  return path.join(configDir(), "skills", "az", "SKILL.md");
}

function owned(file) {
  try {
    return fs.readFileSync(file, "utf8").includes(MARKER);
  } catch {
    return false;
  }
}

function main(argv) {
  const file = target();
  const exists = fs.existsSync(path.dirname(file));
  if (argv.length > 1 || (argv.length === 1 && argv[0] !== "--remove")) {
    process.stderr.write("usage: install-az.mjs [--remove]\n");
    return 2;
  }
  if (exists && !owned(file)) {
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
  fs.writeFileSync(file, SKILL);
  process.stdout.write(`installed ${file}\n`);
  return 0;
}

process.exitCode = main(process.argv.slice(2));
