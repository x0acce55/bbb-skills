---
type: adr
status: accepted
summary: An advisory TTL lock guards distillation only, and is documented as advisory rather than presented as mutual exclusion.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0010: An advisory lock, scoped to distillation

## Context

Per ADR-0009, ordinary memory writes need no coordination. Distillation does: it reads a
machine's buffer and writes to the shared `context/`, `decisions/`, and `daily/` files,
and two machines distilling at once would interleave writes to the same notes.

Distillation is short, deliberate, and human-initiated, which is the kind of operation a
lock can meaningfully protect — unlike continuous autonomous writes.

## Decision

`memories/.lock.json` holds the machine identifier, operation, PID, and a heartbeat, with
a TTL. `scripts/memlock.py` acquires, refreshes, releases, and force-breaks it. A stale
lock past its TTL is reclaimed automatically, because otherwise a crashed session blocks
the vault permanently.

After acquiring, the script waits briefly and re-reads the lock to confirm this machine
still holds it, catching the case where two machines acquired near-simultaneously and
the writes crossed in sync.

The lock's limits are documented in `references/memory-protocol.md` and stated to the
user rather than glossed: it is advisory, it does not close the sync propagation window,
and it does not cover auto memory writes.

## Rejected

**No lock at all.** Defensible given how rare simultaneous distillation is, but the
failure is silent and corrupts the shared layer, which is the layer worth protecting.

**A lock presented as mutual exclusion.** The most tempting option and the worst. A lock
believed to be binding is more dangerous than no lock, because work gets built on a
guarantee that doesn't exist.

**A `PreToolUse` hook blocking writes to shared files while another machine holds the
lock.** This is the only mechanism that actually enforces, since hooks run regardless of
what the agent decides. Held in reserve rather than adopted: it's the right move once
the conventions stop moving, and a hook wired to a convention still in flux breaks every
time the convention moves.

**Pinning distillation to a single designated machine.** Simple and genuinely safe.
Rejected as the default because it makes the second machine a second-class citizen, but
it remains the fallback if conflicts recur.

## Consequences

The user must be told the lock is advisory. Any documentation that implies otherwise is
a bug in the documentation.

Distillation sessions must release the lock, including on failure. An abandoned lock
clears only after its TTL.

**Open:** adopt the `PreToolUse` hook once conventions settle, or accept advisory-only
permanently? Revisit after a month of real use.
