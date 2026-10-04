"""Read-only format audit: check the latest full-format reply of every recent Claude Code session.

Usage:
  python3 scripts/audit_sessions.py                     # sessions active in the last 120 minutes
  python3 scripts/audit_sessions.py --since-minutes 30 --json
  python3 scripts/audit_sessions.py --projects-dir DIR  # default ~/.claude/projects

For each project folder, it reads every session transcript (*.jsonl) modified inside the window, takes the last
assistant text that contains **Admin-Zone** or **Conclusion:**, and runs check_reply.check() on it.
It writes nothing except the report on stdout. Exit 0 when every checked reply passes, 1 otherwise, 2 on wrong usage.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # read-only: do not leave __pycache__ next to the checker
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_reply import check  # noqa: E402


def last_reply(transcript):
    """The last assistant text in a transcript that has the conclusion part, with its timestamp."""
    found = None
    with open(transcript, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("type") != "assistant":
                continue
            content = (record.get("message") or {}).get("content") or []
            text = "".join(part.get("text", "") for part in content
                           if isinstance(part, dict) and part.get("type") == "text").strip()
            if "**Admin-Zone**" in text or "**Conclusion:**" in text:
                found = (text, record.get("timestamp", ""))
    return found


def audit(projects_dir, since_minutes):
    cutoff = time.time() - since_minutes * 60
    rows = []
    for project in sorted(p for p in Path(projects_dir).iterdir() if p.is_dir()):
        for transcript in sorted(project.glob("*.jsonl")):
            if transcript.stat().st_mtime < cutoff:
                continue
            reply = last_reply(transcript)
            if not reply:
                continue
            report = check(reply[0])
            rows.append({
                "project": project.name,
                "session": transcript.stem,
                "time": reply[1],
                "ok": report["ok"],
                "violations": report["violations"],
                "warnings": report["warnings"],
            })
    return rows


def main(argv):
    args = list(argv[1:])
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    options = {"--since-minutes": "120", "--projects-dir": os.path.expanduser("~/.claude/projects")}
    while args:
        flag = args.pop(0)
        if flag not in options or not args:
            print(__doc__.strip())
            return 2
        options[flag] = args.pop(0)
    try:
        since = float(options["--since-minutes"])
    except ValueError:
        print(__doc__.strip())
        return 2
    rows = audit(options["--projects-dir"], since)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print("%s %s %s" % ("OK  " if row["ok"] else "FAIL", row["project"], row["session"][:8]))
            for violation in row["violations"]:
                print("     violation:", violation[:140])
            for warning in row["warnings"]:
                print("     warning:", warning[:140])
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
