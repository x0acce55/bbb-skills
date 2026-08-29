---
type: adr
status: accepted
summary: The home note is always BBB.md, regardless of the vault folder's name, because the folder name is machine-local and the note is synced.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0015: The home note is pinned to `BBB.md`

> **Ledger note.** Numbered into the gap left by two records lost before first
> deployment (see ADR-0014's note). This records a decision made during the
> pre-deployment review, replacing a shipped behaviour that was found broken.

## Context

The skill originally instructed renaming `BBB.md` after the vault folder — the
folder-note convention applied to the root. But the vault folder's name is a
machine-local property: the same synced vault sat in a folder named `BBB` on
one machine and `big-beautiful-brain` on another. The home note is a synced
file with exactly one name, so a name derived from the folder is wrong on every
machine but the one that scaffolded first.

Meanwhile the templates, `AGENTS.md`, and several ADR bodies hardcode
`[[BBB]]`. A test scaffold with any other home-note name produced broken links
immediately, and `build_index.py` / `health_report.py` each carried a
two-candidate lookup to paper over the ambiguity.

## Decision

The home note is `BBB.md`, always, on every machine, regardless of what the
vault folder is called. The scripts look for exactly that name and the rename
instruction is removed from the skill.

## Rejected

**Rename per vault folder (the shipped behaviour).** Broken by construction
for a synced vault, as above.

**Parameterising the home-note name through every template, script, and
link.** A configuration knob whose only effect is letting the vault's most
linked-to note have an unstable name. All cost, no benefit.

**A folder-note plugin convention.** Renders only in Obsidian; invisible to an
agent reading files, which fails the ADR-0003 test.

## Consequences

The vault folder can be renamed or moved freely — including fixing the
misspelled `big-beatiful-brain` parent from ADR-0008's Open marker — without
touching a single note. That Open marker is resolved: the path is now
cosmetic.

`BBB.md` at the root of any folder is also how tooling recognises "this is the
vault," which simplifies multi-vault detection (ADR-0019).
