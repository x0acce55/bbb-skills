# Claude Code configuration for the BBB vault

Everything here is behaviour that is easy to get wrong in a way that fails silently —
instructions that never load, or context that loads every session and quietly costs
tokens forever.

## AGENTS.md and CLAUDE.md

Claude Code reads `CLAUDE.md`. It does not read `AGENTS.md`.

Since the goal is agent-agnostic instructions, all substance goes in `AGENTS.md` and
`CLAUDE.md` is a thin wrapper that imports it:

```markdown
@AGENTS.md

## Claude Code specifics

...anything that only applies to Claude Code...
```

A symlink would also work, but on Windows creating one requires Administrator
privileges or Developer Mode, so use the import.

Other agents read `AGENTS.md` directly and get the same instructions. Nothing that
matters to more than one agent should ever be written below the import.

## What loads, and when

This is the part that determines whether the structure is cheap or expensive.

- `CLAUDE.md` in the working directory and **every directory above it** loads at
  launch, every session.
- `@path` imports are expanded inline at launch. **Imports do not save context.** A
  `context/` directory that grows over time and is imported at root gets more expensive
  every session, forever, and larger instruction files reduce how reliably they're
  followed. Target under 200 lines.
- `CLAUDE.md` files in **subdirectories** below the working directory load on demand,
  when Claude reads files in that directory.

That last behaviour is the whole reason for the one-line `CLAUDE.md` in each project
folder. `projects/foo/CLAUDE.md` containing `@foo.md` means the project's index note
becomes its context exactly when the agent starts working in that folder, and costs
nothing the rest of the time.

So: root `AGENTS.md` imports only the small, stable core of `context/`. Everything
else is *described* there so the agent knows to go read it, rather than imported so it
loads whether it's needed or not.

To verify what actually loaded in a session, run `/context` and check under **Memory
files**. If a file isn't listed, Claude cannot see it — no amount of rewriting the file
will help.

## Auto memory into the vault

By default Claude Code writes its own memory to `~/.claude/projects/<project>/memory/`,
machine-local and outside the vault. Redirect it with `autoMemoryDirectory` in
`.claude/settings.local.json`, pointed at this machine's own buffer:

```json
{
  "autoMemoryDirectory": "C:\\Users\\Admin\\Obsidian\\big-beautiful-brain\\BBB\\memories\\desktop-win"
}
```

Backslashes are doubled because this is JSON, where a single backslash escapes the next
character. The value must be an absolute path or start with `~/`.

Two things about that placement are load-bearing. The vault syncs, so each machine
writes only its own `memories/<machine-id>/` subdirectory — two machines sharing one
memory directory would conflict on `MEMORY.md` (see `references/memory-protocol.md`).
And the key must sit in `settings.local.json`, not the checked-in project
`settings.json`: it differs per machine, and Claude Code ignores `autoMemoryDirectory`
in checked-in project settings for security — put it there and it configures nothing.

What this gets you: Claude writes `MEMORY.md` plus one topic file per memory, into the
vault, as plain markdown that Obsidian will index and that the user can read and edit.

What to know about it:

- `MEMORY.md` is an index. Its first 200 lines (or 25KB) load at the start of every
  session; topic files are read on demand. It is the same pattern as the project index
  notes, arrived at independently.
- Claude Code excludes the memory directory from its transcript retention cleanup, so
  these files persist until someone deletes them.
- Claude Code adds a `modified` timestamp to memory files that already have
  frontmatter, and never adds frontmatter to a file that has none. Seed `MEMORY.md`
  with a frontmatter block to get timestamps.
- To turn it off for this machine: `"autoMemoryEnabled": false` in the same file.

## Enforcement

`CLAUDE.md` and `AGENTS.md` are context, not enforced configuration. They shape what an
agent does; they do not constrain it. Anything that must happen regardless of what the
agent decides needs a hook.

The relevant one here is `PostToolUse`, firing after writes under `projects/` to run
`build_index.py`. Offer it once the conventions have stopped changing — a hook wired to
a convention still in flux is a thing that breaks every time the convention moves.

## Which settings file gets what

Settings layer: managed → user → project → local, with later layers winning.

**`.claude/settings.json`** — machine-independent: anything true of the vault no matter
who opens it. Note that *how* it reaches other machines depends on the sync mechanism:
Obsidian Sync never syncs hidden files or folders, so nothing under `.claude/`
propagates through it — every machine gets this file from the setup skill, which is why
the published bbb-skills repo (ADR-0013's Open item, since closed) is the actual
distribution mechanism for shared config. Under git, the file syncs normally.

**`.claude/settings.local.json`** — this machine only, never synced. Holds
`autoMemoryDirectory` and the `env` block:

```json
{
  "autoMemoryDirectory": "<vault>/memories/<machine-id>",
  "env": {
    "BBB_VAULT_ROOT": "<vault>",
    "BBB_MACHINE_ID": "<machine-id>",
    "BBB_VAULT_ID": "<vault-id>",
    "BBB_SETUP_SKILL": "bbb-vault-setup",
    "BBB_SETUP_SOURCE": "github-bbb-agent:x0acce55/bbb-skills.git"
  }
}
```

`env` values are exported into the session, so `$BBB_VAULT_ROOT` is available to any
command an agent runs. That is what lets the vault be located from any working
directory, and what `verify_setup.py` reads first.

Keep these to string values in `env` and documented settings keys. Invented top-level
keys are not part of the settings schema and may surface as validation errors in
`claude doctor`, so metadata belongs in `env` where it is both valid and useful.

**What does not go in settings:** instructions. "Use the bbb-vault-setup skill" is
behavioural guidance and belongs in `AGENTS.md`, which is the file an agent actually
reads as instruction. Settings are enforced by the client regardless of what the agent
decides; `AGENTS.md` shapes what it decides. Putting a directive in JSON gets you
neither.

## Session tiers and credentials

Sessions carry an identity — vault, machine, domain, tier — set by a launch wrapper
(ADR-0019). The tiers map to Claude Code's own mechanisms: read-only is
`--permission-mode plan`; elevated is default mode plus deny rules on the governance
surface (`decisions/`, `context/`, `.claude/`, the root instruction files) with writes
confined to `$BBB_SESSION_DOMAIN`; privileged is `acceptEdits` at the vault root.
`Read` deny rules are best-effort — a bash command can still read a denied file after a
prompt — so enable the macOS sandbox for work tiers to make the rules bind on bash too.
These are guardrails against accident, not a security boundary; the boundaries are
separate OS accounts or separate vaults.

Credentials never live in the vault (ADR-0020): MCP OAuth is handled by Claude Code
itself, outside the vault; anything a script needs comes from the OS keychain, injected
by the wrapper as env for that one session. Which MCP servers attach is scoped per
domain via a `.mcp.json` at the domain root, gated by `enabledMcpjsonServers`.

## Detecting the vault, and fetching the skill later

`scripts/verify_setup.py` resolves the vault from its argument, then `$BBB_VAULT_ROOT`,
then by walking up from the working directory looking for `.obsidian/`. It exits 0 when
this machine is registered, 4 when the vault is present but the machine is not, and 5
when no vault is found.

Those exit codes exist so the check can eventually be automated. Right now it is a
manual check that reports what it finds — that is deliberate, because the automated
version should not be wired up until the conventions have stopped moving (the skill
is published now, so that is the remaining gate).

When you are ready for that, the mechanism is a `SessionStart` hook, not a setting:
`settings.local.json` cannot fetch anything, it only holds configuration. A `SessionStart`
hook runs a command when a session begins or resumes, which is where a "clone the setup
repo if the vault is missing" step would live, branching on exit code 5.

Two things to know before writing it. `SessionStart` takes no tool matcher — its matcher
filters on the source (`startup`, `resume`, `clear`, `compact`). And adding an `if` field
to a non-tool event like `SessionStart` silently prevents the hook from running at all,
which is a confusing failure to debug.

`BBB_SETUP_SOURCE` is set at registration to the machine's clone URL of the bbb-skills
repo — `github-bbb-agent:x0acce55/bbb-skills.git` through the standard host alias.
`verify_setup.py` reports it and warns when it is empty; a machine registered before
the repo existed should backfill it.

## Related settings worth knowing

- `claudeMdExcludes` — skip specific `CLAUDE.md` files by glob. Useful if the vault ends
  up nested under a directory that has its own.
- `.claude/rules/` with `paths:` frontmatter — instructions scoped to matching files,
  loaded only when the agent touches them. A third loading tier between "always" and
  "on directory read," if per-project `CLAUDE.md` turns out to be too coarse.
