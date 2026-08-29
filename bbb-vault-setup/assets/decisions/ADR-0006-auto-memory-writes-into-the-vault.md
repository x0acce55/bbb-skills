---
type: adr
status: superseded
summary: Claude Code's auto memory is redirected into the vault's memories/ directory via autoMemoryDirectory.
up: "[[decisions]]"
scope: foundational
affects: []
superseded_by: ADR-0009
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0006: Auto memory writes into the vault

> **Superseded by [[ADR-0009-per-machine-memory-buffers]].** The decision to put auto
> memory in the vault stands; scoping it to a shared directory did not. Left unedited
> because the ledger records what was believed at the time.

## Context

Claude Code maintains its own memory, writing a `MEMORY.md` index and topic files. By
default these go to `~/.claude/projects/<project>/memory/`, machine-local and outside
the vault. A second brain with an agent's accumulated knowledge stored somewhere the
user never looks is a second brain with a hole in it.

## Decision

Set `autoMemoryDirectory` in `.claude/settings.json` to the vault's `memories/`
directory. Claude writes markdown there; Obsidian indexes it; the user can read and edit
it like any other note.

`memories/` is distinguished from `context/` by authorship and reliability: `context/`
is asserted by the user and treated as true, `memories/` is observed by an agent and
treated as evidence.

## Rejected

**Leaving auto memory at its default location.** Keeps the vault clean, but splits the
second brain across two places, one of which is invisible.

**Disabling auto memory and having agents write notes into `memories/` manually.**
Loses the automatic accumulation, which is the feature's entire value.

**Folding `memories/` into `context/`.** Rejected because it destroys the distinction
between what the user asserted and what an agent inferred. A wrong memory sitting in a
file labelled always-true is exactly the failure worth designing against.

## Consequences

`memories/` uses `MEMORY.md` rather than a note named after its folder, breaking the
index-note convention. Exempted deliberately rather than fighting the tool.

Auto memory is designed to be machine-local. If this vault ever syncs to a second
machine, two Claude Code installations will write the same `MEMORY.md` and conflict.

**Open:** does this vault sync to any other device? If yes, this ADR needs revisiting
before that happens, not after.

`MEMORY.md` is seeded with frontmatter, because Claude Code adds a `modified` timestamp
only to memory files that already have some, and never adds frontmatter to a file
without it.
