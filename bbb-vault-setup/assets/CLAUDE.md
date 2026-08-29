@AGENTS.md

## Claude Code specifics

Instructions for every agent live in `AGENTS.md` above. Add nothing here that another
agent would also need — this section is only for behaviour unique to Claude Code.

- This machine's wiring lives in `.claude/settings.local.json`: `autoMemoryDirectory`
  plus an `env` block exporting `BBB_VAULT_ROOT`, `BBB_MACHINE_ID`, and
  `BBB_SETUP_SKILL`. That file is machine-specific and must never sync.
- Auto memory writes to `memories/<machine-id>/` for *this* machine only, configured in
  the same file. Never write into another machine's directory. Those
  files are visible to the user in Obsidian, so write them as notes a human would read.
- Memory buffers are volatile working notes. Durable knowledge is promoted into
  `context/`, `decisions/`, or `daily/` by the `bbb-memory-distill` skill. If a memory
  looks like it belongs in the shared layer, say so rather than writing it there
  directly.
- Each domain folder and each project folder has a one-line `CLAUDE.md` importing its
  index note, so that context loads when you start reading files there. You don't need
  to read the index note separately once you're working in the folder.
- Your session identity is in the environment: `$BBB_VAULT_ID`, `$BBB_MACHINE_ID`, and
  — when launched through a wrapper — `$BBB_SESSION_DOMAIN` and `$BBB_SESSION_TIER`.
  Respect them: do not write outside the session's domain at the elevated tier, and
  never write credentials anywhere (ADR-0019, ADR-0020).
- Use plan mode before any change touching more than three files in `projects/`.
