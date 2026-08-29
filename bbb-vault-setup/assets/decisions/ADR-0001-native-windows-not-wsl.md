---
type: adr
status: accepted
summary: Claude Code runs natively on Windows rather than inside WSL, because the vault lives on NTFS.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0001: Run Claude Code natively on Windows, not WSL

## Context

The vault is at `C:\Users\Admin\Obsidian\big-beatiful-brain\BBB` and is edited by
Obsidian, a Windows application. Claude Code supports both native Windows and WSL, and
the documented basis for choosing is where the files live and which features are needed.

## Decision

Run Claude Code natively on Windows, with Git for Windows installed so the Bash tool is
available via Git Bash rather than falling back to the PowerShell tool.

## Rejected

**WSL 2.** Would put a filesystem boundary between the agent and the notes. The vault
would be reached through `/mnt/c/`, which is the slow path and where file watching
becomes unreliable — and this vault is a large number of small markdown files, which is
the worst case for that boundary. Moving the vault into the WSL filesystem instead only
inverts the problem onto Obsidian, which would then reach it over `\\wsl$\`.

WSL 2 does offer sandboxed command execution, which native Windows does not. This was
judged not to apply: the agent needs write access to the vault by design, so the thing
sandboxing would protect is not the thing at risk.

**Running both.** Native and WSL installations keep separate configuration directories.
Settings, credentials, and MCP server lists do not cross between them, which means two
logins and two configurations drifting apart.

## Consequences

No sandboxing; permission rules are the layer doing that job instead. Scheduled agent
runs, if wanted later, go through Task Scheduler rather than cron. Windows path escaping
applies throughout: paths in `settings.json` need doubled backslashes.

**Open:** whether scheduled runs are wanted at all. Unresolved, and if the answer turns
out to be a heavy yes, revisit this ADR.
