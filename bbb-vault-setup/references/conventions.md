# BBB vault conventions

## Contents

- [Why frontmatter carries the context](#why-frontmatter-carries-the-context)
- [Frontmatter schema](#frontmatter-schema)
- [Writing a good summary](#writing-a-good-summary)
- [Prefer appending to creating](#prefer-appending-to-creating)
- [Naming](#naming)
- [Linking and human routing](#linking-and-human-routing)
- [Index notes](#index-notes)
- [Directory rules](#directory-rules)

## Why frontmatter carries the context

Obsidian shows a human backlinks, a graph, and tag panes. None of that exists in the
file. An agent that opens `foo.md` sees the text and the forward links, and nothing
else — no backlinks, no graph, no "related notes."

So any relationship that matters to an agent has to be written into the file. YAML
frontmatter is the right place because it is the one channel both readers understand:
Obsidian renders it as Properties and can filter and query on it, and an agent reads it
as the first few lines of plain text.

That last part is the point. An agent can read the first ~12 lines of every file in a
folder and come away with a complete picture of the folder's contents for a fraction of
the cost of reading the folder. **The frontmatter is the per-file context index.**

## Frontmatter schema

Every note in the vault carries this block. Fields marked optional may be omitted, not
left blank — an empty field reads as "answered: nothing," which is worse than absent.

```yaml
---
type: note            # note | index | adr | context | daily
summary: One sentence describing what is in this file and why it exists.
up: "[[some-project]]"  # the note one level up. Clickable in Obsidian.
status: active        # active | paused | done | archived   (optional)
project: some-project # folder name, for notes inside projects/  (optional)
domain: audacy        # employer, client, or personal — mirrors the path  (optional)
decisions: [ADR-0004] # ADRs that govern this file  (optional)
tags: [research]      # optional
created: 2026-08-25
updated: 2026-08-25
---
```

ADRs additionally carry:

```yaml
status: proposed      # proposed | accepted | superseded
affects: ["[[projects/some-project/some-project]]"]
superseded_by: ADR-0011   # only once superseded
```

Index notes additionally carry:

```yaml
type: index
project: some-project
```

Leave Claude Code's own files in `memories/` alone. It manages their frontmatter and
adds a `modified` timestamp itself.

## Writing a good summary

The `summary` is the highest-leverage field in the vault and the easiest to write
badly. Write the sentence you would want to read if you were deciding whether to open
the file.

Good: `Benchmarks of three embedding models on our own corpus; bge-m3 won on recall.`
Bad: `Notes on embeddings.`

The test: if ten files in a folder all had summaries as vague as yours, would the folder
index tell you anything? If not, rewrite it.

Update `summary` when the file's purpose changes, not when its contents change. A file
whose summary no longer describes it is worse than a file with no summary, because the
scanning pass will trust it.

## Prefer appending to creating

Before creating a note, read the folder's index and look for an existing note whose
`summary` already covers the topic. If one exists, append to it rather than creating a
sibling: add a dated `## YYYY-MM-DD` section, update `updated`, and revise `summary` if
the file's purpose has widened.

Create a new note only when the topic genuinely does not belong under any existing
summary — not merely because the content is new.

This is not tidiness for its own sake. Every additional file is another index entry,
another `up:` link, another thing that can go stale, and another candidate for a
duplicate basename. A vault of two hundred thin notes is harder to navigate than one of
forty substantial ones, for both readers. The frontmatter index only stays useful while
summaries describe meaningfully different things.

The same applies to frontmatter: update the existing fields rather than inventing new
ones. If a field you want doesn't exist in the schema, that's a conventions change and
belongs in an ADR, not in one file's header.

## Naming

- Folders and files: `kebab-case`.
- Notes inside `projects/` should have **vault-globally unique basenames**. Obsidian
  resolves `[[Research]]` across the entire vault, so two projects each containing
  `research.md` creates ambiguity that will silently resolve to the wrong file. Prefix
  collision-prone names with the project or domain (`audacy-roadmap.md`) — decided in
  [[ADR-0014-vault-globally-unique-basenames]], enforced by `check_vault.py`.
- Daily notes: `daily/YYYY-MM-DD.md`.
- ADRs: `decisions/ADR-NNNN-kebab-title.md`, zero-padded to four digits.
- Avoid `[` and `]` in file and folder names. Beyond confusing wikilink syntax, Claude
  Code's path-scoped rule globs treat `[` as the start of a bracket expression, and a
  pattern containing an unmatched one matches nothing.

## Linking and human routing

The vault has to be navigable by clicking, not just by grep. Someone browsing in
Obsidian should be able to get anywhere from anywhere without using search.

**Down:** folder index notes link to their contents, generated from frontmatter.

**Up:** every note carries `up:` in frontmatter, pointing to its index note. Obsidian
renders wikilinks in Properties as clickable, so this is a real navigation control in
the UI and not merely metadata. It is also the only up-path an agent can see, since
backlinks don't exist in the file.

**Home:** `BBB.md` at the vault root — always that name, on every machine (ADR-0015) —
links to `context/`, `decisions/decisions.md`, each domain index, and the daily index.
Every domain index's `up:` points here; project indexes point at their domain.

**Across:** ADR `affects:` and note `decisions:` link the two together in both
directions, so a decision is reachable from the work and the work from the decision.

The resulting chain is complete: home → domain index → project index → note, and back
up the same `up:` links, and any ADR from any note it governs. Traversal by clicking and traversal by an
agent following forward links visit the same set of files, which is the property that
makes the vault usable by both readers.

Beyond that structure:

- Human-facing relationships: inline `[[wikilinks]]` in prose, where the sentence
  explains *why* two notes relate.
- Machine-facing relationships: frontmatter fields.
- Don't express the same relationship both ways as a matter of routine. Frontmatter
  says *that* two things relate; prose says *why*.
- If your only path from A to B is Obsidian's backlink pane, an agent cannot follow it.

## Index notes

Every project folder contains a note named after the folder. It is the folder's entry
point for both readers.

Structure:

```markdown
---
type: index
project: some-project
summary: ...
up: "[[BBB]]"
---

# some-project

Whatever the user wants to write. Purpose, current state, open threads.
This section is hand-written and the generator never touches it.

<!-- INDEX:START -->
| Note | Summary | Status | Decisions |
| ... generated ... |
<!-- INDEX:END -->

## Notes

Anything below the end marker is also hand-written and preserved.
```

The generated block is a function of the folder's frontmatter. Do not hand-edit it — if
it's wrong, the frontmatter or the generator is wrong. Hand-editing it reintroduces
exactly the drift the generated block exists to prevent.

`decisions/decisions.md` is generated the same way, indexing the ADRs by number, status,
and what they affect.

The folder-note convention has one exemption: `memories/<machine-id>/` uses `MEMORY.md`,
because Claude Code names that file itself. Don't fight the tool for the sake of a
convention.

## Directory rules

**`context/`** — background the user writes, that is true regardless of what project is
open. Personal facts, standing goals, tooling conventions. If a fact is only true for
one project, it belongs in that project's index note, not here. Keep the total small:
everything root `CLAUDE.md` imports is loaded at the start of every session and is paid
for every time.

**`memories/<machine-id>/`** — written by Claude Code, not by the user, and scoped to
one machine so that no two machines ever write the same file. Observed, inferred, and
possibly wrong. The distinction from `context/` is *authorship and reliability*: context
is asserted by the user and treated as true; memories are noticed by an agent and
treated as evidence. If you cannot tell which of the two a fact belongs in, ask who
would be embarrassed if it turned out to be false.

These buffers are volatile. Anything durable is promoted out of them into `context/`,
`decisions/`, or `daily/` by the `bbb-memory-distill` skill. See
`references/memory-protocol.md`.

**`decisions/`** — append-only. See the ADR section in SKILL.md.

**`daily/`** — dated capture. Daily notes are allowed to be messy; that is their job.
The discipline is the promotion path: when something in a daily note turns out to be
permanently true, it moves to `context/`, and when it turns out to be a decision, it
becomes an ADR. A daily note that never promotes anything is a diary, which is fine, but
then it isn't part of the second brain.

**`projects/<domain>/<project>/`** — work partitioned by domain (ADR-0018): an
employer, a client, or `personal`. Both levels carry an index note named after the
folder and a one-line `CLAUDE.md` importing it. The path is authoritative; `domain:`
and `project:` frontmatter mirror it and `check_vault.py` reports disagreement.
