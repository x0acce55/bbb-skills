---
type: adr
status: accepted
summary: Auto memory writes to a per-machine subdirectory, so no two machines ever write the same file.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0009: Per-machine memory buffers

Supersedes [[ADR-0006-auto-memory-writes-into-the-vault]].

## Context

ADR-0006 pointed Claude Code's auto memory at a single shared `memories/` directory in
the vault. The vault is used from more than one machine and syncs between them.

That combination has no safe outcome. Auto memory is written autonomously and
continuously by the tool as it works, and is designed on the assumption that nothing
else writes the same files. Two machines writing one synced `MEMORY.md` produces
conflicted copies, and does so during normal use rather than in some edge case.

The obvious fix — a lock — does not work here either. The lockfile lives in the same
synced directory as the files it protects and is subject to the same propagation delay,
so machine B can see no lock while machine A holds one.

## Decision

Each machine writes only to `memories/<machine-id>/`, set per machine in
`.claude/settings.local.json`, which is excluded from sync.

No two machines write the same file, so ordinary operation needs no coordination at all.
Auto memory continues to work exactly as designed.

The buffers are volatile and machine-scoped. Durable shared knowledge lives in
`context/`, `decisions/`, and `daily/`, and is promoted there by the
`bbb-memory-distill` skill.

## Rejected

**A shared memory directory with a lock.** The original request. Rejected because a lock
inside the synced directory cannot close the propagation window, and because a lock over
continuous autonomous writes would have to be held essentially all the time — at which
point it stops being a lock and starts being a queue for one machine.

**A shared directory with no lock.** Conflicted copies during normal use.

**Disabling auto memory entirely and writing memories by hand.** Removes the conflict by
removing the feature.

**Keeping memory outside the vault, at the tool default.** Conflict-free, and splits the
second brain across two places, one of which the user never sees. ADR-0006's reasoning
on this still holds.

## Consequences

Memory is no longer shared *directly* between machines. It is shared *after
distillation*, which is a deliberate step rather than an automatic one. This is slower
and it is the point: an agent's raw observations are evidence, and promoting them into
shared truth should involve judgment.

Machine identifiers become load-bearing. They're recorded in
`context/stack-and-conventions.md` under Environment.

`.claude/settings.local.json` must be excluded from sync. If it syncs, the second
machine inherits the first machine's memory path and the separation silently collapses —
the one failure mode of this design, and the thing to check first if conflicts appear.
