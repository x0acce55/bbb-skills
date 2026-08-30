# bbb-launcher

Session launcher for the BBB vault, implementing ADR-0019 (sessions carry
identity and tier) via ADR-0036 (domain settings carry session config; the
wrapper carries identity). See those ADRs in the vault's `decisions/` for the
full rationale — this README is the install and operating procedure.

## What it does

```
bbb <domain>            elevated session at projects/<domain> (default mode)
bbb <domain> --ro       read-only session there (plan mode)
bbb admin               privileged session at the vault root (acceptEdits)
bbb admin --ro          read-only session at the vault root
bbb                     list domains
bbb install <vault>     (re)generate all per-machine config
```

The `bbb` script exports the identity tuple (`BBB_VAULT_ROOT`, `BBB_MACHINE_ID`,
`BBB_VAULT_ID`, `BBB_SESSION_DOMAIN`, `BBB_SESSION_TIER`), cds to the right
root, and execs `claude` with the tier's permission mode. **Nothing else rides
the wrapper.** Deny rules, MCP gating, sandbox, memory wiring, and hooks live
in each domain's generated `.claude/settings.json`, so a bare `claude` launched
in a domain folder is equally protected.

## Why generated files

Claude Code resolves project settings from the cwd only (no upward walk in a
non-git tree), `CLAUDE.md` walks up ancestors, and `.mcp.json` walks up too —
verified empirically 2026-08-29, recorded in ADR-0036. So:

- Domain launches lose the vault root's settings → the generated domain
  settings resupply memory, hooks, and guardrails.
- `.mcp.json` at the vault root would leak into every domain → the vault root
  must never carry one; servers live per domain.
- Deny rules bind every tier and can't be overridden → governance denies live
  only in domain settings, which privileged sessions (vault root) never load.

Dot-files never sync (Obsidian Sync skips hidden files), so every machine
generates its own. `domains/<domain>.json` fragments here are the source;
`projects/<domain>/.claude/settings.json` and `.mcp.json` are outputs. Edit
the fragment, re-run `bbb install`, never the output.

## Fragment format

```json
{
  "mcpServers":            { ...written to projects/<d>/.mcp.json... },
  "enabledMcpjsonServers": [ ...hand-written gate; the whole point... ],
  "permissions":           { "allow": [ ...domain-scoped allows... ] },
  "autoMode":              { "allow": [ ...domain-scoped auto-mode grants... ] }
}
```

Everything except `mcpServers` merges over the generated base settings. Do NOT
derive `enabledMcpjsonServers` from `mcpServers` keys — the hand-list is the
approval gate.

Note: permission-granting content (`permissions.allow`, `autoMode`) is
enforcement surface — agents are blocked from writing it, by design. Those
blocks are the human's to add to a fragment.

## Install (per machine)

```sh
sh bbb-launcher/bbb install /path/to/vault/BBB
```

Idempotent; re-run after adding a domain, editing a fragment, or pulling this
repo. It:

1. writes `~/.config/bbb/env` (the seed: `BBB_VAULT_ROOT=...`),
2. generates each domain's `.claude/settings.json` (+ `.mcp.json` where the
   fragment declares servers),
3. ensures the vault root's `settings.json` carries the universal credential
   read-denies (`**/.env`, `**/*.pem`, `**/*.key`) — the one deny set that
   binds every tier, ADR-0020,
4. symlinks `bbb` into `/opt/homebrew/bin` (adjust on non-Homebrew machines).

Requires `jq` and a machine already registered via `bbb-vault-setup` (the
install reads `BBB_MACHINE_ID` from the vault's `.claude/settings.local.json`).

**Windows:** `bbb.ps1` does not exist yet. Until it does, prove-desktop-win
launches sessions the old way; watch the vault's cross-machine-actions note.

## Sandbox posture

Domain sessions run with `sandbox.enabled: true` (macOS Seatbelt — makes the
deny rules bind on bash) and `autoAllowBashIfSandboxed: false`. If a credential
workflow (gcloud / Tines / Zendesk fetch-at-call-time) misbehaves inside the
sandbox, the escape is the per-call unsandboxed prompt — approve it or add a
targeted `sandbox.filesystem` rule to the fragment, don't disable the sandbox.
Flipping `autoAllowBashIfSandboxed` to true is a later hardening decision
(ADR-0036, Open).

Admin sessions (vault root) are deliberately unsandboxed and carry no
governance denies — that's the privileged tier doing its job. The honesty
clause from ADR-0019 stands: tiers are guardrails against accident, not a
security boundary.
