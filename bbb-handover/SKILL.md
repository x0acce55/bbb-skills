---
name: bbb-handover
description: Build a handover document for the current task, enriched with BBB vault context (project index, ADRs, durable facts, open threads) so the next session skips rediscovery. Use when the user asks for a handover, a task brief, or to prepare context for another or new session.
argument-hint: "What will the next session do? Add 'standalone' if the reader has no vault access."
---

Produce a handover document that combines two things the stock `handoff` skill
doesn't: compaction of *this conversation* AND enrichment from the *BBB vault*, so
the receiving session starts mid-stride instead of rediscovering.

## 1. Determine the audience

Two modes; pick from the arguments, or ask one question if unclear:

- **Vault-connected** (default for a Claude Code session launched from the vault
  root): the doc stays lean — it *links* to vault notes rather than inlining them.
- **Standalone** (a claude.ai chat, a person, a machine before sync — or the word
  "standalone" in the arguments): the doc inlines the load-bearing content;
  assume the reader can open nothing.

## 2. Compact the conversation

Follow the same discipline as the `handoff` skill: summarize so a fresh agent can
continue the work. Do not duplicate content already captured in artifacts, notes,
commits, or staging READMEs — reference them by path or [[wikilink]]. Treat the
arguments as what the next session will focus on and tailor accordingly.

## 3. Enrich from the vault

Identify the task's project(s) under `$BBB_VAULT_ROOT/projects/` and gather:

- the project index — summary, current state, **open threads**
- ADRs the project's notes declare (`decisions:` fields) — the settled choices the
  next session must not re-litigate
- durable-facts / gotcha notes in the project
- relevant machine memories (note: memories are machine-scoped and do NOT sync —
  anything load-bearing from memory must go into the doc itself)
- conventions that constrain the work (data-handling rules, naming, placement
  rulings)

Vault-connected: render this as a **"Read these first"** list — wikilink + one line
on why it matters. Standalone: inline the essential content, condensed.

## 4. Document structure

1. **Task and current state** — what this is, where it stands, one paragraph.
2. **Done and verified** — completed work, stated plainly, with paths.
3. **Next steps** — ordered, concrete, starting with the very next action.
4. **Vault context** — the "Read these first" list, or the inlined enrichment.
5. **Settled decisions** — ADR one-liners; do not re-litigate.
6. **Gotchas and constraints** — the things that bit us or almost did.
7. **Open questions** — and what each is waiting on.
8. **Suggested skills** — which skills the next agent should invoke and when.

## 5. Deliver

Write the doc to a scratch file OUTSIDE the vault (the session scratchpad, or the
task's staging directory if one exists) named `handover-<topic>.md`. Then copy it
to the clipboard per the `copy-prompt` skill's procedure (`pbcopy < file`, verify
byte count with `pbpaste | wc -c`) and report both the path and "copied to
clipboard (N bytes)".

Never write the handover into the vault by default — it's ephemeral. If the user
asks to keep one (a long-running task crossing machines), add it via the
`bbb-vault-setup` conventions as a dated section on the project index, not a new
note.

## Redaction — always

No credentials, ever (ADR-0020) — reference where a secret lives, never its value.
No PII: role-based references only, per the same rules as the import prompts. A
standalone doc leaves the vault's trust boundary, so it gets the strictest pass.
