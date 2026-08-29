# claude-fallback

Paid fallback for Claude Code when the Max subscription runs out, plus one-off
Fable 5 access from anywhere. Backend: **Claude Platform on AWS** — the
Anthropic-operated endpoint (`aws-external-anthropic.us-east-1.api.aws`), billed
through AWS Marketplace, with same-day first-party API parity (`claude-fable-5`
verified present). Not Amazon Bedrock — Bedrock is partner-operated and does
not carry Fable 5.

## How it works

Two PATH shims, no settings file:

- `bin/claude-paid` — full fallback session. Fetches the 365-day CPA key from
  Secret Manager (`anthropic-api-key`, project `secops-opintel`) into that one
  session's env as `ANTHROPIC_AUTH_TOKEN`, sets `ANTHROPIC_BASE_URL` and the
  required `anthropic-workspace-id` header via `ANTHROPIC_CUSTOM_HEADERS`
  (Claude Code ≥ 2.1.227), then `exec claude "$@"`. Alternate key sources
  (leading flags; everything after them passes to claude):
  - `claude-paid -s <secret-name> ...` — a different Secret Manager secret,
    same project/endpoint/workspace (the "multiple keys" path).
  - `claude-paid -k <key> ...` — literal key, break-glass for when gcloud is
    down. **A pasted literal lands in shell history** — use
    `-k "$(<command>)"` or `CLAUDE_PAID_KEY="$(<command>)" claude-paid ...`
    instead whenever possible.
  - Precedence: `-k` > `-s` > `CLAUDE_PAID_KEY` env > default secret. An empty
    result from any source fails loudly before claude launches.
- `bin/fable` — same wrapper around `claude -p --model claude-fable-5` for
  one-off questions from any context.

Default `claude` stays on the Max subscription; backend choice is launch-time
only (verified — no mid-session switching).

## Why NOT apiKeyHelper (the hard-won part)

The obvious design — an `apiKeyHelper` in a `--settings` file — **cannot work
against this endpoint**: Claude Code sends helper output in BOTH the
`Authorization: Bearer` and `x-api-key` headers, and the CPA endpoint returns
**401 whenever both are present** (verified by probe: x-api-key alone 200,
Bearer alone 200, both 401). `ANTHROPIC_AUTH_TOKEN` sends Bearer only, and —
unlike `ANTHROPIC_API_KEY` — carries no one-time interactive approval prompt,
so `-p` works non-interactively.

## Other gotchas

- **Probe the endpoint the key belongs to.** A CPA key against
  `api.anthropic.com` returns `invalid x-api-key` — wrong door, not a bad key.
  Working probe shape:
  `curl -s -H "x-api-key: <key>" -H "anthropic-version: 2023-06-01" -H "anthropic-workspace-id: <wrkspc>" https://aws-external-anthropic.us-east-1.api.aws/v1/models`
- Model IDs are bare first-party strings (`claude-fable-5`) — no `anthropic.` prefix.
- The workspace ID is not a secret; it lives in the shims plainly.

## Key lifecycle

- The key is a **long-term (365-day) CPA key**, minted in the Claude console of
  the AWS account. Rotate before expiry (set a reminder): mint a new one, then
  `pbpaste | gcloud secrets versions add anthropic-api-key --data-file=- --project=secops-opintel`,
  clear the clipboard, disable the old key in the console, destroy the old
  secret version. Shims always read `latest`.
- **Zero-standing-secret alternative** (stricter, not currently used): CPA also
  mints short-term keys (≤12h) from AWS credentials
  (`pip install token-generator-for-aws-external-anthropic`); a shim could mint
  per invocation instead of fetching from Secret Manager, at the cost of
  requiring a live AWS SSO session. Revisit with the agent-service-account /
  federation work.

## Install (per machine — user-run; PATH executables are human acts)

1. `cp bin/claude-paid bin/fable <a PATH dir>/` and `chmod +x` them
   (macOS: /opt/homebrew/bin; Linux: ~/.local/bin; Windows Git Bash: ~/bin).
2. Requires gcloud installed and authenticated as yourself, with
   `secretmanager.versions.access` on the secret.
3. Test without touching the subscription: `claude-paid -p "reply OK" --model haiku`.
4. If a `~/.claude/paid-settings.json` exists from the v2 design, delete it —
   it is obsolete and its apiKeyHelper breaks against this endpoint.
