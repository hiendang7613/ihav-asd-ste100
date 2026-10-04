"""Offline check of one reply against the ihav-asd-ste100 shape. No model call, no network.

Usage:
  python3 scripts/check_reply.py REPLY.md            # human-readable report
  python3 scripts/check_reply.py REPLY.md --json     # machine-readable report
  cat reply.md | python3 scripts/check_reply.py -    # read standard input

Exit code 0 when there is no violation, 1 otherwise. Warnings never fail the check.
The check covers what can be checked mechanically: the three zone labels and step lines, the conclusion part,
ASCII structure, exact English labels,
section order and indentation, bold-key sub-items, option markers, duplicate conclusions, emoji and square brackets,
sentence length, openers and closers.
It cannot judge meaning, accuracy or tone; a passing reply can still be wrong.

Any language: body text can use any language. Structural numbers, labels and colons stay in ASCII.
Length is counted in words for scripts with spaces and in characters (converted to word equivalents)
for scripts written without spaces.
"""

import json
import re
import sys

SECTIONS = {0: "Goals", 1: "Done", 2: "Doing", 3: "Todos", 4: "Pending", 5: "Quests", 6: "Risks", 7: "Ideas"}
GOALS, QUESTIONS, RISKS, IDEAS = 0, 5, 6, 7
# Numbered lists: Goals items are **L1.** (long-term aim), **G1.** (current goal) and **B1.** (deferred work);
# decision lists use **Q1.**, **R1.** and **I1.**.
ID_KEYS = {GOALS: "LGB", QUESTIONS: "Q", RISKS: "R", IDEAS: "I"}
MUST_CHOOSE = (RISKS, IDEAS)  # every risk and idea offers a choice
ALWAYS_SHOWN = tuple(SECTIONS)  # every section is shown; an empty one shows only its label
BAR_WIDTH = 10
# An L line opens with the agent's estimate and a bar, one # per 10 percent: **L1.** [~80%] [########--] | aim
L_PROGRESS = re.compile(r"^\[~([0-9]{1,3})%%\] \[([#-]{%d})\] \| \S" % BAR_WIDTH)
L_PROGRESS_LINE = re.compile(r"(?m)^(   [-*] \*\*L[0-9]+\.\*\* )\[~[0-9]{1,3}%%\] \[[#-]{%d}\]" % BAR_WIDTH)
MAX_STEP_WORDS = 16
MAX_CONCLUSION_WORDS = 25
MAX_SENTENCE_WORDS = 25
BODY_WORD_BUDGET = 250
SMALL_ANSWER_WORDS = 40
NO_SPACE_SCRIPTS = [  # (regex, characters per English-word equivalent); see docs/RESEARCH.md
    # About 1.5 Chinese characters carry one English word (translation ratio, Google Research 2007).
    (re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]"), 1.5),   # Japanese kana, Chinese and Japanese kanji
    # No published ratio found for these scripts; 4 characters per word is an unverified placeholder.
    (re.compile(r"[฀-๿຀-໿က-႟ក-៿]"), 4.0),   # Thai, Lao, Myanmar, Khmer
]
EMOJI = re.compile(r"[☀-➿⬀-⯿⌀-⏿\U0001F000-\U0001FAFF️]")
SENTENCE_END = r"(?<=[.!?。！？؟।])\s*"
CONCLUSION_LINE = re.compile(r"^\*\*([^*:\n]{1,30}):\*\*\s*(\S.*)$")
SECTION_LINE = re.compile(r"^([0-9])\.\s+\*\*([^*:\n]{1,30}):\*\*\s*(.*)$")
SECTION_CANDIDATE = re.compile(r"(?m)^\d+\.\s+\*\*[^*\n]{1,30}[:：]\*\*")
MALFORMED_CONCLUSION = re.compile(r"(?m)^\*\*Conclusion：\*\*")
FULLWIDTH_MARKER_LINE = re.compile(r"(?m)^\s*(?:[-*]\s+)?\*\*[^*\n]{1,40}：\*\*")
SUB_ITEM = re.compile(r"^\s{2,}[-*]\s+(.*)$")
BOLD_KEY = re.compile(r"^\*\*[^*:\n]{1,40}:\*\*(\s|$)")
OPTION_ITEM = re.compile(r"^(?:`<a>`|\([a-z]\))(?:\s|$)")
ID_CANDIDATE = re.compile(r"\*\*[QRI]\d+\.\*\*")
RECOMMENDED = "`<a>`"
ZONES = ("Agents-Zone", "Result-Zone", "Admin-Zone")
ZONE_LINE = re.compile(r"^\*\*(%s)\*\*\s*$" % "|".join(ZONES))
STEP_LINE = re.compile(r"^- (?:`(?:1[0-2]|[1-9]):[0-5][0-9] (?:AM|PM)` )?\S.* => \S")
TIME_LIKE = re.compile(r"^- `[^`]*\d:\d\d[^`]*`")
STEP_TIME = re.compile(r"^- `(?:1[0-2]|[1-9]):[0-5][0-9] (?:AM|PM)` ")
RESULT_BULLET = re.compile(r"^[-*]\s+(.*)$")
RESULT_KEY = re.compile(r"^(?:\*\*[^*\n]+\*\*|`[^`\n]+`)")
# A sentence ends where a Latin stop is followed by a space and a capital letter, or where a CJK stop is
# followed by more text. "e.g. this", "0.4.2" and "check_reply.py" do not end a sentence.
LATIN_STOP = re.compile(r"[.!?]\s+(\S)")
CJK_STOP = re.compile(r"[。！？]\s*\S")
ABBREVIATION = re.compile(r"(?:\b(?:[A-Za-z]\.){2,}|\b(?:vs|etc|cf|approx|incl|no|nr|mr|ms|dr|st)\.)$", re.I)
OPENERS = re.compile(r"^(great question|good question|sure[,!. ]|certainly|of course|let me |i'll |i will now|"
                     r"câu hỏi hay|tuyệt|để tôi |chắc chắn rồi)", re.I)
CLOSERS = re.compile(r"(hope this helps|let me know if|feel free to|happy to help|hy vọng (điều này|giúp)|"
                     r"cứ hỏi nếu|đừng ngần ngại)", re.I)


def units(text):
    """Length in word equivalents: words for spaced scripts, characters divided by a ratio for unspaced scripts."""
    count = 0.0
    for token in text.split():
        for pattern, ratio in NO_SPACE_SCRIPTS:
            chars = len(pattern.findall(token))
            if chars:
                count += chars / ratio
                token = pattern.sub("", token)
        if re.search(r"\w", token):
            count += 1
    return round(count, 1)


def fenced_blocks(text):
    """Yield root-level fenced ranges and payloads; no Markdown dependency.

    Tildes/backticks need at least three markers. A closing fence uses the same
    marker and at least the opening length. An unclosed block reaches EOF.
    This is a fence scanner, not a full Markdown/list-container parser.
    """
    opening = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if opening is None:
            match = re.match(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)", line)
            if match and not (match[1][0] == '`' and '`' in match[2]):
                opening = (offset, offset + len(line), match[1][0], len(match[1]))
        else:
            start, payload, marker, length = opening
            if re.fullmatch(r" {0,3}" + re.escape(marker) + r"{%d,}[ \t]*" % length, line.rstrip('\r\n')):
                yield start, offset + len(line), text[payload:offset]
                opening = None
        offset += len(line)
    if opening is not None:
        yield opening[0], len(text), text[opening[1]:]


def strip_code(text):
    return mask_code(text)


def sentences(text):
    plain = re.sub(r"`[^`]*`", "X", strip_code(text))
    plain = re.sub(r"(?m)^\s*(?:[-*•]|\d+[.)]|#+)\s+", "", plain)
    parts = re.split(SENTENCE_END + r"|\n+", plain)
    return [p.strip() for p in parts if units(p) >= 3]


def sentence_count(line):
    """Sentences in one line. Inline code counts as a lowercase word, and a stop that ends an abbreviation
    such as e.g. or vs. does not end the sentence."""
    plain = re.sub(r"`[^`]*`", "x", line).strip()
    breaks = sum(match.group(1).isupper() and not ABBREVIATION.search(plain[:match.start() + 1])
                 for match in LATIN_STOP.finditer(plain))
    return 1 + breaks + len(CJK_STOP.findall(plain)) if plain else 0


def split_reply(text):
    """Return (body, conclusion_label, conclusion_text, sections, layout_problems). sections is a list of
    (number, label, text, sub_items). The conclusion part is the last bold-label line, one blank line,
    then a numbered list whose items start with a bold label. When the user asked for the conclusion
    first, the Conclusion line opens the reply and the numbered list still ends it."""
    lines = text.rstrip().splitlines()
    index = len(lines) - 1
    tail = []
    while index >= 0 and (not lines[index].strip() or SECTION_LINE.match(lines[index])
                          or SUB_ITEM.match(lines[index])):
        tail.insert(0, lines[index])
        index -= 1
    conclusion = CONCLUSION_LINE.match(lines[index].strip()) if index >= 0 else None
    has_sections = any(SECTION_LINE.match(line) for line in tail)
    body_lines = lines[:index]
    top = next((i for i, line in enumerate(lines[:index]) if line.strip()), None)
    if not conclusion and has_sections and top is not None and CONCLUSION_LINE.match(lines[top].strip()):
        conclusion = CONCLUSION_LINE.match(lines[top].strip())
        body_lines = lines[top + 1:index + 1]
    if not conclusion or (any(line.strip() for line in tail) and not has_sections):
        return text, None, None, [], []
    problems = []
    if not tail or tail[0].strip():
        problems.append("Put one blank line between the Conclusion line and the list, or the list merges into it.")
    items = [line for line in tail[1:]]
    first = next((i for i, line in enumerate(items) if line.strip()), None)
    if first is not None and any(not line.strip() for line in items[first:]):
        problems.append("Write the sections without blank lines between them.")
    sections = []
    for line in tail:
        match = SECTION_LINE.match(line)
        if match:
            sections.append((int(match.group(1)), match.group(2).strip(), match.group(3).strip(), []))
        elif SUB_ITEM.match(line) and sections:
            sections[-1][3].append(line)
    return "\n".join(body_lines), conclusion.group(1).strip(), conclusion.group(2).strip(), sections, problems


def item_problems(number, sub_items):
    """Each top-level item in a section starts with a bold key; in a decision list the key is its ID: **Q1.**, **R1.**, **I1.**"""
    letters = ID_KEYS.get(number)
    key = re.compile(r"^\*\*[%s][0-9]+\.\*\*\s" % letters) if letters else BOLD_KEY
    shown = " or ".join("**%s1.**" % letter for letter in letters) if letters else "**Key:**"
    return ["Section %d item must start with %s: %s..." % (number, shown, item[:30])
            for item in (SUB_ITEM.match(line).group(1) for line in sub_items
                         if len(line) - len(line.lstrip()) <= 3) if not key.match(item)]


def question_problems(number, sub_items):
    """Each decision item with two or more options needs exactly one recommended option. Options are deeper
    sub-items, or one sub-item that lists them with " | ". Risks and ideas must offer a choice."""
    problems = []
    groups = []
    for line in sub_items:
        indent = len(line) - len(line.lstrip())
        item = SUB_ITEM.match(line).group(1)
        if indent <= 3:
            groups.append((item, []))
        elif groups:
            groups[-1][1].append(item)
    for question, options in groups:
        choices = [part for option in options for part in option.split(" | ")]
        if number in MUST_CHOOSE and len(choices) < 2:
            problems.append("Item '%s' needs a choice line: `<a>` ... | (b) ... | (c) ..." % question[:30])
        if len(choices) >= 2:
            marked = sum(RECOMMENDED in choice for choice in choices)
            if marked != 1:
                problems.append("Question '%s' has %d options marked `<a>` (need exactly 1)." % (question[:30], marked))
    return problems


def indentation_problems(number, sub_items):
    """Require three spaces for keyed section items and five for option markers."""
    letters = ID_KEYS.get(number)
    key = re.compile(r"^\*\*[%s][0-9]+\.\*\*\s" % letters) if letters else BOLD_KEY
    problems = []
    for line in sub_items:
        indent = len(line) - len(line.lstrip())
        item = SUB_ITEM.match(line).group(1)
        if indent < 3 or indent % 2 == 0:
            problems.append("Section %d list indentation must use 3 spaces, then add 2 per nested level." % number)
        if key.match(item) and indent != 3:
            problems.append("Top-level items in section %d must be indented exactly 3 spaces." % number)
        if OPTION_ITEM.match(item) and indent != 5:
            problems.append("Options in section %d must be indented exactly 5 spaces." % number)
    return problems


def numbering_problems(number, sub_items):
    """Q, R and I items restart at 1 in every reply, so a short answer such as Q1.a always means the latest reply.
    L, G and B keep stable IDs across replies and are not checked here."""
    letter = ID_KEYS[number]
    found = [int(match.group(1)) for match in (re.match(r"^\*\*%s([0-9]+)\.\*\*" % letter, SUB_ITEM.match(line).group(1))
                                               for line in sub_items if len(line) - len(line.lstrip()) <= 3) if match]
    if found != list(range(1, len(found) + 1)):
        return ["Section %d numbers %s; number %s items from %s1 in every reply, in order."
                % (number, ", ".join("%s%d" % (letter, n) for n in found), letter, letter)]
    return []


def goal_problems(sub_items):
    """Goals lists L, then G, then B lines. Only the user sets L aims; each L line opens with the agent's estimate
    and a bar, one # per 10 percent. G and B lines are plain text: no bar, no percent and no link."""
    problems, goals, order = [], [], []
    for line in sub_items:
        if len(line) - len(line.lstrip()) > 3:
            continue
        match = re.match(r"^\*\*([LGB])([0-9]+)\.\*\*\s+(.*)$", SUB_ITEM.match(line).group(1))
        if match:
            goals.append(match.groups())
            order.append("LGB".index(match.group(1)))
    if order != sorted(order):
        problems.append("Goals lists L lines, then G lines, then B lines.")
    for letter, number, text in goals:
        if letter != "L":
            if re.search(r"[#-]{%d}|%%|->\s*L[0-9]" % BAR_WIDTH, text):
                problems.append("%s%s is plain text: no bar, percent or link." % (letter, number))
            continue
        progress = L_PROGRESS.match(text)
        if not progress:
            problems.append("L%s opens with [~80%%] [########--] | then the aim." % number)
            continue
        percent, bar = int(progress.group(1)), progress.group(2)
        filled = bar.count("#")
        if percent > 100:
            problems.append("L%s estimate is %d%%; use 0 to 100." % (number, percent))
        elif bar != "#" * filled + "-" * (BAR_WIDTH - filled) or filled not in (int(percent / 10 + 0.5), round(percent / 10)):
            expected = int(percent / 10 + 0.5)
            problems.append("L%s bar must be %s for ~%d%%." % (number, "#" * expected + "-" * (BAR_WIDTH - expected), percent))
    return problems


def goals_progress_removed(text):
    """Remove the [~80%] [########--] prefix from L lines inside the Goals section only, the one place brackets are allowed."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(r"^0\.\s+\*\*Goals:\*\*", line)), None)
    if start is None:
        return text
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^[0-9]\.\s", lines[i])), len(lines))
    lines[start + 1:end] = [L_PROGRESS_LINE.sub(r"\1", line) for line in lines[start + 1:end]]
    return "\n".join(lines)


def step_warnings(text):
    """Agents-Zone lines stay short: about 12 words, warned above MAX_STEP_WORDS. A code span counts as one word."""
    lines = mask_code(text).splitlines()
    labels = [index for index, line in enumerate(lines) if ZONE_LINE.match(line)]
    names = [ZONE_LINE.match(lines[index]).group(1) for index in labels]
    if names[:2] != ["Agents-Zone", "Result-Zone"]:
        return []
    warnings = []
    for line in lines[labels[0] + 1:labels[1]]:
        words = units(re.sub(r"`[^`]*`", "x", line[2:]))
        if line.strip() and words > MAX_STEP_WORDS:
            warnings.append("Agents-Zone line has %g words (target about 12): %s..." % (words, line[:40]))
    return warnings


def duplicate_items(sections):
    """An item belongs in one section only; the same bold key in two sections is likely one item listed twice."""
    seen, warnings = {}, []
    for number, _, _, subs in sections:
        for line in subs:
            if len(line) - len(line.lstrip()) > 3:
                continue
            key = BOLD_KEY.match(SUB_ITEM.match(line).group(1))
            if not key:
                continue
            name = key.group(0).strip().strip("*:：").casefold()
            if name in seen and seen[name] != number:
                warnings.append("Item '%s' appears in sections %d and %d; put each item in one section only."
                                % (name, seen[name], number))
            seen.setdefault(name, number)
    return warnings


def mask_code(text):
    """Blank out fenced code but keep its line count, so line numbers still match the reply."""
    parts, previous = [], 0
    for start, end, _ in fenced_blocks(text):
        parts.extend((text[previous:start], '\n' * text[start:end].count('\n')))
        previous = end
    return ''.join(parts) + text[previous:]


def zone_problems(text):
    """The full format has three labelled zones: Agents-Zone (one line per step: `4:43 PM` why => what),
    Result-Zone (the key-first body) and Admin-Zone (the Conclusion and the eight sections).
    An "adminzone" reply has the Admin-Zone alone."""
    lines = mask_code(text).splitlines()
    zones = [(index, ZONE_LINE.match(line).group(1)) for index, line in enumerate(lines) if ZONE_LINE.match(line)]
    if [name for _, name in zones] == ["Admin-Zone"]:
        # "adminzone" asks for the Admin-Zone alone: its label, the Conclusion line and the eight sections.
        if any(line.strip() for line in lines[:zones[0][0]]):
            return ["An Admin-Zone-only reply starts with **Admin-Zone**; a full reply has all three zones."]
        agents = result = admin = zones[0][0]
    elif [name for _, name in zones] != list(ZONES):
        return ["Write the three zone labels once each, in order, on their own lines: **Agents-Zone**, "
                "**Result-Zone**, **Admin-Zone**."]
    else:
        agents, result, admin = (index for index, _ in zones)
    problems = []
    for index, name in zones:
        if index > 0 and lines[index - 1].strip():
            problems.append("Put a blank line before **%s**, or it merges into the line above." % name)
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if following.strip() and not re.match(r"\s*(?:[-*]|\d+\.)\s", following):
            problems.append("After **%s**, start a list or leave a blank line; plain text would join the label." % name)
    for line in (line for line in lines[agents + 1:result] if line.strip()):
        if not STEP_LINE.match(line) or (TIME_LIKE.match(line) and not STEP_TIME.match(line)):
            problems.append("Agents-Zone lines are '- `4:43 PM` why => what' (time only from a real clock): %s" % line[:40])
    for line in lines[result + 1:admin]:
        bullet = RESULT_BULLET.match(line)
        if bullet and not RESULT_KEY.match(bullet.group(1)):
            problems.append("Result-Zone bullets start with a bold key or a code path: %s" % line[:40])
    after = [line for line in lines[admin + 1:] if line.strip()]
    if admin + 1 < len(lines) and lines[admin + 1].strip():
        problems.append("Put a blank line after **Admin-Zone**.")
    if not after or not (CONCLUSION_LINE.match(after[0].strip()) or SECTION_LINE.match(after[0])):
        problems.append("**Admin-Zone** must be followed by the Conclusion line, then the eight sections.")
    return problems


def check(text):
    body, conclusion_label, conclusion, sections, layout = split_reply(text)
    words = units(strip_code(text))
    violations, warnings = [], []

    if conclusion is None:
        outside_code = strip_code(text)
        if SECTION_CANDIDATE.search(outside_code) or MALFORMED_CONCLUSION.search(outside_code):
            violations.append("No valid Conclusion part was found for the attempted section format.")
        elif words > SMALL_ANSWER_WORDS:
            violations.append("No conclusion part at the end of a reply longer than %d words." % SMALL_ANSWER_WORDS)
    else:
        if conclusion_label != "Conclusion":
            violations.append("The conclusion label must be exactly 'Conclusion'; found '%s'." % conclusion_label)
        if units(conclusion) > MAX_CONCLUSION_WORDS:
            violations.append("The Conclusion line has %g words (limit %d)." % (units(conclusion), MAX_CONCLUSION_WORDS))
        if sentence_count(conclusion) > 1:
            violations.append("The Conclusion line has %d sentences; write one." % sentence_count(conclusion))
        numbers = [number for number, _, _, _ in sections]
        missing = [n for n in ALWAYS_SHOWN if n not in numbers]
        if missing:
            violations.append("Sections %s must be shown; an empty one shows only its label." % ", ".join(str(n) for n in missing))
        if numbers != sorted(set(numbers)) or any(n not in SECTIONS for n in numbers):
            violations.append("Sections must be numbered 0 to 7, in order, each once; found %s." % numbers)
        violations.extend(layout)
        for number, label, line, subs in sections:
            if number in SECTIONS and label != SECTIONS[number]:
                violations.append("Section %d label must be '%s'; found '%s'." % (number, SECTIONS[number], label))
            if line.strip():
                violations.append("Section %d must show its label only on its line; write each item below it as a "
                                  "sub-item that starts with a bold key." % number)
            violations.extend(item_problems(number, subs))
            violations.extend(indentation_problems(number, subs))
            if number in (QUESTIONS, RISKS, IDEAS):
                violations.extend(question_problems(number, subs))
                violations.extend(numbering_problems(number, subs))
            if number == GOALS:
                violations.extend(goal_problems(subs))
        warnings.extend(duplicate_items(sections))
        goals = next((subs for number, _, _, subs in sections if number == GOALS), None)
        if goals is not None and not any(re.match(r"^\s{3}[-*]\s+\*\*L[0-9]+\.\*\*", line) for line in goals):
            warnings.append("Goals has no L line; ask the user for a long-term aim in Quests.")
        violations.extend(zone_problems(text))
        warnings.extend(step_warnings(text))

    outside_code = goals_progress_removed(re.sub(r"`[^`]*`", "", strip_code(text)))
    section_candidates = [line for line in strip_code(text).splitlines() if SECTION_CANDIDATE.match(line)]
    if any(not line.split(".", 1)[0].isascii() for line in section_candidates):
        violations.append("Section numbers and structural colons must use ASCII.")
    if FULLWIDTH_MARKER_LINE.search(strip_code(text)):
        violations.append("Bold structural labels and keys must use an ASCII colon.")
    if any(not match.group()[2:-2].isascii() for match in ID_CANDIDATE.finditer(outside_code)):
        violations.append("Q, R and I IDs must use ASCII digits.")
    if len(re.findall(r"\*\*Conclusion:\*\*", outside_code)) > 1:
        violations.append("A reply must not contain more than one Conclusion marker.")
    if EMOJI.search(outside_code):
        violations.append("The reply contains emoji; write status in words.")
    if re.search(r"\*\*\[|^[-*]\s+\[[^\]]+\]", outside_code, re.M):
        violations.append("Labels use square brackets; write bold labels without them.")
    elif re.search(r"[\[\]]", outside_code):
        violations.append("The reply uses square brackets outside code; use words or a code span.")
    if any(re.search(r"(?m)^\d\.\s+\*\*[^*]+:\*\*", payload)
           for _, _, payload in fenced_blocks(text)):
        violations.append("The conclusion part is inside a code block; the reader would see raw markers.")

    body_sentences = sentences(body)
    for sentence in (s for s in body_sentences if units(s) > MAX_SENTENCE_WORDS):
        warnings.append("Long sentence (%g words): %s..." % (units(sentence), sentence[:60]))
    body_words = units(strip_code(body))
    if conclusion is not None and body_words > BODY_WORD_BUDGET:
        warnings.append("Body has %g words (target about %d); trim optional detail, keep every needed fact."
                        % (body_words, BODY_WORD_BUDGET))
    first = next((line for line in strip_code(body).splitlines() if line.strip() and not ZONE_LINE.match(line)
                  and not STEP_LINE.match(line)), conclusion or "")
    if OPENERS.match(re.sub(r"^[#*\s-]+", "", first)):
        violations.append("The reply opens with a filler opener: %s..." % first[:40])
    if body_sentences and CLOSERS.search(body_sentences[-1]):
        violations.append("The body ends with a closing pleasantry: %s..." % body_sentences[-1][:40])

    return {
        "ok": not violations,
        "violations": violations,
        "warnings": warnings,
        "stats": {
            "words": words,
            "body_words": body_words,
            "conclusion_words": units(conclusion) if conclusion else 0,
            "sections": [number for number, _, _, _ in sections],
            "longest_sentence": max((units(s) for s in body_sentences), default=0),
        },
    }


def main(argv):
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__.strip())
        return 2
    text = sys.stdin.read() if argv[1] == "-" else open(argv[1], encoding="utf-8").read()
    report = check(text)
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("OK" if report["ok"] else "FAIL")
        for item in report["violations"]:
            print("violation:", item)
        for item in report["warnings"]:
            print("warning:", item)
        print("stats:", json.dumps(report["stats"], ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
