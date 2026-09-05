# BBB vault

This is an Obsidian vault used as a second brain: projects, decisions, daily notes, and
accumulated context. You are working directly in the user's notes. Treat every file as
something they wrote by hand and care about.

## Orientation

Start at [[BBB]], the home note. From there everything is reachable by following links.

- `context/` — background the user wrote. Assume it is true.
- `decisions/` — architecture decision records. Append-only. Index at [[decisions]].
- `projects/<domain>/<project>/` — work partitioned by domain (an employer, a
  client, or `personal`). Entry points are `<domain>.md` and `<project>.md`.
- `daily/` — dated capture, `YYYY-MM-DD.md`.
- `memories/<machine-id>/` — an agent's own working notes for one machine. Evidence,
  not fact, and not shared between machines.

Read `context/about-me.md` and `context/goals.md` before starting a task. For work
inside a project, the project's index note is its context and its current state.

Already in your context at launch, so never open them again with Read or `cat`:
`AGENTS.md` (imported by `CLAUDE.md`), your machine's `memories/<machine-id>/MEMORY.md`,
and the index note that a folder's `CLAUDE.md` imports once you work there. Re-reading
them re-enters the same text as a tool result.

## This vault has a setup skill — use it

Structure, frontmatter, index notes, and decision records in this vault are maintained
by the `bbb-vault-setup` skill. Use it rather than improvising a layout: the conventions
here are load-bearing and the reasons are recorded in `decisions/`, so improvising
quietly breaks invariants that other tooling depends on.

Use `bbb-memory-distill` to promote memories into the shared layer.

If anything about the setup looks wrong or missing — no `context/`, no index note, a
memory buffer in the wrong place — run the check rather than guessing:

```
python <skill>/scripts/verify_setup.py "$BBB_VAULT_ROOT"
```

`$BBB_VAULT_ROOT` and `$BBB_MACHINE_ID` are set from `.claude/settings.local.json`. If
they are unset, this machine has not been registered against the vault; say so and offer
to run `bbb-vault-setup` rather than working around it.

## Append before you create

Before creating a note, read the folder's index and look for an existing note whose
summary already covers the topic. If one exists, append a dated section to it and update
its `summary` and `updated` fields rather than creating a sibling.

Create a new file only when the topic genuinely doesn't belong under any existing
summary — not merely because the content is new. Every extra file is another index
entry, another link to maintain, and another chance for a duplicate basename. Forty
substantial notes navigate better than two hundred thin ones.

The same applies to frontmatter: update existing fields rather than inventing new ones.
A new field is a conventions change and belongs in an ADR.

## Frontmatter

Every note carries YAML frontmatter with at minimum `type`, `summary`, `up`, `created`,
and `updated`. A note without it is invisible to the tooling that keeps this vault
navigable, so add it rather than leaving it out.

`summary` is one sentence: what a reader needs in order to decide whether to open the
file. Write it before writing the note. Update it when the file's *purpose* changes, not
every time its contents do — a summary that no longer describes its file is worse than
none, because the scanning pass trusts it.

`up` points at the note one level up: a note points at its project index, a project
index at its domain index, a domain index at [[BBB]]. Obsidian renders it as a clickable property, so it is real navigation for a
human, and it is the only upward path an agent can see.

## Links

Keep the vault navigable by clicking, not just by grep. Someone browsing should be able
to get anywhere from anywhere without using search.

- Down: index notes link to their contents. Generated — never hand-edit inside the
  `<!-- INDEX:START -->` / `<!-- INDEX:END -->` markers.
- Up: the `up:` field.
- Across: ADRs and the notes they govern, linked in both directions.
- In prose: inline `[[wikilinks]]` where the sentence explains *why* two notes relate.

Obsidian's backlink pane does not exist in the file. If your only path from A to B is a
backlink, an agent cannot follow it — write the forward link.

After adding, renaming, or deleting a note, regenerate the folder index. If the
generated output looks wrong, fix the frontmatter or the generator, not the output.

## Decisions

Record decisions as ADRs and reference them in two directions: `decisions: [ADR-NNNN]`
in the affected note's frontmatter, `affects:` in the ADR's. Add an inline ADR link in
prose only where the text actually invokes the decision.

Never rewrite an accepted ADR body. Supersede it with a new one and set `superseded_by`.

Do not hand-write an ADR's `affects:` field. It is generated from the `decisions:` fields
of the notes that declare it, so anything you write there is overwritten on the next
regeneration. Declare the relationship on the note.

## Limits

- Never delete a note without asking.
- Never edit anything in `context/` without asking — those are the user's own words.
- Never hand-edit another machine's directory under `memories/`.
- `kebab-case` for files and folders; note basenames unique across the whole vault,
  since Obsidian resolves `[[links]]` globally; avoid `[` and `]` in filenames.
- When something in a daily note turns out to be permanently true, propose promoting it
  to `context/`; when it turns out to be a decision, propose an ADR. Propose — don't
  move the user's notes on your own initiative.
