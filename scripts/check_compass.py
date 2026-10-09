"""Offline lint of a project's Compass file: <project>/.ihav_space/ihav-asd-ste100/compass.md. No model call.

Usage:
  python3 scripts/check_compass.py compass.md
  python3 scripts/check_compass.py compass.md --json

Line format: `- V1 text` is active, `- V1? text` is proposed (one letter, digits, an optional ?). The hook sends only
the active lines to the agent, at most 60 lines and 4 KB. Headings and blank lines are ignored.
Warnings: a line over 15 words, a repeated ID, a bullet that is not a valid line (it would be ignored), a hook cap that cuts lines.
Exit 0 (warnings never fail), 1 when the file cannot be read, 2 on wrong usage.
"""

import json
import re
import sys

MAX_WORDS = 15
MAX_LINES = 60
MAX_BYTES = 4096
LINE = re.compile(r"^[-*]\s+([A-Za-z][0-9]+)(\?)?\s+(\S.*)$")  # the same pattern as hooks/ste-core.mjs


def lint(text):
    active, proposed, warnings = [], [], []
    seen = set()
    for number, raw in enumerate(text.lstrip("﻿").splitlines(), 1):
        match = LINE.match(raw)
        if not match:
            if re.match(r"^[-*]\s", raw):
                warnings.append("line %d is a bullet without a valid ID, so it is ignored: %s" % (number, raw[:40]))
            continue
        ident, mark, body = match.group(1), match.group(2), match.group(3).strip()
        if ident.upper() in seen:
            warnings.append("line %d repeats the ID %s" % (number, ident))
        seen.add(ident.upper())
        if len(body.split()) > MAX_WORDS:
            warnings.append("line %d (%s) has %d words (limit %d); the hook keeps it" % (number, ident, len(body.split()), MAX_WORDS))
        (proposed if mark else active).append("%s %s" % (ident, body))
    size = len("; ".join(active).encode())
    if len(active) > MAX_LINES or size > MAX_BYTES:
        warnings.append("the hook sends at most %d active lines and %d bytes; this file has %d lines and %d bytes"
                        % (MAX_LINES, MAX_BYTES, len(active), size))
    return {"active": len(active), "proposed": len(proposed), "injected_bytes": size,
            "tokens_per_turn": round(size / 4), "warnings": warnings}


def main(argv):
    args = [a for a in argv[1:] if a != "--json"]
    if len(args) != 1 or args[0] in {"-h", "--help"}:
        print(__doc__.strip())
        return 2
    try:
        report = lint(open(args[0], encoding="utf-8").read())
    except OSError as error:
        print("cannot read %s: %s" % (args[0], error.strerror), file=sys.stderr)
        return 1
    if "--json" in argv:
        print(json.dumps(report, indent=2))
    else:
        print("active %d, proposed %d, about %d bytes (%d tokens) per turn" % (
            report["active"], report["proposed"], report["injected_bytes"], report["tokens_per_turn"]))
        for item in report["warnings"]:
            print("warning:", item)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
