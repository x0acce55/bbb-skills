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

It does **not** trust the domain folders — that is interactive and per machine.
See **Trust each domain once** below; until it is done the generated grants do
not fire.

Requires `jq` and a machine already registered via `bbb-vault-setup` (the
install reads `BBB_MACHINE_ID` from the vault's `.claude/settings.local.json`).

**Windows:** `bbb.ps1` does not exist yet. Until it does, prove-desktop-win
launches sessions the old way; watch the vault's cross-machine-actions note.

## Trust each domain once (required)

`bbb install` is not enough on its own. Claude Code **silently ignores
`permissions.allow` from a project's `.claude/settings.json` until that folder
has been trusted**, and trust is per folder, per machine, and granted
interactively:

```
Ignoring 6 permissions.allow entries from .claude/settings.json:
this workspace has not been trusted.
```

So the first launch of every domain on every machine has to be interactive —
`bbb <domain>` — with the trust dialog accepted. Until then the session is
*more* restricted than designed, not less:

| Layer | Untrusted folder | Verified by |
| --- | --- | --- |
| `permissions.deny` | applies | headless probe, 2026-08-29 |
| `sandbox` | applies | headless probe, 2026-08-29 |
| `permissions.allow` | **silently ignored** | headless probe, 2026-08-29 |
| `enabledMcpjsonServers` / `.mcp.json` | **applies** | live untrusted session, 2026-08-30 |
| `autoMode` | unverified | — |

Fail-safe, but confusing in practice: grants you can read in the generated file
simply do not fire, and the session prompts for commands the fragment already
allows. **If a domain session keeps asking permission for something you know is
granted, check trust before you debug the fragment.**

MCP is decided by **directory scope, not trust**: a session whose cwd is the domain
folder gets its `.mcp.json` servers even with the trust flag false. Only the grants
evaporate.

Trust is recorded in `~/.claude.json` under
`projects["<abs-path>"].hasTrustDialogAccepted`. Read it to check the state.
Setting it by hand is granting yourself enforcement — a human action, not an
agent one.

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

## Smoke test

`sandbox-smoke-test.sh` proves a domain session really is sandboxed, that its
write boundary holds, and that the credential and network workflows survive
Seatbelt. Run it inside the domain session, after accepting trust:

```sh
sh bbb-launcher/sandbox-smoke-test.sh \
  --project secops-opintel \
  --secret tines-api-credentials \
  --url https://crimson-cloud-7047.tines.com/
```

`--secret` and `--url` may each repeat; all secrets share one `--project`. Both
are optional — with no arguments it still checks the sandbox and the write
boundary.

The first block is a control test: it tries to write to `$HOME` and declares the
whole run VOID if that succeeds, because an unsandboxed session passes every
other check trivially. Exit 0 means the sandbox was active and nothing behaved
unexpectedly; exit 1 means read the UNEXPECTED / FAILED / VOID lines.

The secret test never prints a value — stdout goes to `/dev/null`, and only the
exit code and stderr are reported (ADR-0020). Keep it that way.
