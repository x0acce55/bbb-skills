# Memory protocol

## Contents

- [The problem this solves](#the-problem-this-solves)
- [Per-machine buffers](#per-machine-buffers)
- [Configuration](#configuration)
- [The distillation lock](#the-distillation-lock)
- [What the lock does not do](#what-the-lock-does-not-do)
- [Recovering from a conflict](#recovering-from-a-conflict)

## The problem this solves

Two goals pull in opposite directions.

Claude Code's auto memory is designed to be machine-local. Claude writes it
autonomously and continuously as it works, and the tool assumes nothing else is writing
the same files.

The vault, meanwhile, is meant to be a shared second brain, used from several machines.

Point auto memory at a shared synced directory and you have combined continuous
autonomous writes with a sync layer, from multiple machines, with no coordination. That
does not produce shared memory. It produces conflicted copies.

## Per-machine buffers

Each machine writes only to its own directory:

```
memories/
├── desktop-win/
│   ├── MEMORY.md
│   └── feedback_testing.md
├── macbook/
│   └── MEMORY.md
└── .lock.json
```

No two machines ever write the same file, so there is nothing to contend over and no
lock is needed for ordinary operation. Auto memory keeps working exactly as designed.

The index file `MEMORY.md` is loaded into every session on its machine, so every byte in
it is paid on every turn. Keep it to one line per memory, at most 300 bytes each and
8 KB in total, naming the topic file and its current conclusion; corrections and detail
go in the topic file. `health_report.py` reports entries and indexes over that budget
(measured 2026-09-05: an 18 KB index with one 6.4 KB entry cost ~7.6k tokens per turn).

The buffers are **volatile and machine-scoped**. They are working notes, not the shared
brain. Anything that matters is promoted out of them into `context/`, `decisions/`, or
`daily/`, which are the durable shared layer. That promotion is the `bbb-memory-distill`
skill.

The distinction between the three layers is authorship and reliability:

| Layer | Written by | Trust | Scope |
| --- | --- | --- | --- |
| `context/` | the user | asserted, treated as true | shared |
| `decisions/` | user + agent, append-only | reasoned, dated | shared |
| `memories/<machine>/` | the agent, autonomously | observed, may be wrong | one machine |

If you cannot tell whether a fact belongs in `context/` or a memory buffer, ask who
would be embarrassed if it turned out to be false.

## Configuration

`autoMemoryDirectory` must be an absolute path or start with `~/`. Because it differs
per machine, it goes in `.claude/settings.local.json`, not the shared `settings.json`.

Windows:

```json
{
  "autoMemoryDirectory": "C:\\Users\\Admin\\Obsidian\\big-beautiful-brain\\BBB\\memories\\desktop-win"
}
```

macOS or Linux:

```json
{
  "autoMemoryDirectory": "~/Obsidian/big-beautiful-brain/BBB/memories/macbook"
}
```

Backslashes are doubled on Windows because the file is JSON.

**Exclude `settings.local.json` from sync.** If it syncs, the second machine inherits
the first machine's memory path and the whole separation collapses. Add it to
`.gitignore`, or to Obsidian Sync's excluded files, depending on the sync mechanism
recorded in `context/stack-and-conventions.md`.

Seed each buffer's `MEMORY.md` from `assets/templates/MEMORY.md`. The frontmatter
matters: Claude Code adds a `modified` timestamp only to memory files that already have
frontmatter, and never adds frontmatter to a file that has none.

`MEMORY.md` is exempt from the folder-note naming convention, because Claude Code names
that file itself. Don't fight the tool for the sake of a convention.

## The distillation lock

Distillation is the one operation that reads a machine's buffer and writes to the shared
files. It is short, deliberate, and human-initiated — which is exactly the kind of
operation a lock can meaningfully protect.

```
python scripts/memlock.py <vault> status
python scripts/memlock.py <vault> acquire --machine desktop-win --operation distill
python scripts/memlock.py <vault> heartbeat --machine desktop-win
python scripts/memlock.py <vault> release --machine desktop-win
python scripts/memlock.py <vault> break --force
```

`acquire` writes `memories/.lock.json` with the holder, the operation, and a heartbeat
timestamp. It refuses if another machine holds a live lock, and reclaims automatically
if the existing lock's heartbeat is older than its TTL — otherwise a crashed session
would block the vault permanently.

`acquire` also re-reads the lock after a short delay and confirms this machine still
holds it, which catches the case where two machines acquired near-simultaneously and the
writes crossed in sync. This narrows the race; it does not eliminate it.

Always `release` in the same session that acquired, including when distillation fails
partway. An abandoned lock is only cleaned up after its TTL expires.

## What the lock does not do

Be honest about this with the user rather than letting them believe they have mutual
exclusion.

**It is advisory.** Nothing prevents another process from ignoring it. To make it
binding for Claude Code specifically, pair it with a `PreToolUse` hook that blocks
writes under `context/` and `decisions/` while another machine holds the lock. Only a
hook enforces regardless of what the agent decides; markdown instructions do not.

**It cannot close the sync propagation window.** If machine A acquires and the lockfile
has not finished syncing when machine B checks, B sees no lock and acquires too. No
lockfile placed inside the synced directory can solve this, because the lock is subject
to the same propagation delay as the thing it protects. The confirm-after-delay check
narrows the window to roughly the sync interval rather than closing it.

**It does not protect auto memory writes**, which are continuous and autonomous. It does
not need to — per-machine buffers already make those conflict-free.

The lock's real value is that it turns a silent corruption into a visible refusal most
of the time, and leaves an attributable record of who was writing when it doesn't.

## Recovering from a conflict

`check_vault.py` reports files matching the conflict-copy patterns that sync clients
produce — `*conflicted copy*`, `*.sync-conflict-*`, and similar.

When one appears:

1. Do not delete it. It contains work that would otherwise be lost.
2. Diff it against the file it conflicts with.
3. Merge by hand into the canonical file, then delete the copy.
4. If the conflict is in a shared file that distillation wrote, note it — repeated
   conflicts there mean the lock's propagation window is too narrow for the sync
   mechanism in use, and distillation should be pinned to one machine instead.
