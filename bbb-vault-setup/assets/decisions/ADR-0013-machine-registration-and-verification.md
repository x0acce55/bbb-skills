---
type: adr
status: accepted
summary: Each machine registers against the vault in settings.local.json, and a check script verifies the wiring and reports what it finds.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0013: Machines register against the vault, and the wiring is checkable

## Context

ADR-0009 gave each machine its own memory buffer. That created a per-machine
configuration surface with no way to tell, from inside a session, whether the current
machine was set up correctly — or whether the vault was present at all.

The failure this guards against is specific and silent. If
`.claude/settings.local.json` reaches a second machine through sync, that machine
inherits the first machine's `autoMemoryDirectory`, both write the same buffer, and the
per-machine separation collapses back into exactly the design ADR-0009 rejected. Nothing
about that failure is visible until conflicted copies appear.

## Decision

Every machine writes `.claude/settings.local.json` containing `autoMemoryDirectory` and
an `env` block exporting `BBB_VAULT_ROOT`, `BBB_MACHINE_ID`, `BBB_SETUP_SKILL`, and
`BBB_SETUP_SOURCE`. The file is excluded from sync.

`scripts/verify_setup.py` resolves the vault from an argument, then `$BBB_VAULT_ROOT`,
then by walking up looking for `.obsidian/`, and reports whether the vault was found and
whether this machine is registered. It exits 0 (registered), 4 (vault found, machine
unregistered), 5 (no vault), or 1 (broken).

For now it is a manual check that reports its findings. The exit codes exist so it can
later be driven by a `SessionStart` hook that fetches the skill from git when the vault
isn't found.

The instruction to *use* the skill lives in `AGENTS.md`, not in the settings file.

## Rejected

**Putting the directive in `settings.local.json`.** The original request. Settings are
configuration enforced by the client; instructions are `AGENTS.md` and shape what the
agent decides. A directive in JSON is read as neither. Invented top-level settings keys
are also outside the schema and can surface as validation errors.

**Automating the git fetch now.** The end state, deliberately deferred. The skill is not
published yet, so there is nothing to fetch, and a `SessionStart` hook that clones a
repository is a thing that runs on every session start — worth having only once the
thing it clones is stable. Building it now means debugging it against a moving target.

**Deriving the machine id from the hostname automatically.** Removes a setup step and
makes the identifier opaque, unstable across OS reinstalls, and occasionally
non-filesystem-safe. An explicit short identifier the user chose is more legible in a
directory listing they will read for years.

**Folding this into `check_vault.py`.** Different question. That script asks whether the
vault's *contents* are consistent; this one asks whether *this machine* is wired to it.
They fail for different reasons and are run at different times — the wiring check on a
new machine, the content check after edits.

## Consequences

Adding a machine is a real step that cannot be skipped, which is the intent: the check
exits 4 and says so rather than letting an unregistered machine write into a shared
buffer.

`verify_setup.py` warns while `BBB_SETUP_SOURCE` is empty. That warning is a deliberate
placeholder and should stay noisy until the repository exists.

Sync exclusion is only automatically verifiable for git. For Obsidian Sync and Syncthing
the check can report that it cannot confirm, and the exclusion has to be set in that
client. That is the one gap in this design and the first thing to check if buffers ever
collide.

**Open:** publish the skills to git and wire the `SessionStart` hook, or leave detection
manual? Revisit once the conventions have been stable for a month.
