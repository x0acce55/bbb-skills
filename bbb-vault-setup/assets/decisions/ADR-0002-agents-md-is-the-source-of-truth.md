---
type: adr
status: accepted
summary: All agent instructions live in AGENTS.md; CLAUDE.md imports it and holds only Claude-specific additions.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0002: AGENTS.md is the instruction source of truth

## Context

The vault should not be tied to one agent. Claude Code reads `CLAUDE.md` and does not
read `AGENTS.md`, so a vault whose instructions live only in `AGENTS.md` would be
invisible to it.

## Decision

All substance goes in `AGENTS.md` at the vault root. `CLAUDE.md` consists of an
`@AGENTS.md` import plus a short section for behaviour unique to Claude Code. Anything
another agent would also need goes above the line, in `AGENTS.md`.

## Rejected

**Symlinking `CLAUDE.md` to `AGENTS.md`.** Works on Unix, but on Windows creating a
symlink requires Administrator privileges or Developer Mode, and it leaves nowhere to
put Claude-specific instructions.

**Duplicating the content into both files.** Two files to keep in sync, and no rule for
which one wins when they disagree.

**`CLAUDE.md` only.** Simplest, but forecloses the agent-agnostic goal, which the user
stated explicitly.

## Consequences

Adding a Claude-specific instruction requires deciding whether it is genuinely
Claude-specific. That friction is intentional; without it everything drifts below the
import over time and the agnosticism is nominal.
