// Install or remove the personal /az skill: typing /az asks for the Admin-Zone alone.
//
// Usage:
//   node scripts/install-az.mjs            # install or update <config dir>/skills/az/SKILL.md
//   node scripts/install-az.mjs --remove   # remove it, only if this plugin wrote it
//
// The file carries an ownership marker. A skill named az that lacks the marker belongs to someone else, so this
// script never overwrites or removes it. Exit 0 on success, 1 when a foreign skill blocks the change, 2 on wrong usage.

import { installSkill } from "./install-skill.mjs";

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

process.exitCode = installSkill({ name: "az", marker: MARKER, skill: SKILL, script: "install-az.mjs", argv: process.argv.slice(2) });
