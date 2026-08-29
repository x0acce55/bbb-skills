---
type: adr
status: superseded
summary: ADR references are written in both directions in frontmatter, because agents cannot see Obsidian backlinks.
up: "[[decisions]]"
scope: foundational
superseded_by: ADR-0016
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0005: Decisions are cross-referenced in both directions

> **Superseded by [[ADR-0016-back-references-are-generated]].** Both directions still
> exist; requiring a human to write both was the mistake. Left unedited.

## Context

The original design had ADRs linking to the project files they affect, so a decision
could be traced back to its reasoning. That gives the reverse direction only through
Obsidian's backlink pane — which, per ADR-0003, an agent cannot see. An agent reading a
project file from disk would have no path to the decision governing it.

## Decision

Both directions are written explicitly, in frontmatter:

- ADR: `affects: ["[[projects/foo/foo]]"]`
- Affected note: `decisions: [ADR-0005]`

Inline `[[ADR-NNNN-...]]` links appear in a note's body only where the prose actually
invokes the decision. Frontmatter carries the machine-readable relationship; prose
carries the argument. The two are not duplicates of each other.

`scripts/check_vault.py` reconciles the two lists and reports asymmetry, so the pair
cannot drift apart unnoticed.

## Rejected

**One direction plus Obsidian backlinks.** The original proposal. Works for a human in
the app, fails for every agent and for anything reading the vault as files.

**Omitting decision references from notes entirely, keeping ADRs self-contained.**
Considered seriously, since it removes a maintenance burden. Rejected because tracing
from work back to its reasoning was a stated goal, and an ADR nobody encounters while
doing the work is an ADR nobody reads.

**Inline links in both directions instead of frontmatter.** Clutters prose with
references that aren't part of the argument, and is not machine-readable enough to
reconcile automatically.

## Consequences

Two places to update when a decision starts governing a new file. The reconciliation
check makes the omission visible rather than silent, which is the trade being made:
slightly more work, and a guarantee instead of a hope.
