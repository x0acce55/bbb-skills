---
type: adr
status: accepted
scope: foundational
summary: Notes declare which decisions govern them; each ADR's affects field is generated from those declarations rather than written by hand.
up: "[[decisions]]"
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0016: Back-references are generated

Supersedes [[ADR-0005-decisions-cross-referenced-both-directions]].

## Context

ADR-0005 required both directions of a decision reference to be written by hand:
`affects:` on the ADR, `decisions:` on each note it governs.

That stores one fact in two places with neither authoritative, which is a normalisation
problem rather than a discipline problem. Redundant storage without a source of truth
drifts by construction. It drifted within twenty minutes of the first vault being
populated, in five places, with both halves written deliberately minutes apart.

`check_vault.py` detected the drift, which is level 3 on the enforcement ladder --
visible, but still requiring a human to notice and repair. Index notes had already
solved the same class of problem at level 1 by being generated. Decision references were
the last hand-maintained redundancy in the vault.

## Decision

A note's `decisions:` field is authoritative. `build_index.py` regenerates every ADR's
`affects:` from the notes that declare it. The fact is stored once; the other direction
is derived, so the two cannot disagree.

Only ADR frontmatter is written. The body -- the argument -- is never touched.

## Rejected

**Making `affects:` authoritative and generating `decisions:`.** The obvious symmetric
alternative, and wrong for two reasons. ADRs are append-only, so a note written in
November falling under a July decision would mean editing an accepted record every time
new work appears. And authorship sits the wrong way round: the person writing a note
knows which decision they are following, while a decision cannot know what has not been
written yet.

**Keeping both hand-written and relying on the checker.** What ADR-0005 did. The checker
works, and detection is strictly worse than impossibility when impossibility is available
at the same cost.

**Dropping the back-reference entirely.** Would remove the drift by removing the feature.
Tracing from a decision to the work it governs was the point of ADR-0005 and is still
wanted.

## Consequences

`build_index.py` now writes to files in `decisions/`. This is a narrowing of the
append-only rule, made explicit: frontmatter is a machine-maintained index, the body is
the immutable record. Anything that edits an ADR body is still a bug.

Hand-editing `affects:` is now pointless -- the next regeneration overwrites it. The
checker still verifies symmetry, which now functions as a test that the generator ran.
