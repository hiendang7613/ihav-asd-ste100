// Install or remove the personal /x skill: typing /x asks for the project's Compass alone.
//
// Usage:
//   node scripts/install-x.mjs            # install or update <config dir>/skills/x/SKILL.md
//   node scripts/install-x.mjs --remove   # remove it, only if this plugin wrote it
//
// The file carries an ownership marker. A skill named x that lacks the marker belongs to someone else, so this
// script never overwrites or removes it. Exit 0 on success, 1 when a foreign skill blocks the change, 2 on wrong usage.

import { installSkill } from "./install-skill.mjs";

export const MARKER = "<!-- owned-by: ihav-asd-ste100 install-x -->";
const SKILL = `---
name: x
description: Show only the Compass of the current project, the same as typing "x" or "compass".
---

${MARKER}

x

Reply with the Compass alone, in the ihav-asd-ste100 shape: the bold Compass label, then the active compass lines
grouped by letter (V Vision, A Architecture, W Work habits, C Code, S Style), then the proposed lines marked
"(proposed, not enforced)". Take the lines from the Compass in the context; when it is missing, read
.ihav_space/ihav-asd-ste100/compass.md, searched from the project folder up to the git root. With no Compass file,
say so in one sentence. Add no other zone.
`;

process.exitCode = installSkill({ name: "x", marker: MARKER, skill: SKILL, script: "install-x.mjs", argv: process.argv.slice(2) });
