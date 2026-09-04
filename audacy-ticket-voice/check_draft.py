#!/usr/bin/env python3
"""Lint a ticket/MR draft against Josiah's measured voice.

Usage:
    python check_draft.py draft.md          # ordinary reply (strict formatting)
    python check_draft.py draft.md --long   # long technical sign-off (structure allowed)
    cat draft.md | python check_draft.py -

Exit 0 when clean, 1 when anything is flagged. This is a linter, not a judge: a flag you
can justify is fine. The rules and the evidence behind them are in the vault note
projects/audacy/ticket-voice.md.
"""
import re
import sys

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")

# Phrases that offer his time or availability. He writes these himself when he chooses;
# an agent writing one commits him to work he has not agreed to. Always flagged.
OFFERS = [
    "happy to", "let me know", "feel free", "reach out to me", "ping me",
    "i can help", "i can write", "i'm available", "im available", "glad to",
    "standing by", "if you need anything", "don't hesitate", "dont hesitate",
    "i'd be happy", "id be happy", "just ask", "shout if",
]

# Wrapper he strips from agent drafts: meta-commentary, appeals to authority,
# reassurance, and restating the other person's position before answering.
WRAPPER = [
    ("that's the actual fix", "narrating your own argument"),
    ("thats the actual fix", "narrating your own argument"),
    ("everything below is", "narrating your own argument"),
    ("the real issue here is", "narrating your own argument"),
    ("to be clear,", "narrating your own argument"),
    ("it's the role google lists", "appeal to authority"),
    ("google recommends", "appeal to authority"),
    ("aws recommends", "appeal to authority"),
    ("best practice is", "appeal to authority"),
    ("not more", "reassurance clause"),
    ("rest assured", "reassurance clause"),
    ("nothing to worry about", "reassurance clause"),
    ("as you said", "restating their position back at them"),
    ("as you mentioned", "restating their position back at them"),
    ("you're right that", "restating their position back at them"),
    ("agreed that", "restating their position back at them"),
]

APPROVAL_WORDS = re.compile(r"\b(approval|sign[- ]?off|signoff|sponsor)\b", re.I)
# A named approver is an @mention or a capitalised full name. Case matters here, so this
# pattern must NEVER carry re.I -- IGNORECASE would make [A-Z] match lowercase and the
# check would silently pass on every draft.
NAMED_PERSON = re.compile(r"@\w|\b[A-Z][a-z]+ [A-Z][a-z]+\b")
# A role class is a fine substitute for a name, and this one is case-insensitive.
NAMED_ROLE = re.compile(
    r"\b(manager|supervisor|director|senior management|leadership|data owner|"
    r"system owner|account owner|his manager|her manager|their manager)\b", re.I)


def names_an_approver(text):
    return bool(NAMED_PERSON.search(text) or NAMED_ROLE.search(text))


def check(text, long_form=False):
    flags = []
    warn = []
    body = text.strip()
    low = body.lower()

    if not body:
        return ["draft is empty"], []

    # --- always-on rules -------------------------------------------------
    for phrase in OFFERS:
        if phrase in low:
            flags.append(f"closing offer: {phrase!r} — never offer his time in a draft")

    for phrase, why in WRAPPER:
        if phrase in low:
            flags.append(f"{why}: {phrase!r}")

    if APPROVAL_WORDS.search(body) and not names_an_approver(body):
        flags.append(
            "asks for an approval without naming who gives it — in four years he has "
            "never written a bare 'needs an approval'")

    # --- formatting: ordinary register only ------------------------------
    if not long_form:
        n = body.count("—")
        if n:
            flags.append(f"{n} em-dash(es) — he has used one zero times in 4 years; use --")
        if EMOJI.search(body):
            flags.append("emoji — only ever appeared in an agent-drafted thread")
        if re.search(r"^\s{0,3}#{1,6}\s", body, re.M):
            flags.append("markdown header — not in an ordinary reply")
        if re.search(r"\*\*[^*\n]{2,}\*\*", body):
            flags.append("bold run used as a pseudo-header — he strips these")

    # --- shape -----------------------------------------------------------
    words = len(body.split())
    limit = 400 if long_form else 60
    if words > limit:
        warn.append(f"{words} words, over the ~{limit} guide for this register")

    if not body.lstrip().startswith("@"):
        warn.append("does not open with an @mention of whoever owes the next action "
                    "(66% of his comments do)")

    if "?" not in body and not re.search(r"secops (approves|is ok|is good|has no issue|"
                                         r"signs off|does not approve)", low):
        warn.append("neither asks a question nor states a SecOps position — most of his "
                    "comments do one or the other")

    return flags, warn


def main():
    args = [a for a in sys.argv[1:]]
    long_form = "--long" in args
    args = [a for a in args if a != "--long"]
    if not args:
        print(__doc__.strip())
        return 2
    src = args[0]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()

    flags, warn = check(text, long_form)
    register = "long technical sign-off" if long_form else "ordinary reply"
    print(f"register: {register}\n")
    for f in flags:
        print(f"  FLAG  {f}")
    for w in warn:
        print(f"  warn  {w}")
    if not flags and not warn:
        print("  clean")
    print()
    if flags:
        print("Fix the FLAGs or be able to say why each one is right here.")
    print("Then re-read the draft for invented role names, project ids, or approvers.")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
