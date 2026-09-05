---
name: bbb-memory-distill
description: Promote a machine's volatile agent memories into the BBB vault's shared layer (context, ADRs, daily notes), optionally with a handover doc. Use when asked to distill, flush, promote, consolidate, review or clear memories, when the memory file is long or messy, or before switching machines.
---

# Distill memory into the vault

A machine's buffer under `memories/<machine-id>/` is volatile working notes: things an
agent noticed while working. The durable shared layer is `context/`, `decisions/`, and
`daily/`. This skill moves what deserves to survive from the first into the second.

The reason this is a skill and not a script is that every judgment in it is a judgment.
Deciding whether an observation is a standing truth, a decision, or a passing detail is
exactly the part that can't be automated — and getting it wrong pollutes the layer the
user is supposed to be able to trust.

Read `references/routing.md` in this skill before classifying anything. Read the vault's
own `references/memory-protocol.md` (in `bbb-vault-setup`) if the memory layout is
unclear.

## Step 1: take the lock

Distillation writes to shared files, so take the lock first:

```
python <bbb-vault-setup>/scripts/memlock.py <vault> acquire --machine <machine-id> --operation distill
```

If it refuses, another machine is distilling. Stop and tell the user who holds it. Do
not break the lock on the user's behalf — offer `break --force` as something they can
choose, and say plainly that it means overriding another session.

Be honest about what this lock is: advisory, and unable to close the sync propagation
window. If two machines started within a sync interval of each other, both may hold it.
Say so if the user seems to be relying on it as a guarantee.

For a long distillation, refresh with `heartbeat` so the TTL doesn't expire mid-run.

## Step 2: read the buffer

Read `memories/<machine-id>/MEMORY.md` and every topic file beside it. Read the current
`context/` files too — you cannot tell what's new without knowing what's already there.

## Step 3: classify

Sort every memory into exactly one of six outcomes. `references/routing.md` has the
full decision procedure and worked examples; the summary:

| Outcome | When |
| --- | --- |
| **Context** | A standing truth about the user, their goals, or their tooling |
| **Decision** | A choice was made, with alternatives that lost |
| **Daily** | Something that happened on a date and stays dated |
| **Project** | Scoped to one project; belongs in that project's notes |
| **Domain** | True across one domain but not others; belongs in that domain's notes, never global context |
| **Drop** | Already recorded, superseded, trivial, or an artifact of one session |

Two rules that matter more than the rest:

**When unsure between context and drop, drop it.** Context is the layer the user treats
as true without checking. A wrong entry there is worse than a missing one, because it
propagates into every session silently.

**Secrets never promote.** Anything credential-shaped is dropped on sight and flagged
(ADR-0020).

**A memory is a claim, not a fact.** It was inferred by an agent from one session's
evidence. Promoting it into `context/` is asserting it on the user's behalf. If you
wouldn't defend it to them, it isn't ready.

## Step 4: present before writing

Show the user the classification as a table before touching a single file. For each
memory: what it says, where you'd put it, and one clause of why.

Ask them to confirm, correct, or veto. Then write only what survives that pass.

This is not a formality. The whole point of a distillation step is that a human decides
what enters the shared layer — automating it away turns this back into the thing
ADR-0009 rejected.

## Step 5: write

Follow `bbb-vault-setup`'s conventions, which the vault's own `AGENTS.md` also states:

- **Append rather than create.** Add to the existing context file or project note. New
  files are the exception.
- Update `summary` when a file's purpose widens, and always update `updated`.
- ADRs need real `Rejected` and `Consequences` sections. A distilled decision that
  records no alternatives isn't an ADR, it's a note — put it in context instead.
- Cross-reference decisions both ways: `affects:` on the ADR, `decisions:` on each note.
- Set `up:` on anything new.
- Regenerate indexes: `python <bbb-vault-setup>/scripts/build_index.py <vault>`

## Step 6: clear what was promoted

Remove the promoted entries from `MEMORY.md` and its topic files, leaving anything not
yet ready. A buffer that's never cleared grows until its index stops loading — only the
first 200 lines or 25KB of `MEMORY.md` enter context each session, so entries past that
threshold are silently invisible.

Leave a short line noting the date of the last distillation and where things went.

## Step 7: release the lock

```
python <bbb-vault-setup>/scripts/memlock.py <vault> release --machine <machine-id>
```

Release even if distillation failed partway. An abandoned lock clears only after its TTL
and blocks the other machine until then.

Then run `python <bbb-vault-setup>/scripts/check_vault.py <vault>` and report the result.

## Handover documents

If the user asks for a handover — for another agent, another machine, or a later session
— write it after distillation, not instead of it. Distillation puts knowledge somewhere
permanent; a handover is a pointer to work in flight.

Write it to the OS temporary directory, not the vault. A handover is disposable by
design, and anything worth keeping should have been promoted in step 5 instead.

Structure:

- What the work is and what state it's in
- What was decided this session, **by link** to the ADRs — never restated
- What's still open, and what the next session should do first
- Which skills the next agent should use
- Anything believed but not verified, marked as such

Redact absolute paths containing the user's name, machine identifiers, and anything
identifying from `about-me`.

Do not duplicate what's now in the vault. If a handover restates an ADR, the ADR should
have been linked instead.
