---
type: adr
status: accepted
summary: Every agent session has an identity — vault, machine, domain, tier — set by a launch wrapper; tiers map to plan mode, scoped default mode, and acceptEdits, and credentials scope by domain and vault.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0019: Sessions carry an identity — vault, machine, domain, tier

## Context

Until now a session's only identity was the machine (`BBB_MACHINE_ID`,
ADR-0013). Three pressures demand more. Work and personal domains (ADR-0018)
need different write scopes and different credentials. Three levels of write
authority are wanted: read-only, elevated (some write), and privileged
(vault-wide, including governance files). And more than one vault will exist —
an agent must know *which* vault it is in and therefore which credentials
apply.

Two axes were being conflated and must be separated: **write authority** (what
the session may change) and **credential scope** (whose accounts and which MCP
servers the session can act through). A read-only session may still need work
credentials to look things up; a privileged maintenance session may need no
external credentials at all.

## Decision

A session's identity is the tuple **(vault, machine, domain, tier)**, plus a
credential profile derived from vault and domain.

**Identity is set at launch by a wrapper**, not mid-session: small entry points
(`bbb <domain>`, `bbb <domain> --ro`, `bbb admin`) that cd to the domain root
(vault root for admin), export `BBB_SESSION_DOMAIN` and `BBB_SESSION_TIER`
alongside the existing env block, and pass the permission mode. Each vault's
`.claude/settings.local.json` gains `BBB_VAULT_ID` — a stable short name,
independent of the folder path — so any session can tell vaults apart and
tooling can key credential profiles on (vault, domain). `verify_setup.py`
warns when it is missing.

**Tiers map to Claude Code's real mechanisms:**

- *read-only* → `--permission-mode plan`. Structurally unable to modify files
  or run state-changing commands.
- *elevated* → default mode, plus deny rules in the vault root's
  `.claude/settings.json` on the governance surface: `decisions/`, `context/`,
  `.claude/`, `AGENTS.md`, `CLAUDE.md`, `BBB.md`. Writes are confined to the
  session's domain by a `PreToolUse` hook that reads `$BBB_SESSION_DOMAIN` —
  one hook and one variable rather than a settings file per domain × tier.
- *privileged* → `acceptEdits` at the vault root; the only tier that touches
  governance paths, runs distillation, or edits another domain.

**Credentials scope by directory and by Claude Code's own storage.** MCP OAuth
tokens live where Claude Code puts them — outside the vault — and are never
reimplemented. Which servers *attach* is scoped per domain: a `.mcp.json` at
the domain root (the session's launch directory), gated by
`enabledMcpjsonServers`, so work Gmail/Drive/Slack exist only in work
sessions. Secrets themselves are governed by ADR-0020.

**Honesty clause**, in the ADR-0010 tradition: this is a guardrail against
accident and drift, not a security boundary. `Read(...)` deny rules are
best-effort across the built-in tools and a bash command can still read a
denied file (prompting first, in default mode). Enabling Claude Code's sandbox
on macOS makes the filesystem rules bind on bash too and is expected for work
tiers. The actual boundaries are separate OS user accounts or separate vaults;
documentation that implies otherwise is a bug in the documentation.

## Rejected

**A settings file per domain × tier.** N×3 files that drift; the wrapper +
hook + shared deny rules express the same matrix in three moving parts.

**Everything in one always-elevated posture.** The status quo. Makes every
prompt-injection and every mistake vault-wide.

**`bypassPermissions` for the privileged tier.** Privileged means "may touch
governance," not "skip the seatbelts." Deny rules still apply under
acceptEdits; bypass discards them for nothing.

**Per-domain OS accounts now.** The real boundary, and disproportionate while
one person operates every domain. Recorded as the escalation path alongside
separate vaults.

## Consequences

Session start becomes deliberate: pick a domain and a tier. That friction is
the feature — it is the moment credentials and write scope get chosen.

Auto memory remains **machine**-scoped, not domain-scoped: one buffer per
machine feeds every session on it, so cross-domain facts meet in the buffer
and are separated only at distillation (routing rule added to
`bbb-memory-distill`). Acceptable while one person operates all domains.

**Open:** verify empirically, on this machine, what project scope Claude Code
resolves when launched in a domain folder of a non-git vault — check
`/permissions` and `/mcp` in a test session. If domain-level `.claude` and
`.mcp.json` are not picked up there, the wrapper supplies them per session
instead. Do this before writing the wrappers.

**Open:** adopt the `PreToolUse` domain-confinement hook once conventions
settle — the same trigger as ADR-0010's hook. Until then the elevated tier is
deny-rules only.

**Open:** if a future employer's confidentiality rules make the shared memory
buffer unacceptable, the answer is a separate vault (ADR-0018), not a lock on
the buffer.
