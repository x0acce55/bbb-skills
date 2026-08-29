---
type: adr
status: accepted
summary: Folder index notes are generated from the frontmatter of the folder's contents, making the no-orphans invariant true by construction.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0004: Index notes are generated, not hand-maintained

## Context

The original design called for each project folder to contain a note named after the
folder, linking to every other file in the folder, such that traversing the links
touches every file. Agents were to update it as they went.

That invariant is valuable and, maintained by hand, unenforceable. `AGENTS.md` and
`CLAUDE.md` are context, not configuration — they shape behaviour but guarantee nothing.
The first file written without a corresponding index entry breaks the guarantee
silently, and everything built on top of it is then built on a false assumption.

## Decision

The index note contains a generated block between `<!-- INDEX:START -->` and
`<!-- INDEX:END -->`, produced by `scripts/build_index.py` from the frontmatter of every
note in the folder. Content outside the markers is hand-written and preserved.

The invariant holds by construction: the index is a function of the folder's contents,
so a file cannot be missing from it.

## Rejected

**Hand-maintained, per the original design.** Rots on the first miss, with no signal
that it has.

**A hook enforcing the update.** A `PostToolUse` hook running the generator after writes
under `projects/` is the correct end state and is the enforcement layer if wanted. Not
adopted yet because the conventions are still moving and a hook wired to a moving
convention breaks every time it moves. Revisit once the structure has settled.

**Dataview or Bases queries generating the view live.** Renders beautifully in Obsidian
and is invisible to an agent reading the file, which fails the same test that produced
ADR-0003.

## Consequences

The generator has to be run after adding, renaming, or deleting notes. Until a hook
exists, that is a manual step and will sometimes be forgotten — but `check_vault.py`
detects it, which is the difference between drift that is visible and drift that is not.

Hand-editing inside the markers silently reintroduces the original problem. `AGENTS.md`
prohibits it explicitly.
