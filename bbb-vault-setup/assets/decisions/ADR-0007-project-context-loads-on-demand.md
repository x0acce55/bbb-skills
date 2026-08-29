---
type: adr
status: accepted
summary: Each project folder holds a one-line CLAUDE.md importing its index note, so project context loads on directory read rather than at session start.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0007: Project context loads on demand

## Context

`context/` is meant to grow over time. But `@path` imports do not save context —
imported files are expanded inline at launch — so a growing `context/` imported at the
root gets more expensive every session, forever, and larger instruction files are
followed less reliably.

Separately, Claude Code discovers `CLAUDE.md` files in subdirectories below the working
directory and loads them when it reads files in that directory, rather than at launch.

## Decision

Two tiers.

Root `AGENTS.md` imports only the small, stable core of `context/` and *describes* the
rest so an agent knows to go read it on demand.

Each project folder contains a `CLAUDE.md` whose entire contents are `@<project>.md`.
The project's index note becomes its context exactly when an agent starts working in
that folder, and costs nothing otherwise. This is also what the user wanted the index
note to be — the folder's context — so the loading mechanism and the intent coincide.

## Rejected

**Importing everything from root.** Simple, and it makes every session progressively
more expensive while degrading adherence. This is the failure mode the ADR exists to
avoid.

**`.claude/rules/` with `paths:` frontmatter for per-project context.** A genuine third
option, offering finer scoping than per-directory. Held in reserve: if per-folder
`CLAUDE.md` turns out too coarse, this is the next move.

**Per-folder `AGENTS.md` alongside per-folder `CLAUDE.md`.** More agent-agnostic in
form, but doubles the config files in every project folder of a notes vault. Rejected
because the per-folder `CLAUDE.md` contains no instructions — only a pointer — so the
substance still lives in the index note, which any agent can read. Agnosticism is
preserved where it matters.

## Consequences

A `CLAUDE.md` appears in every project folder and is visible in Obsidian's file
explorer. Small, one line, and can be excluded from Obsidian search if it becomes noise.

An agent that never opens a file in a project folder never sees that project's context.
This is the intended behaviour and occasionally the surprising one.
