---
type: adr
status: accepted
summary: Every note carries an up-link so the vault is navigable by clicking in Obsidian, not only by an agent following forward links.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0012: Up-links make the vault clickable

## Context

Generated index notes give downward navigation: an index links to everything in its
folder. Nothing gave upward navigation. A human who clicked into a note had no way back
except the file explorer or search, and an agent had no upward path at all — Obsidian's
backlink pane is computed by the application and does not exist in the file.

## Decision

Every note carries `up:` in frontmatter, pointing at the note one level above: a project
note points at its project index, an index points at the home note [[BBB]], ADRs point
at [[decisions]].

`BBB.md` at the vault root is the home note, linking to context, decisions, every project
index, and the daily folder.

Obsidian renders wikilinks in Properties as clickable, so `up:` is a real navigation
control in the UI rather than only metadata — one field serving both readers, which is
the same reason the rest of the context lives in frontmatter (ADR-0003).

## Rejected

**Relying on Obsidian's backlink pane.** Works for a human, invisible to an agent, and
it lists every inbound link rather than the structural parent.

**A breadcrumb line in the body of each note.** Visible without opening Properties, but
it is prose an agent must parse and a human must maintain, and it drifts when a note
moves.

**A Dataview or Bases query rendering navigation.** Renders well in Obsidian and is
invisible to an agent, failing the same test as backlinks.

**Nothing — treating downward navigation as sufficient.** Leaves every leaf note a dead
end for the person clicking through, which was the stated requirement.

## Consequences

`up:` must be set when a note is created and updated when a note moves between folders.
`check_vault.py` reports notes missing it. `context/` and `daily/` are exempt, since they
are flat and reached directly from home.

Traversal by clicking and traversal by an agent following forward links now visit the
same set of files, which is the property that makes the vault usable by both readers.
