# claude-fallback

Paid fallback for Claude Code when the Max subscription runs out, plus one-off
Fable 5 access from anywhere. Backend: Anthropic Console API key (Audacy org),
stored as Secret Manager secret `anthropic-api-key` in `secops-opintel` —
chosen over Bedrock because Fable 5 is not offered on Bedrock.

## How it works

- `paid-settings.json` carries an `apiKeyHelper` that fetches the key via
  gcloud at call time (re-invoked every ~5 min or on 401). The key never rests
  on disk, never sits in env, never enters agent context.
- **The helper must NOT go in the main settings**: `apiKeyHelper` outranks
  subscription OAuth in Claude Code's auth precedence, so putting it in
  `~/.claude/settings.json` would bill every session to the API forever.
  It lives in its own file, used only via `--settings`.
- `bin/claude-paid` — full fallback session: `claude --settings ~/.claude/paid-settings.json`.
- `bin/fable` — one-off `claude -p --model claude-fable-5` with the key in a
  single invocation's env (ADR-0020 rule-2 wrapper).
- Backend choice is launch-time only (verified): when Max runs out mid-session,
  start a new session with `claude-paid`. The built-in alternative is the
  `autoContinueAtUsageLimit` setting (wait for reset).

## Install (per machine — user-run; PATH executables and settings are human acts)

1. `cp paid-settings.json ~/.claude/paid-settings.json`
2. `cp bin/claude-paid bin/fable <a PATH dir>/` and `chmod +x` them
   (macOS: /opt/homebrew/bin; Linux: ~/.local/bin; Windows Git Bash: ~/bin —
   same targets as the twss shim).
3. Requires gcloud installed and authenticated as yourself, with
   `secretmanager.versions.access` on the secret.
4. Test without touching the subscription: `claude-paid -p "reply OK" --model haiku`
   (~fractions of a cent, billed to the key).

## Key lifecycle

- Create/rotate in the Audacy Anthropic Console (human act), then:
  `pbpaste | gcloud secrets versions add anthropic-api-key --data-file=- --project=secops-opintel`
  (first time: `gcloud secrets create` instead) — and clear the clipboard.
  Disable the old key in the Console; the helper picks up the new version
  within its ~5-minute TTL.
- Fable 5 requires 30-day data retention — not available under zero-data-retention orgs.

## Deferred: Bedrock lane

Fable 5 absent on Bedrock (verified 2026-08-29). If an AWS-billed Opus 5 lane
is ever wanted: Claude Code honors SSO profiles + `awsAuthRefresh` natively —
zero standing credentials, strictly better than an IAM user with a stored key.
The IAM-user chain only earns its place for headless agents; revisit with the
workforce-federation / agent-service-account work. Note: AWS CLI must be
≥ 2.13 for `bedrock` commands.
