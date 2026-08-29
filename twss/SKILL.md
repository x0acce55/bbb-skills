---
name: twss
description: Batch-approve a queue of shell commands ("that's what she said") — Claude writes the exact commands to .claude/twss-queue.txt, the user approves once with the twss CLI, and a PreToolUse hook auto-allows only byte-exact, unconsumed lines of the approved queue. Use when the user invokes /twss, asks to batch-approve commands, mentions a command queue, or wants a known sequence to run without prompt-by-prompt approvals.
argument-hint: "the commands/task to queue, or 'status' / 'clear'"
---

Run a user-approved queue of shell commands without per-command permission
prompts. The enforcement is NOT this skill — it is the PreToolUse hook
(`.claude/hooks/twss.py`, registered in `.claude/settings.json`). This skill is
only the workflow around it. If the hook is not installed, say so and stop;
never simulate it.

## First run (per machine)

Check that the hook and the `twss` command exist: run `twss status` (Bash). If
the command is missing or the hook is unregistered, walk the user through setup
— the user runs these steps, not the agent, because PATH executables, hooks,
and settings are enforcement surface (agents are expected to be blocked from
them; that is the same rule that keeps `approve` human):

1. Copy `twss.py` (from this skill's folder) to `<vault>/.claude/hooks/twss.py`
   and merge the hook registration into `<vault>/.claude/settings.json` — the
   exact JSON is printed by step 2's installer when missing. Use `python`
   instead of `python3` in the hook command on Windows.
2. User runs the installer (via the `!` prefix):
   - macOS/Linux: `! python3 <skill-dir>/install.py`
   - Windows (Git Bash): `! python <skill-dir>/install.py`
   It writes a `twss` shim into a PATH directory per OS (macOS:
   /opt/homebrew/bin or /usr/local/bin or ~/.local/bin; Linux: ~/.local/bin;
   Windows: %USERPROFILE%\bin plus twss.cmd for cmd/PowerShell), shell-agnostic
   because it is a PATH executable, not an alias. `TWSS_INSTALL_DIR` overrides
   the target. Idempotent; re-run any time.
3. `python3 <skill-dir>/test_twss.py` once to prove the environment, then
   `/hooks` (or restart) so the session reloads hook config.

## Workflow

1. **Build the queue.** Write the exact commands — verbatim, one per line, in
   execution order — to `<project>/.claude/twss-queue.txt`. `#` comments and
   blank lines are allowed (they are shown but never matched). No denylisted
   content: `sudo`, recursive deletes of `/`, network pipe-to-shell.
2. **Show the user the numbered list** and ask them to approve by running (via
   the `!` prefix, themselves — NEVER run this yourself):
   `! twss approve`
   (long form if the shim isn't installed: `! python3 .claude/hooks/twss.py approve`;
   `python` on Windows)
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
