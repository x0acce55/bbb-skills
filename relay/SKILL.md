---
name: relay
description: Graceful hand-off when Max subscription usage is nearly out: flush pending vault, memory and artifact writes, produce a handover via bbb-handover, and give the user the claude-paid restart command. Use on /relay, when the user says usage is almost exhausted, or to prepare for the paid fallback.
argument-hint: "optional: what the next session should focus on"
---

The subscription is nearly exhausted; spend the remaining budget making the
next session cheap. A fresh `claude-paid` session reading a handover doc costs
~$0.15; `claude-paid --continue` re-sends this whole transcript (potentially
$1–2 on a heavy session). This skill buys that difference. Work fast and
terse — every token here comes out of what's left.

## Procedure

1. **Flush state first, prose second.** Complete any half-done writes: memory
   files + MEMORY.md index, project notes and their `updated:` fields, index
   regeneration if notes were added, uncommitted artifact-repo work the user
   would want committed (via twss if git ops are blocked — but if the queue
   isn't already approved, skip commits and list them in the handover instead;
   there is no budget for an approval round-trip).
2. **Run the `bbb-handover` skill** with the arguments (or infer the focus from
   the current task). Vault-connected mode — the next session has the same
   vault. The doc lands outside the vault and on the clipboard, per that skill.
3. **Tell the user exactly how to resume**, in one short block:
   - `claude-paid` (fresh session) then paste the handover — the cheap path.
   - `claude-paid --continue` — full context, priced by transcript size; for
     when nuance matters more than dollars.
   - Or wait for the usage reset if it is near (free).
4. Stop. Do not start new work after the handover is written.

## Constraints

- The agent cannot see usage percentages — this skill is triggered by the USER
  when Claude Code's approaching-limit warning appears. Do not pretend to
  monitor usage.
- Never touch credentials: claude-paid fetches its own key at launch. Nothing
  goes on the clipboard except the handover text.
- If usage runs out mid-procedure, the flushed state is the fallback — that is
  why flushing precedes prose.
