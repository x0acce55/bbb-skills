---
type: adr
status: accepted
summary: The vault's decisions/ directory is the only decision ledger; setup decisions and project decisions share it.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0008: One decision ledger

## Context

The vault design includes a `decisions/` directory. The process of designing the vault
also produced decisions, which a grilling workflow would normally write as ADRs
somewhere in a working repo. That is two ADR directories and no rule about which one
receives the next entry.

## Decision

`decisions/` in the vault is the only ledger. The decisions that produced this structure
— ADR-0001 through ADR-0008 — are its first entries. Vault-structure decisions and
project decisions live together, distinguished by their `affects` field rather than by
location.

## Rejected

**A separate ledger for meta-decisions about the vault itself.** Cleaner in theory. In
practice it means asking "is this a vault decision or a project decision?" every time,
a question with no reliable answer and no consequence attached to getting it wrong.

**No ADRs for the setup at all, treating the structure as self-evident.** The structure
has several non-obvious choices — generated indexes, bidirectional references,
frontmatter over backlinks — each of which looks arbitrary without its reasoning and
will be "simplified" by someone in six months, possibly the user.

## Consequences

ADR numbering is global across the vault. Early numbers are structural; later ones will
be a mix. This is fine and is what `affects` is for.

**Open:** the vault root is `BBB` inside a parent folder `big-beatiful-brain`. If that
parent becomes a git repository with the vault inside it, that is a reasonable
separation and should be recorded. If the nesting is accidental, flatten it now, while
nothing references the path.

**Open:** `big-beatiful-brain` is missing an `f`. The path is about to be written into
`settings.json` and every ADR. Rename now or accept it permanently.
