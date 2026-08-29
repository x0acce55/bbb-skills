---
type: adr
status: accepted
summary: Note basenames are unique across the whole vault, enforced by check_vault, with domain or project prefixes for collision-prone names.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0014: Note basenames are vault-globally unique

> **Ledger note.** The original ADR-0014 and ADR-0015 were written in a session
> whose files were not preserved, before anything was deployed. This is a fresh
> record numbered into the gap — it documents a convention the tooling and
> `references/conventions.md` already depended on, not a reconstruction of the
> lost text. Safe only because no vault had been scaffolded yet.

## Context

Obsidian resolves `[[wikilinks]]` across the entire vault. Two folders each
containing `research.md` make `[[research]]` ambiguous, and Obsidian resolves
the ambiguity silently — links land on the wrong file with no error. The
tooling inherits the same assumption: generated index tables link by stem, and
the reachability walk in `health_report.py` keys its graph on stems, so a
duplicate basename corrupts both.

With multiple domains (ADR-0018), collisions stop being hypothetical: every
employer eventually has a `roadmap`, an `onboarding`, a `notes`.

## Decision

Every note basename is unique across the vault. `check_vault.py` reports
duplicates. When a natural name collides, prefix it with the project or domain
(`audacy-roadmap.md`, not `roadmap.md`) rather than relying on path-qualified
links.

## Rejected

**Obsidian's "use full path for new links" setting.** Fixes links the human
creates in the app and nothing else: agents write stem links, generated tables
write stem links, and path links break when a note moves between folders —
which is exactly what domain restructuring and job offboarding do.

**Per-folder uniqueness only.** Matches how filesystems think and not how
Obsidian resolves links. The ambiguity is vault-global, so the rule must be.

**Allowing duplicates and path-qualifying every link.** Verbose in prose,
move-fragile, and unenforceable against agents that emit the short form.

## Consequences

Stem links survive moves, which keeps domain restructuring and archiving cheap
— the payoff for paying the uniqueness cost up front.

Naming requires a moment of thought for generic titles. The prefix convention
makes the collision-prone cases mechanical.

`check_vault.py` is the enforcement (rung 3 on the ladder). If duplicates keep
appearing, the next move is a `PreToolUse` hook that rejects the write (rung
2), same escalation path as everything else here.
