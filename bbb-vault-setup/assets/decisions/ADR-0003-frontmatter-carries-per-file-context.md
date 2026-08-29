---
type: adr
status: accepted
summary: Per-file context lives in YAML frontmatter, because it is the only per-file metadata both Obsidian and a raw-file-reading agent can see.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0003: Frontmatter carries per-file context

## Context

An agent needs to know what a file contains and what it relates to without reading the
file. Obsidian offers backlinks, a graph view, and tag panes, but all of these are
computed by the application from the vault as a whole. None of them exist in the bytes
of a `.md` file. An agent reading a file from disk sees its text and its forward links,
and nothing else.

## Decision

Every note carries a YAML frontmatter block: `type`, `summary`, `created`, `updated`,
and optionally `project`, `status`, `decisions`, `tags`. The `summary` is one sentence
stating what the file contains and why it exists.

This makes the frontmatter the per-file context index. An agent can read the first
handful of lines of every file in a folder and know the folder's contents at a small
fraction of the cost of reading it.

## Rejected

**Relying on Obsidian backlinks and the graph.** Invisible to agents. This is the
central constraint and it rules out most of what Obsidian offers natively.

**Tags alone.** Visible in the file, but unstructured and unable to carry a summary or a
typed relationship.

**A separate manifest file listing every note.** One file to keep in sync with the whole
vault, guaranteed to drift, and it duplicates what the notes already know about
themselves.

**Naming conventions encoding metadata in filenames.** Limited, and renaming a file to
change its status breaks every link to it.

## Consequences

Every note must have frontmatter, which is a real ongoing cost and the most likely
convention to be skipped under time pressure. `scripts/check_vault.py` reports files
missing it.

The `summary` field has to be maintained honestly. A stale summary is worse than none,
because the scanning pass trusts it and will not open the file to find out otherwise.
