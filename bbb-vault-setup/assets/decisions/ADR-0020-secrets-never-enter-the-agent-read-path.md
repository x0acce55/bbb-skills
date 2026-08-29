---
type: adr
status: accepted
summary: Credentials never live in the vault or pass through the agent's readable surface; MCP auth stays native, script credentials come from the OS keychain via the launch wrapper.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0020: Secrets never enter the agent's read path

## Context

Sessions need credentials — MCP connections to work and personal services, and
occasionally tokens for scripts. The obvious designs all put a secret
somewhere an agent can read it, and that is the flaw: **anything an agent
reads becomes conversation state.** It can persist in the transcript and in
auto-memory files that live in the vault and sync to every machine. Encryption
at rest does not help; the moment the value is decrypted into context, it is
on the exfiltration surface.

Obsidian 1.11+ has a native Secret Storage API backed by the OS keychain. It
is the right home for *Obsidian plugins'* keys — per-device, out of
`data.json` — but it is a plugin-facing store, not a session-credential
transport, and fetching from it into an agent session has the same exposure as
any other read.

The vault also syncs (Obsidian Sync), so anything written into a vault file —
including the `env` block of `settings.local.json`, which is plaintext on disk
— must be assumed replicated and backed up in places no one audits.

## Decision

Four rules, in order of how often they apply:

1. **MCP authentication stays native.** Claude Code performs the OAuth flows
   and stores tokens in its own credential storage, outside the vault. Never
   reimplemented, never copied.
2. **Script and tool credentials come from the OS keychain, injected by the
   launch wrapper.** On macOS, `security find-generic-password` (or a password
   manager's CLI); the wrapper exports the value as env for that one session.
   The agent receives the capability without a file to read; nothing
   credential-shaped is ever written to `settings*.json`, `CLAUDE.md`, or any
   note.
3. **Defense in depth on the read side.** Deny-`Read` rules cover
   credential-shaped paths (`**/.env`, key files); the macOS sandbox makes
   those rules bind on bash for work tiers (ADR-0019).
4. **Memory and distillation are secret-free.** Tokens, keys, and passwords
   are never written to memory buffers; distillation drops anything
   credential-shaped on sight and flags that it did.

If a note needs to *refer* to a credential, it refers by name — or via a
display-only placeholder plugin that resolves from a password manager at
render time and never writes the value into the `.md`.

## Rejected

**Secrets in vault notes, encrypted-note plugins included.** Sync exposure
plus agent exposure; the encrypted variant merely defers the exposure to the
moment of use.

**Obsidian's Secret Storage as the session transport.** Right store, wrong
consumer. Keep it for plugins; sessions get theirs from the wrapper.

**The `env` block of `settings.local.json`.** Correct for identity
(`BBB_VAULT_ROOT`, `BBB_MACHINE_ID`, `BBB_VAULT_ID`), which is not secret.
Plaintext at rest disqualifies it for tokens.

**A vault-level encrypted secrets file with an agent-usable decrypt step.**
An agent that can decrypt it can paste it, and will eventually be asked to.

## Consequences

Each machine gains a small keychain setup step per credential, owned by the
wrapper. Rotation happens keychain-side and touches nothing in the vault.

A session that lacks a credential fails loudly at the tool call instead of
finding the value lying around — the failure mode this design prefers.

**Open:** a `PreToolUse`/`PostToolUse` redaction hook that pattern-matches
token shapes in tool output before they enter context would move rule 4 from
"instructed" to "enforced" on the ladder. Revisit with the other hooks once
conventions settle.
