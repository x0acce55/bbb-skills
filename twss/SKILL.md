---
name: twss
description: Batch-approve a queue of shell commands ("that's what she said") — Claude writes the exact commands to .twss-queue.txt, the user approves once with the twss CLI, and a PreToolUse hook auto-allows only byte-exact, unconsumed lines of the approved queue. Use when the user invokes /twss, asks to batch-approve commands, mentions a command queue, or wants a known sequence to run without prompt-by-prompt approvals.
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

Then the user **restarts the session** (`claude --continue`): until they do,
the hook is on disk but not live here. Do not tell them `/hooks` will do it —
`/hooks` edits hook configuration, it does not re-arm a hook for the session
already running. Because a twss decline prints nothing, an unarmed hook is
indistinguishable from a correct decline, so "I ran the installer and it still
prompts me for every line" is the expected symptom of skipping the restart.
After the restart, `twss status` reports the hook registered and its
interpreter runnable — use that, not the log, as the test. The log is not a
per-call trace: consecutive identical declines collapse to one line, so a live
hook facing one unapproved queue logs once and then stays quiet however many
Bash calls follow. Absence of a log line is not evidence of a dead hook. To
prove a hook live, change the queue — the decline message carries the queue
hash, so the next call logs afresh.

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
   execution order — to `<project>/.twss-queue.txt`. Note the location: the
   project root, **not** `.claude/`, which Claude Code refuses agent writes into
   (ADR-0043). `#` comments and blank lines are allowed (they are shown but
   never matched). No denylisted content: `sudo`, recursive deletes of `/`,
   network pipe-to-shell.
   If a queued command will need Claude Code's sandbox disabled — anything
   reaching the network or writing outside the workspace, in a domain where the
   sandbox is on — put `# twss: allow-sandbox-escape` in the queue as a comment
   line. Without it the hook declines those calls, because the user approved
   command *text* and running it sandbox-disabled is a larger act than the text
   describes (ADR-0044). The directive is inside the approved bytes, so the user
   reads it and `approve` warns about it.
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
- **When twss "stops working", run `twss status` before theorising.** A decline
  prints nothing by design, so every cause looks identical from the outside —
  that is the failure ADR-0038 was written about. `status` names the resolved
  root and which variable chose it (an approval and a hook addressing different
  directories is the classic cause), reports whether a hook is registered here
  and whether its interpreter can start, and the log names the branch every
  decline took: `DECLINE hash-void`, `ttl-expired`, `consumed`, `no-match`,
  `sandbox-escape`. Read those two before concluding anything.

## What this does NOT do

It streamlines Claude Code's permission prompts for a queue the user has read
and approved — nothing more. Some operations may still be refused by other
layers, and those the user runs themselves via `!`. The "only the user runs
approve" rule is enforced for the Edit/Write path by Claude Code's own refusal
to let an agent write into `.claude/`, where the approval lives — but the hook
still cannot verify it (files do not record their author, and a sandbox-disabled
Bash call can reach `.claude/` anyway, ADR-0044): a strong guardrail against
accident, not a security boundary.
