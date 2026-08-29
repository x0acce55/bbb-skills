#!/usr/bin/env python3
"""Unit tests for parse_frontmatter.

Plain asserts, no pytest -- these must run on a fresh box with nothing
installed, same constraint as the parser itself.

    python test_frontmatter.py

The cases that matter most are the block-style lists, because that is what
Obsidian's Properties UI writes. Before this parser handled them, a single
list-property edit made in Obsidian read back as empty -- and because notes'
`decisions:` fields are authoritative (ADR-0016), build_index then regenerated
the ADR's `affects:` to empty. An unreadable field wasn't a display bug; it was
data loss on the next index run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_index import parse_frontmatter  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got == want:
        print(f"  ok    {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}\n        want: {want!r}\n        got:  {got!r}")


def fm(body):
    return parse_frontmatter(body)


# --- scalars -----------------------------------------------------------------

check(
    "plain scalar",
    fm("---\ntype: note\n---\nx")["type"],
    "note",
)
check(
    "quoted scalar keeps inner value",
    fm('---\nup: "[[BBB]]"\n---\nx')["up"],
    "[[BBB]]",
)
check(
    "scalar containing a colon splits on the first colon only",
    fm("---\nsummary: benchmarks: bge-m3 won\n---\nx")["summary"],
    "benchmarks: bge-m3 won",
)
check(
    "empty value with no items stays empty string",
    fm("---\nsummary:\ncreated: 2026-08-25\n---\nx")["summary"],
    "",
)

# --- inline lists (the shape the templates ship with) -------------------------

check(
    "inline list",
    fm("---\ndecisions: [ADR-0004, ADR-0012]\n---\nx")["decisions"],
    ["ADR-0004", "ADR-0012"],
)
check(
    "inline list with quoted wikilinks",
    fm('---\naffects: ["[[a]]", "[[b]]"]\n---\nx')["affects"],
    ["[[a]]", "[[b]]"],
)
check(
    "empty inline list",
    fm("---\naffects: []\n---\nx")["affects"],
    [],
)

# --- block lists (the shape Obsidian's Properties UI writes) ------------------

OBSIDIAN = """---
type: note
summary: Test note
up: "[[alpha]]"
decisions:
  - ADR-0004
  - ADR-0012
tags:
  - research
  - "quoted tag"
created: 2026-08-25
---
body
"""
parsed = fm(OBSIDIAN)
check("block list: decisions", parsed["decisions"], ["ADR-0004", "ADR-0012"])
check("block list: tags with quoted item", parsed["tags"], ["research", "quoted tag"])
check("scalar after a block list still parses", parsed["created"], "2026-08-25")
check("scalar before a block list untouched", parsed["up"], "[[alpha]]")

check(
    "block list of quoted wikilinks",
    fm('---\naffects:\n  - "[[projects/audacy/podcast]]"\n---\nx')["affects"],
    ["[[projects/audacy/podcast]]"],
)
check(
    "tab-indented block item",
    fm("---\ndecisions:\n\t- ADR-0001\n---\nx")["decisions"],
    ["ADR-0001"],
)
check(
    "bare dash item is skipped, key stays empty",
    fm("---\ndecisions:\n  -\n---\nx")["decisions"],
    "",
)

# --- things outside the schema must not crash or pollute ----------------------

check(
    "nested map is skipped, key reads empty",
    fm("---\nmeta:\n  owner: me\nsummary: s\n---\nx")["meta"],
    "",
)
check(
    "nested map does not eat the following key",
    fm("---\nmeta:\n  owner: me\nsummary: s\n---\nx")["summary"],
    "s",
)
check(
    "comment lines are ignored",
    fm("---\n# a comment\ntype: adr\n---\nx")["type"],
    "adr",
)
check(
    "indented item with no open list key is ignored",
    fm("---\ntype: note\nsummary: s\n---\nx\n"),
    {"type": "note", "summary": "s"},
)
check("no frontmatter at all", fm("just a body"), {})
check("unterminated frontmatter", fm("---\ntype: note\nno end"), {})
check(
    "CRLF line endings",
    fm("---\r\ndecisions:\r\n  - ADR-0001\r\n---\r\nx")["decisions"],
    ["ADR-0001"],
)
check(
    "scalar followed by stray list items keeps the scalar",
    fm("---\nstatus: active\n  - stray\n---\nx")["status"],
    "active",
)

print()
if FAILURES:
    print(f"{len(FAILURES)} test(s) FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("All frontmatter tests passed.")
