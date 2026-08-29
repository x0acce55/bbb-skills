---
type: adr
status: accepted
summary: Agents append to existing notes and update frontmatter rather than creating new files by default.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0011: Append before you create

## Context

An agent working in a notes vault will, left to itself, create a new file for every new
piece of information. That is the path of least resistance and it produces a vault of
hundreds of thin notes.

The cost compounds against the rest of this design. Every file is an index entry, an
`up:` link, a summary to keep honest, and a candidate for a duplicate basename that
breaks Obsidian's vault-global link resolution. The frontmatter index only stays useful
while summaries describe meaningfully different things — a hundred near-identical
summaries index nothing.

## Decision

Before creating a note, check the folder index for an existing note whose `summary`
already covers the topic. If one exists, append a dated section and update `summary` and
`updated`. Create a new file only when the topic genuinely doesn't fit under any
existing summary.

The same applies to frontmatter fields: update the existing schema rather than inventing
fields per file. A new field is a conventions change and belongs in an ADR.

This is written into `AGENTS.md` so it applies to every agent, not just Claude Code.

## Rejected

**No guidance, letting file granularity emerge.** What produces the two-hundred-thin-notes
outcome.

**A hard cap on notes per folder.** Arbitrary, and it pushes toward splitting folders
rather than consolidating notes.

**Requiring approval before any file creation.** Too much friction for a tool meant to
capture things quickly.

## Consequences

Notes grow long over time and will occasionally need splitting. That is a better problem
than sprawl: splitting is a deliberate act with an obvious trigger, whereas sprawl is
invisible until navigation has already degraded.

"Genuinely doesn't fit" is a judgment call, so agents will sometimes get it wrong in
both directions. The check is the folder index — if two summaries describe the same
thing, the notes should be one note.
