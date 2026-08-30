---
name: twss
description: Batch-approve a queue of shell commands ("that's what she said") — Claude writes the exact commands to .claude/twss-queue.txt, the user approves once with the twss CLI, and a PreToolUse hook auto-allows only byte-exact, unconsumed lines of the approved queue. Use when the user invokes /twss, asks to batch-approve commands, mentions a command queue, or wants a known sequence to run without prompt-by-prompt approvals.
argument-hint: "the commands/task to queue, or 'status' / 'clear'"
---

Run a user-approved queue of shell commands without per-command permission
prompts. The enforcement is NOT this skill — it is the PreToolUse hook
(`.claude/hooks/twss.py`, registered in `.claude/settings.local.json` or
`.claude/settings.json`). This skill is only the workflow around it. If the
hook is not installed, say so and stop; never simulate it and never install it
yourself.

## First run (per machine)

**Decide installed-or-not by reading files, never by running `twss`.** A
`twss: command not found` proves nothing: the shim directory is often absent
from an already-open shell's stale PATH while the hook itself is registered and
working. Installed means both of:

1. `<vault>/.claude/hooks/twss.py` exists.
2. Some `<vault>/.claude/settings*.json` has a `PreToolUse` entry whose command
   contains `twss.py` — Grep for `twss.py` under `.claude/`, checking
   `settings.local.json` as well as `settings.json`.

If both hold it is installed: proceed to the workflow, and if the `twss`
command is missing anyway, use the long form
`python "<vault>/.claude/hooks/twss.py" status` and tell the user a new
terminal will have `twss` on PATH.

If either is missing, **print exactly one line for the user to run, then
stop.** Do not copy the hook, edit settings, or write a shim yourself, and do
not read the implementation to work out how to wire it — hooks, settings, and
PATH executables are enforcement surface, and an agent installing its own
permission bypass defeats the point. The installer is one idempotent command
that does every step (copies the hook, registers it in `settings.local.json`
pinned to the running interpreter, writes the shims, adds the Windows PATH
entry, runs the acceptance suite):

- macOS/Linux: `! python3 <skill-dir>/install.py`
- Windows: `! python <skill-dir>/install.py` — if that prints "Python was not
  found", `python` is the Microsoft Store stub; use `! py <skill-dir>/install.py`

Then the user reloads hook config with `/hooks` (or restarts the session):
until they do, the hook is on disk but not live here.

The installer validates an existing registration rather than trusting it, and
exits 2 if it is unhealthy — a dead interpreter (the hook then fails closed, so
twss silently never allows anything and the user is prompted for every line
despite approving), or a registration sitting in the syncing `settings.json`
where a machine-specific interpreter path does not belong. It reports the
problem and leaves it alone; `--repair` rewrites it into `settings.local.json`
pinned to the running interpreter. Report an exit 2 to the user with the
installer's own diagnosis and let them decide — never repair on their behalf.

Flags: `--repair` (fix an unhealthy registration), `--no-test` (skip the
acceptance suites), `--no-path` (leave the Windows user PATH alone);
`TWSS_INSTALL_DIR` overrides the shim directory.

## Workflow

1. **Build the queue.** Write the exact commands — verbatim, one per line, in
   execution order — to `<project>/.claude/twss-queue.txt`. `#` comments and
   blank lines are allowed (they are shown but never matched). No denylisted
   content: `sudo`, recursive deletes of `/`, network pipe-to-shell.
2. **Show the user the numbered list** and ask them to approve by running (via
   the `!` prefix, themselves — NEVER run this yourself):
   `! twss approve`
   (if that reports command-not-found, the shim is not on this shell's PATH —
   give the long form instead: `! python3 .claude/hooks/twss.py approve`, or
   `python` / `py` on Windows. Do not treat it as "not installed".)
3. **Execute after approval**, sequentially, one Bash call per queue line,
   copying each command byte-for-byte from the queue file — any deviation
   (extra space, added flag) will not match and will prompt normally. Stop on
   the first failure and report it; do not improvise recovery commands under
   the same approval.
4. **Report per-command results honestly** — exit codes and key output, no
   glossing. Then run `twss status` to show the consumed/remaining state if any
   lines are left.

## Rules

- An approval covers exactly the bytes the user read: any queue change voids
  it (SHA-256 pinned), each line runs at most once per approval, approvals
  expire after 30 minutes (TTL_SECONDS in the hook; `TWSS_TTL_SECONDS` to
  override).
- Claude NEVER runs `approve`, installs the shim, edits the hook, or edits the
  settings registration. Those are the user's consent acts. If an approval is
  missing, stale, or void, ask the user to re-approve — never retry your way
  around it. There is deliberately no `/twss approve` path: the `!` prefix is
  the only channel that provably comes from the user's keyboard.
- A failed line means the queue is stale: fix the line (which voids the
  approval by design) and ask for re-approval. Note a line is consumed when it
  is ALLOWED, not when it succeeds — a failed line cannot silently re-run.
- `twss clear` removes the queue, approval, and state; `twss status` shows
  hash, approval state, and per-line consumption. The allow log is
  `.claude/twss-log.txt`.

## What this does NOT do

It streamlines Claude Code's permission prompts for a queue the user has read
and approved — nothing more. Some operations may still be refused by other
layers, and those the user runs themselves via `!`. The "only the user runs
approve" rule is a documented convention plus an audit log, not something the
hook can verify (files do not record their author): a guardrail against
accident, not a security boundary.
